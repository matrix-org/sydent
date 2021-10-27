from typing import Optional, Any, List, Dict, AnyStr, TypeVar, Type

import OpenSSL.SSL

# I don't like importing from _sslverify, but IOpenSSLTrustRoot isn't re-exported
# anywhere else in twisted.
from twisted.internet._sslverify import IOpenSSLTrustRoot
from twisted.internet.interfaces import IOpenSSLClientConnectionCreator

from zope.interface import implementer

C = TypeVar("C")

class Certificate:
    original: OpenSSL.crypto.X509
    @classmethod
    def loadPEM(cls: Type[C], data: AnyStr) -> C: ...

def platformTrust() -> IOpenSSLTrustRoot: ...

class PrivateCertificate(Certificate): ...

class CertificateOptions:
    def __init__(
        self, trustRoot: Optional[IOpenSSLTrustRoot] = None, **kwargs: Any
    ): ...
    def _makeContext(self) -> OpenSSL.SSL.Context: ...

def optionsForClientTLS(
    hostname: str,
    trustRoot: Optional[IOpenSSLTrustRoot] = None,
    clientCertificate: Optional[PrivateCertificate] = None,
    acceptableProtocols: Optional[List[bytes]] = None,
    *,
    # Shouldn't use extraCertificateOptions:
    # "any time you need to pass an option here that is a bug in this interface."
    extraCertificateOptions: Optional[Dict[Any, Any]] = None,
) -> IOpenSSLClientConnectionCreator: ...


# Type safety: I don't want to respecify the methods on the interface that we
# don't use.
@implementer(IOpenSSLTrustRoot)  # type: ignore[misc]
class OpenSSLDefaultPaths: ...
