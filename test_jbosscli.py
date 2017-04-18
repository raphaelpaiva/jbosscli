#!/usr/bin/python

import unittest
from mock import MagicMock
from mock import patch

import jbosscli
from jbosscli import Jbosscli
from jbosscli import CliError
from jbosscli import ServerError

class Struct(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

class TestJbosscli(unittest.TestCase):
    """
        Tests for the Jbosscli class
    """

    @patch(
        "jbosscli.requests.post",
        MagicMock(
            return_value=Struct(
                status_code=200,
                text=None,
                json=MagicMock(return_value={"outcome" : "success", "result": {}})
            )
        )
    )
    @patch("jbosscli.Jbosscli._fetch_controller_data", MagicMock())
    def test_invoke_cli_should_return_dict(self):
        expected_json_response = {}

        actual_json_response = Jbosscli("", "a:b").invoke_cli("")

        self.assertEqual(actual_json_response, expected_json_response)

    @patch("jbosscli.requests.post", MagicMock(return_value=Struct(status_code=401, text=None)))
    def test_invoke_cli_401_statuscode__should_raise_CliError(self):
        with self.assertRaises(ServerError) as configmanager:
            Jbosscli("", "a:b").invoke_cli("")

        clierror = configmanager.exception
        self.assertEqual(clierror.msg, "Request responded a 401 code")

    @patch(
        "jbosscli.requests.post",
        MagicMock(
            return_value=Struct(
                json=MagicMock(
                    return_value={
                        "outcome" : "failed",
                        "failure-description" : "JBAS014792: Unknown attribute server-state",
                        "rolled-back" : True
                    }
                ),
                status_code=200,
                text='{"outcome" : "failed", "failure-description" : \
                    "JBAS014792: Unknown attribute server-state", "rolled-back" : true}'
            )
        )
    )
    def test_invoke_cli_outcome_failed_should_raise_CliError(self):
        json_response = {
            "outcome" : "failed",
            "failure-description" : "JBAS014792: Unknown attribute server-state",
            "rolled-back" : True
        }

        with self.assertRaises(CliError) as cm:
            Jbosscli("", "a:b").invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "JBAS014792: Unknown attribute server-state")
        self.assertEqual(clierror.raw, json_response)

    @patch(
        "jbosscli.requests.post",
        MagicMock(
            return_value=Struct(
                status_code=500,
                text="Parser error",
                json=MagicMock(return_value="Parser error")
            )
        )
    )
    def test_invoke_cli_ParserError_should_raise_CliError(self):
        with self.assertRaises(CliError) as cm:
            Jbosscli("", "a:b").invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "Unknown error: Parser error")
        self.assertEqual(clierror.raw, "Parser error")

    @patch("jbosscli.requests.post", MagicMock(side_effect=Exception("OMG")))
    def test_invoke_cli_RequestError_should_raise_ServerError(self):
        with self.assertRaises(ServerError) as cm:
            Jbosscli("", "a:b").invoke_cli("")

        server_error = cm.exception
        self.assertEqual(server_error.msg, "Error requesting: OMG code")

    def test_fetch_controller_data_standalone(self):
        cli_response = {
            "name": "a name for the server",
            "product-name": "a product name",
            "product-version": "1.2.3",
            "release-codename": "Batman",
            "release-version": "3.2.1GA",
            "launch-type": "STANDALONE",
        }

        with patch("jbosscli.Jbosscli.invoke_cli", MagicMock(return_value=cli_response)):
            cli = Jbosscli("h:p", "u:p")
            self.assertEqual(cli.name, cli_response["name"])
            self.assertEqual(cli.release_codename, cli_response["release-codename"])
            self.assertEqual(len(cli.system_properties), 0)
            self.assertFalse(cli.domain)
            self.assertEqual(len(cli.hosts), 1)
            self.assertEqual(cli.hosts[0].name, "a name for the server - Standalone")

    def test_fetch_controller_data_WithSystemProperties(self):
        cli_response = {
            "name": "a name for the server",
            "product-name": "a product name",
            "product-version": "1.2.3",
            "release-codename": "Batman",
            "release-version": "3.2.1GA",
            "launch-type": "STANDALONE",
            "system-property": {
                "some.property" : {
                    "value": "someValue!"
                },
                "other.property" : {
                    "value": "otherValue!"
                }
            }
        }

        with patch("jbosscli.Jbosscli.invoke_cli", MagicMock(return_value=cli_response)):
            cli = Jbosscli("h:p", "u:p")
            self.assertEqual(cli.name, cli_response["name"])
            self.assertEqual(cli.release_codename, cli_response["release-codename"])
            self.assertFalse(cli.domain)
            self.assertEqual(len(cli.system_properties), 2)
            self.assertTrue(
                jbosscli.SystemProperty(
                    "some.property",
                    {"value": "someValue!"}
                ) in cli.system_properties
            )
            self.assertTrue(
                jbosscli.SystemProperty(
                    "other.property",
                    {"value": "otherValue!"}
                ) in cli.system_properties
            )
            self.assertEqual(len(cli.hosts), 1)

    @patch("jbosscli.Jbosscli._fetch_host_data", MagicMock())
    @patch("jbosscli.Jbosscli._fetch_server_group_data", MagicMock())
    def test_fetch_controller_data_domain(self):
        cli_response = {
            "name": "a name for the server",
            "product-name": "a product name",
            "product-version": "1.2.3",
            "release-codename": "Batman",
            "release-version": "3.2.1GA",
            "launch-type": "DOMAIN",
            "local-host-name": "some.host.com"
        }

        with patch("jbosscli.Jbosscli.invoke_cli", MagicMock(return_value=cli_response)):
            cli = Jbosscli("h:p", "u:p")
            self.assertEqual(cli.name, cli_response["name"])
            self.assertEqual(cli.release_codename, cli_response["release-codename"])
            self.assertTrue(cli.domain)
            self.assertEqual(cli.local_host_name, "some.host.com") 
            cli._fetch_host_data.assert_called_once_with()
            cli._fetch_server_group_data.assert_called_once_with()

if __name__ == '__main__':
    unittest.main()
