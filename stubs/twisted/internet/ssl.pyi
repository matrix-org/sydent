from typing import Any, AnyStr, Dict, List, Optional, Type, TypeVar

import OpenSSL.SSL

# I don't like importing from _sslverify, but IOpenSSLTrustRoot isn't re-exported
# anywhere else in twisted.
from twisted.internet._sslverify import IOpenSSLTrustRoot, KeyPair
from twisted.internet.interfaces import (
    IOpenSSLClientConnectionCreator,
    IOpenSSLContextFactory,
)
from zope.interface import implementer

_C = TypeVar("_C")

class Certificate:
    original: OpenSSL.crypto.X509
    @classmethod
    def loadPEM(cls: Type[_C], data: AnyStr) -> _C: ...

def platformTrust() -> IOpenSSLTrustRoot: ...

class PrivateCertificate(Certificate):
    # PrivateKey is not set until you call _setPrivateKey, e.g. via load()
    privateKey: KeyPair

@implementer(IOpenSSLContextFactory)
class CertificateOptions:
    def __init__(
        self, trustRoot: Optional[IOpenSSLTrustRoot] = ..., **kwargs: object
    ): ...
    def _makeContext(self) -> OpenSSL.SSL.Context: ...
    def getContext(self) -> OpenSSL.SSL.Context: ...

def optionsForClientTLS(
    hostname: str,
    trustRoot: Optional[IOpenSSLTrustRoot] = ...,
    clientCertificate: Optional[PrivateCertificate] = ...,
    acceptableProtocols: Optional[List[bytes]] = ...,
    *,
    # Shouldn't use extraCertificateOptions:
    # "any time you need to pass an option here that is a bug in this interface."
    extraCertificateOptions: Optional[Dict[Any, Any]] = ...,
) -> IOpenSSLClientConnectionCreator: ...

# Type ignore: I don't want to respecify the methods on the interface that we
# don't use.
@implementer(IOpenSSLTrustRoot)  # type: ignore[misc]
class OpenSSLDefaultPaths: ...
