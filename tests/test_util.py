from twisted.trial import unittest
from sydent.util.stringutils import is_valid_hostname


class UtilTests(unittest.TestCase):
    """Tests Sydent utility functions."""
    def test_is_valid_hostname(self):
        """Tests that the is_valid_hostname function accepts only valid
        hostnames (or domain names), with optional port number.
        """

        self.assertTrue(is_valid_hostname("example.com"))
        self.assertTrue(is_valid_hostname("EXAMPLE.COM"))
        self.assertTrue(is_valid_hostname("ExAmPlE.CoM"))
        self.assertTrue(is_valid_hostname("example.com:4242"))
        self.assertTrue(is_valid_hostname("localhost"))
        self.assertTrue(is_valid_hostname("localhost:9000"))
        self.assertTrue(is_valid_hostname("a.b:1234"))

        self.assertFalse(is_valid_hostname("example.com:65536"))
        self.assertFalse(is_valid_hostname("example.com:0"))
        self.assertFalse(is_valid_hostname("example.com:a"))
        self.assertFalse(is_valid_hostname("example.com:04242"))
        self.assertFalse(is_valid_hostname("example.com: 4242"))
        self.assertFalse(is_valid_hostname("example.com/example.com"))
        self.assertFalse(is_valid_hostname("example.com#example.com"))
