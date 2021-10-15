import logging
from typing import TYPE_CHECKING, Dict

from sydent.db.valsession import ThreePidValSessionStore
from sydent.util import time_msec
from sydent.validators import (
    THREEPID_SESSION_VALIDATION_TIMEOUT_MS,
    IncorrectClientSecretException,
    IncorrectSessionTokenException,
    InvalidSessionIdException,
    SessionExpiredException,
)

if TYPE_CHECKING:
    from sydent.sydent import Sydent

logger = logging.getLogger(__name__)


def validateSessionWithToken(
    sydent: "Sydent", sid: int, clientSecret: str, token: str
) -> Dict[str, bool]:
    """
    Attempt to validate a session, identified by the sid, using
    the token from out-of-band. The client secret is given to
    prevent attempts to guess the token for a sid.

    :param sid: The ID of the session to validate.
    :param clientSecret: The client secret to validate.
    :param token: The token to validate.

    :return: A dict with a "success" key which is True if the session
        was successfully validated, False otherwise.

    :raise IncorrectClientSecretException: The provided client_secret is incorrect.
    :raise SessionExpiredException: The session has expired.
    :raise InvalidSessionIdException: The session ID couldn't be matched with an
        existing session.
    :raise IncorrectSessionTokenException: The provided token is incorrect
    """
    valSessionStore = ThreePidValSessionStore(sydent)
    result = valSessionStore.getTokenSessionById(sid)
    if not result:
        logger.info("Session ID %s not found", sid)
        raise InvalidSessionIdException()

    session, token_info = result

    if not clientSecret == session.client_secret:
        logger.info("Incorrect client secret", sid)
        raise IncorrectClientSecretException()

    if session.mtime + THREEPID_SESSION_VALIDATION_TIMEOUT_MS < time_msec():
        logger.info("Session expired")
        raise SessionExpiredException()

    # TODO once we can validate the token oob
    # if tokenObj.validated and clientSecret == tokenObj.clientSecret:
    #    return True

    if token_info.token == token:
        logger.info("Setting session %s as validated", session.id)
        valSessionStore.setValidated(session.id, True)

        return {"success": True}
    else:
        logger.info("Incorrect token submitted")
        raise IncorrectSessionTokenException()
