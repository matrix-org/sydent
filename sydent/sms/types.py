# See "Request body" section of
# https://www.openmarket.com/docs/Content/apis/v4http/send-json.htm
from typing_extensions import Literal, TypedDict

ToN = Literal[1, 3, 5]


class SendSMSBody(TypedDict):
    mobileTerminate: "MobileTerminate"


class MobileTerminateRequired(TypedDict):
    # OpenMarket says these are required fields
    destination: "Destination"
    message: "Message"


class MobileTerminate(MobileTerminateRequired, total=False):
    # And these are all optional.
    interaction: Literal["one-way", "two-way"]
    promotional: bool  # Ignored, unless you're sending to India
    options: "Options"
    source: "Source"
    delivery: "Delivery"


class MessageRequired(TypedDict):
    type: Literal["text", "hexEncodedText", "binary", "wapPush"]
    content: str


class Message(MessageRequired, total=False):
    charset: Literal["GSM", "Latin-1", "UTF-8", "UTF-16"]
    validityPeriod: int
    url: str
    mlc: Literal["reject", "truncate", "segment"]
    udh: bool


class DestinationRequired(TypedDict):
    address: str


class Destination(DestinationRequired, total=False):
    mobileOperatorId: int


class SourceRequired(TypedDict):
    address: str


class Source(SourceRequired, total=False):
    ton: ToN


# We don't use either of these, so I'm going to be lazy and not specify the members.
class Options(TypedDict):
    pass


class Delivery(TypedDict):
    pass
