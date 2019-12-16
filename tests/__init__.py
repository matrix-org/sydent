from twisted.test.proto_helpers import MemoryReactorClock
from sydent.sydent import Sydent
from sydent.sydent import CONFIG_DEFAULTS


def make_sydent(config={}):
    """Create a new sydent

    Args:
        config (dict): any configuration variables for overriding the default sydent
            config
    """
    # Override default config with provided dict contents
    config = CONFIG_DEFAULTS
    for section in config.keys():
        if section not in config:
            config[section] = {}
        for option in section.keys():
            config[section][option] = config[section][option]

    reactor = MemoryReactorClock()
    return Sydent(reactor, config=config)
