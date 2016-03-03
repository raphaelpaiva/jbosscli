#!/usr/bin/python

import unittest
from mock import MagicMock

import jbosscli
from jbosscli import Jbosscli
from jbosscli import CliError

class TestJbosscli(unittest.TestCase):
    def test__invoke_cli_should_return_dict(self):
        expected_json_response = {"outcome" : "success"}
        mocked_response = Struct(status_code=200, text=None, json=MagicMock(return_value=expected_json_response))
        jbosscli.requests.post = MagicMock(return_value=mocked_response)

        actual_json_response = Jbosscli("", "a:b")._invoke_cli("")
        self.assertEqual(actual_json_response, expected_json_response)

    def test__invoke_cli_401_statuscode__should_raise_CliError(self):
        jbosscli.requests.post = MagicMock(return_value=Struct(status_code=401, text=None))
        with self.assertRaises(CliError) as cm:
            Jbosscli("", "a:b")._invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "Request responded a 401 code")

    def test__invoke_cli_outcome_failed_should_raise_CliError(self):
        json_response = {"outcome" : "failed", "failure-description" : "JBAS014792: Unknown attribute server-state", "rolled-back" : True}
        response = Struct(json=MagicMock(return_value=json_response),
                          status_code=200,
                          text='{"outcome" : "failed", "failure-description" : "JBAS014792: Unknown attribute server-state", "rolled-back" : true}'
        )

        jbosscli.requests.post = MagicMock(return_value=response)

        with self.assertRaises(CliError) as cm:
            Jbosscli("", "a:b")._invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "JBAS014792: Unknown attribute server-state")
        self.assertEqual(clierror.raw, json_response)

    def test__invoke_cli_ParserError_should_raise_CliError(self):
        response = Struct(status_code=500,
                          text="Parser error",
                          json=MagicMock(return_value="Parser error")
        )
        jbosscli.requests.post = MagicMock(return_value=response)

        with self.assertRaises(CliError) as cm:
            Jbosscli("", "a:b")._invoke_cli("")

        clierror = cm.exception
        self.assertEqual(clierror.msg, "Unknown error: Parser error")
        self.assertEqual(clierror.raw, "Parser error")

class Struct(object):
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

if __name__ == '__main__':
    unittest.main()
