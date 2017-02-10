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

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_read_used_heap_standalone(self):

        cli = Jbosscli("host:port", "a:b")
        
        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": {
                    "heap-memory-usage": {
                        "used": "1024",
                        "max": "2048"
                    }
                }
            }
        )
        result = cli.read_used_heap()

        cli._invoke_cli.assert_called_with({
            "operation": "read-resource",
            "include-runtime": "true",
            "address": [
                "core-service",
                "platform-mbean",
                "type",
                "memory"
            ]
        })

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 0.00000095367431640625)
        self.assertEqual(result[1], 0.0000019073486328125)

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_read_used_heap_domain_should_add_instance_address(self):

        cli = Jbosscli("host:port", "a:b")
        
        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": {
                    "heap-memory-usage": {
                        "used": "1024",
                        "max": "2048"
                    }
                }
            }
        )
        result = cli.read_used_heap(host="somehost", server="someinstance")

        cli._invoke_cli.assert_called_with({
            "operation": "read-resource",
            "include-runtime": "true",
            "address": [
                "host",
                "somehost",
                "server",
                "someinstance",
                "core-service",
                "platform-mbean",
                "type",
                "memory"
            ]
        })

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], 0.00000095367431640625)
        self.assertEqual(result[1], 0.0000019073486328125)

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_read_used_heap_not_successful_should_raise_CliError(self):

        error_response = {
            "outcome": "failure",
            "result": {
                "error": "Some Error String."
            }
        }

        cli = Jbosscli("host:port", "a:b")
        
        cli._invoke_cli = MagicMock(
            return_value=error_response
        )

        with self.assertRaises(CliError) as cm:
            cli.read_used_heap()

        cli._invoke_cli.assert_called_with({
            "operation": "read-resource",
            "include-runtime": "true",
            "address": [
                "core-service",
                "platform-mbean",
                "type",
                "memory"
            ]
        })

        cli_error = cm.exception
        self.assertEqual(cli_error.msg, error_response)

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_read_used_heap_successful_no_heap_information_should_raise_CliError(self):

        error_response = {
            "outcome": "success",
            "result": {
                "error": "Some Error String."
            }
        }

        cli = Jbosscli("host:port", "a:b")
        
        cli._invoke_cli = MagicMock(
            return_value=error_response
        )

        with self.assertRaises(CliError) as cm:
            cli.read_used_heap()

        cli._invoke_cli.assert_called_with({
            "operation": "read-resource",
            "include-runtime": "true",
            "address": [
                "core-service",
                "platform-mbean",
                "type",
                "memory"
            ]
        })

        cli_error = cm.exception
        self.assertEqual(cli_error.msg, error_response['result'])

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_restart_standalone(self):
        cli = Jbosscli("host:port", "a:b")


        cli._invoke_cli = MagicMock(
            return_value={"outcome": "success"}
        )

        cli.restart()

        cli._invoke_cli.assert_called_with({
            "operation": "shutdown",
            "restart": "true"
        })

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_restart_domain(self):
        cli = Jbosscli("host:port", "a:b")

        cli._invoke_cli = MagicMock(
            return_value={"outcome": "success"}
        )

        cli.restart(host="somehost", server="someinstance")

        cli._invoke_cli.assert_called_with({
            "operation": "restart",
            "address": [
                "host",
                "somehost",
                "server",
                "someinstance"
            ]
        })

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_list_domain_hosts(self):
        cli = Jbosscli("host:port", "a:b")

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": [
                    "host1",
                    "host2"
                ]
            }
        )

        hosts = cli.list_domain_hosts()

        cli._invoke_cli.assert_called_with({
            "operation": "read-children-names",
            "child-type": "host"
        })

        self.assertEqual(hosts, ["host1", "host2"])

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_list_servers_success(self):
        cli = Jbosscli("host:port", "a:b")

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": [
                    "instance1",
                    "instance2"
                ]
            }
        )

        hosts = cli.list_servers("somehost")

        cli._invoke_cli.assert_called_with({
            "operation": "read-children-names",
            "child-type": "server",
            "address": [
                "host", "somehost"
            ]
        })

        self.assertEqual(hosts, ["instance1", "instance2"])

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_list_servers_failure(self):
        cli = Jbosscli("host:port", "a:b")

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "failed",
                "failure-description": ":("
            }
        )

        hosts = cli.list_servers("somehost")

        cli._invoke_cli.assert_called_with({
            "operation": "read-children-names",
            "child-type": "server",
            "address": [
                "host", "somehost"
            ]
        })

        self.assertEqual(len(hosts), 0)


if __name__ == '__main__':
    unittest.main()
