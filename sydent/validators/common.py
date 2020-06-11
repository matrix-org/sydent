from __future__ import absolute_import

import logging

from sydent.db.valsession import ThreePidValSessionStore
from sydent.util import time_msec

from sydent.validators import (
    IncorrectClientSecretException,
    InvalidSessionIdException,
    IncorrectSessionTokenException,
    SessionExpiredException,
    ValidationSession,
)

logger = logging.getLogger(__name__)


def validateSessionWithToken(sydent, sid, clientSecret, token):
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

    # TODO once we can validate the token oob
    #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
    #    return True

    if s.token == token:
        logger.info("Setting session %s as validated", s.id)
        valSessionStore.setValidated(s.id, True)

        return {'success': True}
    else:
        logger.info("Incorrect token submitted")
        raise IncorrectSessionTokenException()
