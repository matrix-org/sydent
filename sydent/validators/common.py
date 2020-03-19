import logging

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import (
    ValidationSession,
    SessionExpiredException,
    IncorrectClientSecretException,
    NextLinkValidationException,
)
from sydent.util import time_msec
from sqlite3 import IntegrityError
from urlparse import urlparse


logger = logging.getLogger(__name__)


def validateSessionWithToken(sydent, sid, clientSecret, token, next_link=None):
    """
    Attempt to validate a session, identified by the sid, using
    the token from out-of-band. The client secret is given to
    prevent attempts to guess the token for a sid.
    If the session was sucessfully validated, return a dict
    with 'success': True that can be sent to the client,
    otherwise return False.

    :param sid: The session ID
    :type sid: str

    :param clientSecret: The client_secret originally set when requesting the session
    :type clientSecret: str

    :param token: The validation token
    :type token: str

    :param next_link: The link to redirect the client to after validation, if provided
    :type next_link: str|None

    :return: The JSON to return to the client on success, or False on fail
    :rtype: Dict|bool

    :raises IncorrectClientSecretException if the client secret does not match the sid
    :raises SessionExpiredException is the provided session has expired
    :raises NextLinkValidationException if the next_link provided is different
        from one provided in a previous, successful validation attempt
    """
    valSessionStore = ThreePidValSessionStore(sydent)
    s = valSessionStore.getTokenSessionById(sid)
    if not s:
        logger.info("Session ID %s not found", sid)
        return False

    if not clientSecret == s.clientSecret:
        logger.info("Incorrect client secret", sid)
        raise IncorrectClientSecretException()

    if s.mtime + ValidationSession.THREEPID_SESSION_VALIDATION_TIMEOUT_MS < time_msec():
        logger.info("Session expired")
        raise SessionExpiredException()

    # Check whether this session has already been validated with a next_link
    # If so, and the next_link this time around is different, then the
    # user may be getting phished. Reject the validation attempt.
    if next_link and valSessionStore.next_link_differs(sid, token, next_link):
        logger.warning(
            "Validation attempt rejected as provided 'next_link' is different "
            "from that in a previous, successful validation attempt with this "
            "session id"
        )
        raise NextLinkValidationException()

    # Validate the value of next_link
    if next_link and validate_next_link(sydent, next_link):
        logger.warning(
            "Validation attempt rejected as provided 'next_link' value is not "
            "http(s) or domain does not match "
            "general.next_link.domain_whitelist config value: %s",
            next_link,
        )
        raise NextLinkValidationException()

    # TODO once we can validate the token oob
    #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
    #    return True

    if s.token == token:
        logger.info("Setting session %s as validated", s.id)

        # If a next_link parameter was provided, store it alongside the token in the
        # database
        # We want to do this action atomically with setting the session to validated,
        # thud we disable the validation functino from committing to the db, and instead
        # commit in `set_next_link_for_token`
        try:
            with sydent.db:
                cursor = sydent.db.cursor()
                if next_link:
                    # Use a single cursor to complete both transactions
                    cursor.execute(
                        """
                        update threepid_validation_sessions
                        set validated = ? where id = ?
                        """, (True, sid)
                    )

                    cursor.execute(
                        """
                        update threepid_token_auths 
                        set next_link_used = ?
                        where validationSession = ? and token = ?
                        """, (next_link, sid, token)
                    )
                else:
                    cursor.execute(
                        """
                        update threepid_validation_sessions
                        set validated = ? where id = ?
                        """, (True, sid),
                    )
        except IntegrityError as e:
            logger.error(
                "SQL execution failure during 3PID session validation: %r", e
            )
            return False

        return {'success': True}
    else:
        logger.info("Incorrect token submitted")
        return False


def validate_next_link(sydent, next_link):
    """Return whether a given next_link value is valid. next_link is valid if the scheme is
    http(s) and the next_link.domain_whitelist config option is either empty or contains a
    domain that matches the one in the given next_link

    :param sydent: A global sydent object
    :type sydent: Sydent

    :param next_link: The value of the next_link query parameter
    :type next_link: str

    :returns: Whether a given next_link value is valid
    :rtype: bool
    """
    # Parse the contents of the URL
    next_link_parsed = urlparse(next_link)

    # Scheme must be http(s)
    if next_link_parsed.scheme not in ["http", "https"]:
        return False

    # If the domain whitelist is set, the domain must be in it
    if (
            sydent.next_link_domain_whitelist
            and next_link_parsed.hostname not in sydent.next_link_domain_whitelist
    ):
        return False

    return True
