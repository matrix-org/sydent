from twisted.test.proto_helpers import MemoryReactorClock
from sydent.sydent import Sydent


def make_sydent(test_config={}):
    """Create a new sydent

    Args:
        test_config (dict): any configuration variables for overriding the default sydent
            config
    """
    reactor = MemoryReactorClock()
    return Sydent(reactor, config=test_config)
