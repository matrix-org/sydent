from typing import Optional, Any, List, Dict

import OpenSSL.SSL

# I don't like importing from _sslverify, but IOpenSSLTrustRoot isn't re-exported
# anywhere else in twisted. PrivateCertificate is reexported in
# twisted.internet.ssl, but that's the module we're stubbing!
from twisted.internet._sslverify import IOpenSSLTrustRoot, PrivateCertificate
from twisted.internet.interfaces import IOpenSSLClientConnectionCreator

def platformTrust() -> IOpenSSLTrustRoot: ...

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
