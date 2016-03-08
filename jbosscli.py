#!/usr/bin/python

import json
import logging
import requests

log = logging.getLogger("jbosscli")

class Jbosscli(object):
    def __init__(self, controller, auth):
        self.controller = controller
        self.credentials = auth.split(":")
        self._read_attributes()

    def _read_attributes(self):
        result = self._invoke_cli('{"operation":"read-resource"}')

        result = result['result']

        self.management_major_version = result['management-major-version']
        self.management_micro_version = result['management-micro-version']
        self.management_minor_version = result['management-minor-version']
        self.name = result['name']
        self.product_name = result['product-name']
        self.product_version = result['product-version']
        self.release_codename = result['release-codename']
        self.release_version = result['release-version']

        result = self._invoke_cli('{"operation":"read-attribute", "name":"launch-type"}')

        self.domain = result['result'] == "DOMAIN"

    def _invoke_cli(self, command):
        url = "http://{0}/management".format(self.controller)
        headers = {"Content-type":"application/json"}

        log.debug("Requesting %s -> %s", self.controller, command)

        r = requests.post(url, data=command, headers=headers, auth=requests.auth.HTTPDigestAuth(self.credentials[0], self.credentials[1]))

        log.debug("Finished request with response code: %i", r.status_code)
        log.debug("Request body:\n%s", r.text)

        if (r.status_code >= 400 and not r.text):
            raise CliError("Request responded a {0} code".format(r.status_code))

        response = r.json()

        if 'outcome' not in response:
            raise CliError("Unknown error: {0}".format(r.text), response)

        if response['outcome'] != "success":
            raise CliError(response['failure-description'], response)

        return response

    def read_used_heap(self, host=None, server=None):
        command = '{{"operation":"read-resource", "include-runtime":"true", "address":[{0}"core-service", "platform-mbean", "type", "memory"]}}'
        address = ""

        if (host and server):
            address = '"host","{0}","server","{1}", '.format(host,server)

        command = command.format(address)

        result = self._invoke_cli(command)

        if result['outcome'] != "success":
            raise CliError(result)

        result = result['result']

        if 'heap-memory-usage' not in result:
            raise CliError(result)

        heap_memory_usage = result['heap-memory-usage']

        used_heap = heap_memory_usage['used']
        used_heap = float(used_heap)/1024/1024/1024

        max_heap = heap_memory_usage['max']
        max_heap = float(max_heap)/1024/1024/1024

        return (used_heap, max_heap)

    def restart(self, host=None, server=None):
        command = '{{"operation":{0}{1}}}'
        operation = ""
        address = ""

        if (host and server):
            address = ', "address": ["host", "{0}","server-config", "{1}"]'.format(host, server)
            operation = 'restart'
        else:
            operation = '"shutdown", "restart":"true"'

        command = command.format(operation, address)
        return self._invoke_cli(command)

    def list_domain_hosts(self):
        command = '{"operation":"read-children-names", "child-type":"host"}'
        result = self._invoke_cli(command)
        hosts = result['result']
        return hosts

    def list_servers(self, host):
        command = '{{"operation":"read-children-names", "child-type":"server", "address":["host","{0}"]}}'.format(host)
        result = self._invoke_cli(command)

        if result['outcome'] == "failed":
            return []
        else:
            servers = result['result']
            return servers

    def list_server_groups(self):
        command = '{"operation":"read-children-names","child-type":"server-group"}'

        result = self._invoke_cli(command)

        if result['outcome'] == "failed":
            return []
        else:
            groups = result['result']
            return groups

    def get_server_groups(self):
        result = self.list_server_groups()

        groups = []

        for item in result:
            deployments = self.get_deployments(item)
            group = ServerGroup(item, deployments)
            groups.append(group)

        return groups

    def get_deployments(self, server_group):
        command = '{{"operation":"read-children-resources", "child-type":"deployment", "address":["server-group","{0}"]}}'.format(server_group)
        result = self._invoke_cli(command)

        deployments = []

        if result['outcome'] != "failed":
            result = result['result']

            for item in result.values():
                deployment = Deployment(item['name'], item['runtime-name'], item['enabled'])
                deployments.append(deployment)

        return deployments

class CliError(Exception):
    def __init__(self, msg, raw=None):
        self.msg = msg
        self.raw = raw if raw else self.msg
    def __str__(self):
        return repr(self.msg)

class Deployment:
    def __init__(self, name, runtime_name, enabled=False, path=None):
        self.name = name
        self.runtime_name = runtime_name
        self.enabled = enabled
        self.path = path
    def __str__(self):
        return "{0} - {1} - {2}".format(self.name, self.runtime_name, 'enabled' if self.enabled else 'disabled')

class ServerGroup:
    def __init__(self, name, deployments):
        self.name = name
        self.deployments = deployments
    def __str__(self):
        return repr(self.name)
