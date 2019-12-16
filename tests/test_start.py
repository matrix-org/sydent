from twisted.trial import unittest
from . import make_sydent


class StartupTestCase(unittest.TestCase):
    """Test that sydent started up correctly"""
    def test_start(self):
        sydent = make_sydent()
        sydent.run()
