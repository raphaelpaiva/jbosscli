import unittest
from mock import MagicMock
from mock import patch

import jbosscli
from jbosscli import Jbosscli
from jbosscli import ServerGroup
from jbosscli import Deployment

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

if __name__ == '__main__':
    unittest.main()
