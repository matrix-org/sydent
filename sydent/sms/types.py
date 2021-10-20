# See "Request body" section of
# https://www.openmarket.com/docs/Content/apis/v4http/send-json.htm
from typing_extensions import Literal, TypedDict

TypeOfNumber = Literal[1, 3, 5]


class _MessageRequired(TypedDict):
    type: Literal["text", "hexEncodedText", "binary", "wapPush"]
    content: str


class Message(_MessageRequired, total=False):
    charset: Literal["GSM", "Latin-1", "UTF-8", "UTF-16"]
    validityPeriod: int
    url: str
    mlc: Literal["reject", "truncate", "segment"]
    udh: bool


class _DestinationRequired(TypedDict):
    address: str


class Destination(_DestinationRequired, total=False):
    mobileOperatorId: int


class _SourceRequired(TypedDict):
    address: str


class Source(_SourceRequired, total=False):
    ton: TypeOfNumber


class _MobileTerminateRequired(TypedDict):
    # OpenMarket says these are required fields
    destination: Destination
    message: Message


class MobileTerminate(_MobileTerminateRequired, total=False):
    # And these are all optional.
    interaction: Literal["one-way", "two-way"]
    promotional: bool  # Ignored, unless we're sending to India
    source: Source
    # The API also offers optional "options" and "delivery" keys,
    # which we don't use


class SendSMSBody(TypedDict):
    mobileTerminate: MobileTerminate
