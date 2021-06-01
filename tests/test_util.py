from twisted.trial import unittest

from sydent.util.stringutils import is_valid_matrix_server_name


class UtilTests(unittest.TestCase):
    """Tests Sydent utility functions."""

    def test_is_valid_matrix_server_name(self):
        """Tests that the is_valid_matrix_server_name function accepts only
        valid hostnames (or domain names), with optional port number.
        """
        self.assertTrue(is_valid_matrix_server_name("9.9.9.9"))
        self.assertTrue(is_valid_matrix_server_name("9.9.9.9:4242"))
        self.assertTrue(is_valid_matrix_server_name("[::]"))
        self.assertTrue(is_valid_matrix_server_name("[::]:4242"))
        self.assertTrue(is_valid_matrix_server_name("[a:b:c::]:4242"))

        self.assertTrue(is_valid_matrix_server_name("example.com"))
        self.assertTrue(is_valid_matrix_server_name("EXAMPLE.COM"))
        self.assertTrue(is_valid_matrix_server_name("ExAmPlE.CoM"))
        self.assertTrue(is_valid_matrix_server_name("example.com:4242"))
        self.assertTrue(is_valid_matrix_server_name("localhost"))
        self.assertTrue(is_valid_matrix_server_name("localhost:9000"))
        self.assertTrue(is_valid_matrix_server_name("a.b.c.d:1234"))

        self.assertFalse(is_valid_matrix_server_name("[:::]"))
        self.assertFalse(is_valid_matrix_server_name("a:b:c::"))

        self.assertFalse(is_valid_matrix_server_name("example.com:65536"))
        self.assertFalse(is_valid_matrix_server_name("example.com:0"))
        self.assertFalse(is_valid_matrix_server_name("example.com:-1"))
        self.assertFalse(is_valid_matrix_server_name("example.com:a"))
        self.assertFalse(is_valid_matrix_server_name("example.com: "))
        self.assertFalse(is_valid_matrix_server_name("example.com:04242"))
        self.assertFalse(is_valid_matrix_server_name("example.com: 4242"))
        self.assertFalse(is_valid_matrix_server_name("example.com/example.com"))
        self.assertFalse(is_valid_matrix_server_name("example.com#example.com"))
