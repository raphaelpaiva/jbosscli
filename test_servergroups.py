#!/usr/bin/python

import unittest
from mock import MagicMock
from mock import patch

import jbosscli
from jbosscli import Jbosscli

class TestJbosscli(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
