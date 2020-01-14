from twisted.test.proto_helpers import MemoryReactorClock
from sydent.sydent import Sydent


def make_sydent(test_config={}):
    """Create a new sydent

    Args:
        test_config (dict): any configuration variables for overriding the default sydent
            config
    """
    # Send the Sydent logs to sydent.log in the _trial_temp directory instead of stderr.
    if 'general' not in test_config:
        test_config['general'] = {}
    test_config['general']['log.path'] = 'sydent.log'

    reactor = MemoryReactorClock()
    return Sydent(reactor, config=test_config)
