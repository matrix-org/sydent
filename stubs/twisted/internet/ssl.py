from typing import Optional, Any

import OpenSSL.SSL
from twisted.internet._sslverify import IOpenSSLTrustRoot


def platformTrust() -> IOpenSSLTrustRoot:
    ...


class CertificateOptions:
    def __init__(self, trustRoot: Optional[IOpenSSLTrustRoot] = None, **kwargs: Any):
        ...

    def _makeContext(self) -> OpenSSL.SSL.Context:
        ...