import os.path
from unittest.mock import patch

from twisted.trial import unittest

from tests.utils import make_sydent

from sydent.util.emailutils import sendEmail


class TestTemplate(unittest.TestCase):
    def setUp(self):
        # Create a new sydent
        config = {
            "general": {
                "templates.path": os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "res"
                ),
            },
        }
        self.sydent = make_sydent(test_config=config)

    def test_jinja_template(self):
        templateFile = self.sydent.get_branded_template("matrix", "invite_template.eml.j2",
                                                       ("email", "email.invite_template"))
        substitutions = {"sender_display_name":"Betty Boop"}

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            sendEmail(self.sydent, templateFile, "blah@nowhere.com", substitutions)

        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")

        self.assertIn("Betty Boop", email_contents)

    def test_jinja_escapes_invite(self):
        # test matrix invite template
        templateFile = self.sydent.get_branded_template("matrix", "invite_template.eml.j2",
                                                       ("email", "email.invite_template"))
        substitutions = {"room_id_for_url":"<malicious html>"}

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            sendEmail(self.sydent, templateFile, "blah@nowhere.com", substitutions)

        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertNotIn("<malicious html>", email_contents)

        # test vector-im invite template
        templateFile = self.sydent.get_branded_template("vector-im", "invite_template.eml.j2",
                                                       ("email", "email.invite_template"))
        substitutions = {"room_id_for_url":"<malicious html>"}

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            sendEmail(self.sydent, templateFile, "blah@nowhere.com", substitutions)

        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertNotIn("<malicious html>", email_contents)

    def test_jinja_escapes_verification(self):
        # test matrix template 
        templateFile = self.sydent.get_branded_template("matrix", "verification_template.eml.j2",
                                                       ("email", "email.verification_template"))
        substitutions = {"to":"<malicious html>"}

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            sendEmail(self.sydent, templateFile, "blah@nowhere.com", substitutions)

        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertNotIn("<malicious html>", email_contents)

        # test vector-im template
        templateFile = self.sydent.get_branded_template("vector-im", "verification_template.eml.j2",
                                                       ("email", "email.verification_template"))
        substitutions = {"to":"<malicious html>"}

        with patch("sydent.util.emailutils.smtplib") as smtplib:
            sendEmail(self.sydent, templateFile, "blah@nowhere.com", substitutions)

        smtp = smtplib.SMTP.return_value
        email_contents = smtp.sendmail.call_args[0][2].decode("utf-8")
        self.assertNotIn("<malicious html>", email_contents)