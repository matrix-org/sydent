from twisted.trial import unittest
from sydent.server import ThreadedMemoryReactorClock
from sydent.sydent import Sydent


class StartupTestCase(unittest.TestCase):
    """Test that sydent started up correctly"""
    def test_start(self):
        reactor = ThreadedMemoryReactorClock()
        sydent = Sydent(reactor)

        sydent.run()
