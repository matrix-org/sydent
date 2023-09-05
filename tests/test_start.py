from twisted.trial import unittest

from tests.utils import make_sydent


class StartupTestCase(unittest.TestCase):
    """Test that sydent started up correctly"""

    def test_start(self):
        sydent = make_sydent()
        sydent.run()

    def test_homeserver_allow_list_refuses_to_start_if_v1_not_disabled(self):
        """
        Test that Sydent throws a runtime error if `homeserver_allow_list` is specified
        but the v1 API has not been disabled
        """
        config = {
            "general": {
                "homeserver_allow_list": "friendly.com, example.com",
                "enable_v1_access": "true",
            }
        }

        with self.assertRaises(RuntimeError):
            make_sydent(test_config=config)
