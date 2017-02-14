#!/usr/bin/python

import unittest
from mock import MagicMock
from mock import patch

import jbosscli
from jbosscli import Jbosscli
from jbosscli import ServerGroup
from jbosscli import Deployment

class TestJbosscli(unittest.TestCase):

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_list_servers_groups(self):
        cli = Jbosscli("host:port", "a:b")

        cli.domain = True

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": [
                    "server-group1",
                    "other-server-group"
                ]
            }
        )

        groups = cli.list_server_groups()

        cli._invoke_cli.assert_called_with({
            "operation": "read-children-names",
            "child-type": "server-group"
        })

        self.assertEqual(groups, ["server-group1", "other-server-group"])

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_servers_groups_two_groups_no_deployments_should_return_sv_group_list(self):
        cli = Jbosscli("host:port", "a:b")

        cli.domain = True

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": [
                    "server-group1",
                    "other-server-group"
                ]
            }
        )
        cli.get_assigned_deployments = MagicMock(
            return_value=[]
        )

        expected_sv_groups = [
            ServerGroup("server-group1", []),
            ServerGroup("other-server-group", [])
        ]

        groups = cli.get_server_groups()

        self.assertEqual(groups, expected_sv_groups)

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_servers_groups_two_groups_with_deployments_should_return_sv_group_list(self):
        cli = Jbosscli("host:port", "a:b")

        cli.domain = True

        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": [
                    "server-group1",
                    "other-server-group"
                ]
            }
        )
        cli.get_assigned_deployments = MagicMock(
            return_value=[
                Deployment("abce-version", "abce.war", enabled=True),
                Deployment("ecba-version", "ecba.war", enabled=False)
            ]
        )

        expected_sv_groups = [
            ServerGroup(
                "server-group1", [
                    Deployment("abce-version", "abce.war", enabled=True),
                    Deployment("ecba-version", "ecba.war", enabled=False)
                ]
            ),

            ServerGroup("other-server-group",  [
                    Deployment("abce-version", "abce.war", enabled=True),
                    Deployment("ecba-version", "ecba.war", enabled=False)
                ]
            )
        ]

        groups = cli.get_server_groups()

        self.assertEqual(groups, expected_sv_groups)

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_servers_groups_standalone_should_return_empty_list(self):
        cli = Jbosscli("host:port", "a:b")

        cli.domain = False

        groups = cli.get_server_groups()

        self.assertEqual(len(groups), 0)
    
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_server_groups_standalone_should_return_empty_list(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        groups = controller.get_server_groups()

        self.assertEqual(len(groups), 0)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_standalone_should_not_include_path_in_command(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.get_assigned_deployments()

        jbosscli.Jbosscli._invoke_cli.assert_called_with({"operation":"read-children-resources", "child-type":"deployment"})

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_domain_should_include_path_in_command(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True

        group = jbosscli.ServerGroup("test-server-group", [])

        controller.get_assigned_deployments(group)

        jbosscli.Jbosscli._invoke_cli.assert_called_with({"operation":"read-children-resources", "child-type":"deployment", "address":["server-group","test-server-group"]})


    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_domain_should_return_deployments(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True

        controller._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": {
                    "abce-version": {
                        "enabled": True,
                        "name": "abce-version",
                        "runtime-name": "abce.war"
                    },
                    "ecba-version": {
                        "enabled": False,
                        "name": "ecba-version",
                        "runtime-name": "ecba.war"
                    }

                }
            }
        )

        group = jbosscli.ServerGroup("test-server-group", [])

        expected_deployments = [
            Deployment("abce-version", "abce.war", enabled=True, server_group=group),
            Deployment("ecba-version", "ecba.war", enabled=False, server_group=group)
        ]

        actual_deployments = controller.get_assigned_deployments(group)

        self.assertEqual(actual_deployments, expected_deployments)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_get_assigned_deployments_domain_no_server_group_should_return_all_deployments(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True

        controller._get_all_assigned_deployments = MagicMock()

        controller.get_assigned_deployments()

        controller._get_all_assigned_deployments.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
