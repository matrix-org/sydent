from twisted.internet.defer import Deferred
from twisted.web.iweb import IResponse

def readBody(response: IResponse) -> Deferred[bytes]: ...
