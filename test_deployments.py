import unittest
from mock import MagicMock
from mock import patch
from mock import call

import jbosscli
from jbosscli import Jbosscli
from jbosscli import ServerGroup
from jbosscli import Deployment
from jbosscli import ServerInstance
from jbosscli import CliError

class TestJbosscli(unittest.TestCase):

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

    @patch("jbosscli.requests.post", MagicMock())
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_all_assigned_deployments(self):
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

        cli.get_server_groups = MagicMock(
            return_value=[
                ServerGroup("server-group1", [
                    Deployment("abce-version", "abce.war", enabled=True),
                    Deployment("ecba-version", "ecba.war", enabled=False)
                ]),
                ServerGroup("server-group2", [
                    Deployment("abce-version2", "abce.war", enabled=True),
                    Deployment("ecba-version2", "ecba.war", enabled=False)
                ])
            ]
        )

        deployments = cli._get_all_assigned_deployments()

        expected_deployments = [
            Deployment("abce-version", "abce.war", enabled=True),
            Deployment("ecba-version", "ecba.war", enabled=False),
            Deployment("abce-version2", "abce.war", enabled=True),
            Deployment("ecba-version2", "ecba.war", enabled=False)
        ]

        self.assertEqual(deployments, expected_deployments)

    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock(return_value={
        "outcome": "success",
        "result": {
            "name-version": {
                "content": {},
                "name": "name-version",
                "runtime-name": "name.war"
            },
            "othername-version": {
                "content": {},
                "name": "othername-version",
                "runtime-name": "othername.war"
            }
        }
    }))
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_get_all_deployments(self):
        cli = Jbosscli("a:b", "pass")

        deployments = cli._get_all_deployments()

        cli._invoke_cli.assert_called_with({
            "operation": "read-children-resources",
            "child-type": "deployment"
        })

        expected_deployments = [
            Deployment("name-version", "name.war"),
            Deployment("othername-version", "othername.war")
        ]

        deployments.sort(key=lambda d: d.name)

        self.assertEqual(deployments, expected_deployments)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_fetch_context_root_domain_single_instance(self):
        cli = Jbosscli("a:b", "pass")
        cli.domain = True
        cli.instances = [ServerInstance("someinstance", "somehost")]
        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": "/abcd"
            })

        deployment = Deployment("abcd-version", "abcd.war")
        context_root = cli.fecth_context_root(deployment)

        cli._invoke_cli.assert_called_once_with({
            "operation": "read-attribute",
            "name": "context-root",
            "address": [
                "host", "somehost",
                "server", "someinstance",
                "deployment", "abcd-version",
                "subsystem", "web"
            ]
        })

        self.assertEqual(context_root, "/abcd")

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_fetch_context_root_domain_two_instances_should_search_both(self):
        cli = Jbosscli("a:b", "pass")
        cli.domain = True
        cli.instances = [
            ServerInstance("someinstance", "somehost"),
            ServerInstance("otherinstance", "somehost")
        ]
        cli._invoke_cli = MagicMock(
            side_effect=[
                CliError("Boom!"),
                {
                    "outcome": "success",
                    "result": "/abcd"
                }
            ])

        deployment = Deployment("abcd-version", "abcd.war")
        context_root = cli.fecth_context_root(deployment)

        calls = [
            call({
                "operation": "read-attribute",
                "name": "context-root",
                "address": [
                    "host", "somehost",
                    "server", "someinstance",
                    "deployment", "abcd-version",
                    "subsystem", "web"
                ]
            }),
            call({
                "operation": "read-attribute",
                "name": "context-root",
                "address": [
                    "host", "somehost",
                    "server", "otherinstance",
                    "deployment", "abcd-version",
                    "subsystem", "web"
                ]
            })
        ]

        cli._invoke_cli.assert_has_calls(calls)

        self.assertEqual(context_root, "/abcd")

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_fetch_context_root_domain_two_empty_instances_should_search_both(self):
        cli = Jbosscli("a:b", "pass")
        cli.domain = True
        cli.instances = [
            ServerInstance("someinstance", "somehost"),
            ServerInstance("otherinstance", "somehost")
        ]
        cli._invoke_cli = MagicMock(
            side_effect=[
                CliError("Boom!"),
                CliError("Boom!")
            ])

        deployment = Deployment("abcd-version", "abcd.war")
        context_root = cli.fecth_context_root(deployment)

        calls = [
            call({
                "operation": "read-attribute",
                "name": "context-root",
                "address": [
                    "host", "somehost",
                    "server", "someinstance",
                    "deployment", "abcd-version",
                    "subsystem", "web"
                ]
            }),
            call({
                "operation": "read-attribute",
                "name": "context-root",
                "address": [
                    "host", "somehost",
                    "server", "otherinstance",
                    "deployment", "abcd-version",
                    "subsystem", "web"
                ]
            })
        ]

        cli._invoke_cli.assert_has_calls(calls)

        self.assertIsNone(context_root)

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_fetch_context_root_standalone(self):
        cli = Jbosscli("a:b", "pass")
        cli.domain = False
        cli._invoke_cli = MagicMock(
            return_value={
                "outcome": "success",
                "result": "/abcd"
            }
        )

        deployment = Deployment("abcd-version", "abcd.war")
        context_root = cli.fecth_context_root(deployment)

        cli._invoke_cli.assert_called_once_with({
            "operation": "read-attribute",
            "name": "context-root",
            "address": [
                "deployment", "abcd-version",
                "subsystem", "web"
            ]
        })

        self.assertEqual(context_root, "/abcd")

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    def test_fetch_context_root_standalone_inexisting_deployment_should_return_None(self):
        cli = Jbosscli("a:b", "pass")
        cli.domain = False
        cli._invoke_cli = MagicMock(
            side_effect=CliError('Boom!')
        )

        deployment = Deployment("abcd-version", "abcd.war")
        context_root = cli.fecth_context_root(deployment)

        cli._invoke_cli.assert_called_once_with({
            "operation": "read-attribute",
            "name": "context-root",
            "address": [
                "deployment", "abcd-version",
                "subsystem", "web"
            ]
        })

        self.assertIsNone(context_root)

if __name__ == '__main__':
    unittest.main()
