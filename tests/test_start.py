from twisted.trial import unittest
from twisted.test.proto_helpers import MemoryReactorClock
from sydent.sydent import Sydent


class StartupTestCase(unittest.TestCase):
    """Test that sydent started up correctly"""
    def test_start(self):
        reactor = MemoryReactorClock()
        sydent = Sydent(reactor)

        sydent.run()
