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
                json=MagicMock(return_value={"outcome" : "success"})
            )
        )
    )
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_invoke_cli_should_return_dict(self):
        expected_json_response = {"outcome" : "success"}

        actual_json_response = Jbosscli("", "a:b")._invoke_cli("")

        self.assertEqual(actual_json_response, expected_json_response)

    @patch("jbosscli.requests.post", MagicMock(return_value=Struct(status_code=401, text=None)))
    def test_invoke_cli_401_statuscode__should_raise_CliError(self):
        with self.assertRaises(ServerError) as configmanager:
            Jbosscli("", "a:b")._invoke_cli("")

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
            Jbosscli("", "a:b")._invoke_cli("")

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
            Jbosscli("", "a:b")._invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "Unknown error: Parser error")
        self.assertEqual(clierror.raw, "Parser error")

    @patch("jbosscli.requests.post", MagicMock(side_effect=Exception("OMG")))
    def test_invoke_cli_RequestError_should_raise_ServerError(self):
        with self.assertRaises(ServerError) as cm:
            Jbosscli("", "a:b")._invoke_cli("")

        server_error = cm.exception
        self.assertEqual(server_error.msg, "Error requesting: OMG code")

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_server_groups_standalone_should_return_empty_list(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        groups = controller.get_server_groups()

        self.assertEqual(len(groups), 0)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_list_server_groups_standalone_should_return_empty_list(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        groups = controller.list_server_groups()

        self.assertEqual(len(groups), 0)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_standalone_should_not_include_path_in_command(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.get_assigned_deployments()

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"read-children-resources", "child-type":"deployment"}')

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_domain_should_include_path_in_command(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True

        group = jbosscli.ServerGroup("test-server-group", [])

        controller.get_assigned_deployments(group)

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"read-children-resources", "child-type":"deployment", "address":["server-group","test-server-group"]}')

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_list_datasources_standalone(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.list_datasources()

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"read-children-resources","child-type":"data-source","address":["subsystem","datasources"]}')

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_list_datasources_domain(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True
        controller.instances = [jbosscli.ServerInstance('server-name','host-name')]

        controller.list_datasources()

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"read-children-resources","child-type":"data-source","address":["host","host-name","server","server-name","subsystem","datasources"]}')

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_flush_idle_connections_standalone(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.flush_idle_connections("test-ds", None)

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"flush-idle-connection-in-pool","address":["subsystem","datasources","data-source","test-ds"]}')

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_flush_idle_connections_domain(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True
        controller.instances = [jbosscli.ServerInstance('server-name','host-name')]

        controller.flush_idle_connections("test-ds", controller.instances[0])

        jbosscli.Jbosscli._invoke_cli.assert_called_with('{"operation":"flush-idle-connection-in-pool","address":["host","host-name","server","server-name","subsystem","datasources","data-source","test-ds"]}')

if __name__ == '__main__':
    unittest.main()
