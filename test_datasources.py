#!/usr/bin/python

import unittest
from mock import MagicMock
from mock import patch

import jbosscli
from jbosscli import Jbosscli

class TestJbosscli(unittest.TestCase):
    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_list_datasources_standalone(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.list_datasources()

        jbosscli.Jbosscli._invoke_cli.assert_called_with({
            'operation': 'read-children-resources',
            'child-type': 'data-source',
            'address': ['subsystem','datasources']
        })

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_list_datasources_domain(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True
        controller.instances = [jbosscli.ServerInstance('server-name','host-name')]

        controller.list_datasources()

        jbosscli.Jbosscli._invoke_cli.assert_called_with({
            "operation": "read-children-resources",
            "child-type": "data-source",
            "address": [
                "host", "host-name",
                "server", "server-name",
                "subsystem", "datasources"
            ]})

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_flush_idle_connections_standalone(self):
        controller = Jbosscli("", "a:b")
        controller.domain = False

        controller.flush_idle_connections("test-ds", None)

        jbosscli.Jbosscli._invoke_cli.assert_called_with({
            "operation": "flush-idle-connection-in-pool", 
            "address": [
                "subsystem", "datasources",
                "data-source", "test-ds"
            ]
        })

    @patch("jbosscli.Jbosscli._read_attributes", MagicMock())
    @patch("jbosscli.Jbosscli._invoke_cli", MagicMock())
    def test_flush_idle_connections_domain(self):
        controller = Jbosscli("", "a:b")
        controller.domain = True
        controller.instances = [jbosscli.ServerInstance('server-name','host-name')]

        controller.flush_idle_connections("test-ds", controller.instances[0])

        jbosscli.Jbosscli._invoke_cli.assert_called_with({
            "operation": "flush-idle-connection-in-pool",
            "address": [
                "host", "host-name",
                "server", "server-name",
                "subsystem", "datasources",
                "data-source", "test-ds"
            ]
        })

if __name__ == '__main__':
    unittest.main()
