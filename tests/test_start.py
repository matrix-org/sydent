from twisted.trial import unittest
from tests.utils import make_sydent, setup_logging

setup_logging()


class StartupTestCase(unittest.TestCase):
    """Test that sydent started up correctly"""
    def test_start(self):
        sydent = make_sydent()
        sydent.run()
