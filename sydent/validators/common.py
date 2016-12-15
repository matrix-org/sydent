import logging

from sydent.db.valsession import ThreePidValSessionStore
from sydent.validators import ValidationSession
from sydent.util import time_msec


logger = logging.getLogger(__name__)


def validateSessionWithToken(sydent, sid, clientSecret, token):
    valSessionStore = ThreePidValSessionStore(sydent)
    s = valSessionStore.getTokenSessionById(sid)
    if not s:
        logger.info("Session ID %s not found", (sid))
        return False

    if not clientSecret == s.clientSecret:
        logger.info("Incorrect client secret", (sid))
        raise IncorrectClientSecretException()

    if s.mtime + ValidationSession.THREEPID_SESSION_VALIDATION_TIMEOUT_MS < time_msec():
        logger.info("Session expired")
        raise SessionExpiredException()

    # TODO once we can validate the token oob
    #if tokenObj.validated and clientSecret == tokenObj.clientSecret:
    #    return True

    if s.token == token:
        logger.info("Setting session %s as validated", (s.id))
        valSessionStore.setValidated(s.id, True)

        return {'success': True}
    else:
        logger.info("Incorrect token submitted")
        return False
