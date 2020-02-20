from __future__ import absolute_import

import logging

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import (
    IncorrectClientSecretException,
    InvalidSessionIdException,
    IncorrectSessionTokenException,
    SessionExpiredException,
    ValidationSession,
    NextLinkValidationException,
)
from sydent.util import time_msec
from sqlite3 import IntegrityError


logger = logging.getLogger(__name__)


def validateSessionWithToken(sydent, sid, clientSecret, token, next_link=None):
    """
    Attempt to validate a session, identified by the sid, using
    the token from out-of-band. The client secret is given to
    prevent attempts to guess the token for a sid.

    :param sid: The ID of the session to validate.
    :type sid: unicode
    :param clientSecret: The client secret to validate.
    :type clientSecret: unicode
    :param token: The token to validate.
    :type token: unicode
    :param next_link: The link to redirect the client to after validation, if provided
    :type next_link: unicode or None


    :return: A dict with a "success" key which is True if the session
        was successfully validated, False otherwise.
    :rtype: dict[str, bool]

    :raise IncorrectClientSecretException: The provided client_secret is incorrect.
    :raise SessionExpiredException: The session has expired.
    :raise InvalidSessionIdException: The session ID couldn't be matched with an
        existing session.
    :raise IncorrectSessionTokenException: The provided token is incorrect
    """
    valSessionStore = ThreePidValSessionStore(sydent)
    s = valSessionStore.getTokenSessionById(sid)
    if not s:
        logger.info("Session ID %s not found", sid)
        raise InvalidSessionIdException()

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
        logger.info(
            "Validation attempt rejected as provided 'next_link' is different "
            "from that in a previous, successful validation attempt with this "
            "session id"
        )
        raise NextLinkValidationException()

    # TODO once we can validate the token oob
    #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
    #    return True

    if s.token == token:
        logger.info("Setting session %s as validated", s.id)
        valSessionStore.setValidated(s.id, True)

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
        return IncorrectSessionTokenException()
