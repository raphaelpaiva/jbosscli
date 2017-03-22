# -*- coding: utf-8 -*-
"""
Jbosscli
"""

import json
import types
import requests


# apagar estes imports
import time

class Jbosscli(object):
    """Jbosscli"""
    def __init__(self, controller, auth):
        self.controller = controller
        self.credentials = auth.split(":")
        self.data = {}
        self._fetch_domain_data()

    def invoke_cli(self, command):
        url = "http://{0}/management".format(self.controller)
        headers = {"Content-type": "application/json"}

        data = command if isinstance(command, types.StringType) else json.dumps(command)

        try:
            req = requests.post(
                url,
                data=data,
                headers=headers,
                auth=requests.auth.HTTPDigestAuth(
                    self.credentials[0], self.credentials[1]
                )
            )

        except Exception as ex:
            raise ServerError(
                "Error requesting: {0} code".format(str(ex))
            )

        if req.status_code >= 400 and not req.text:
            raise ServerError(
                "Request responded a {0} code".format(req.status_code)
            )

        response = req.json()

        if 'outcome' not in response:
            raise CliError("Unknown error: {0}".format(req.text), response)

        if response['outcome'] != "success":
            raise CliError(response['failure-description'], response)

        return response['result']

    def _fetch_domain_data(self):
        data = self.invoke_cli({
            "operation": "read-resource",
            "include-runtime": "true"
        })

        self.data["name"] = data["name"]
        self.data["product-name"] = data["product-name"]
        self.data["product-version"] = data["product-version"]
        self.data["release-codename"] = data["release-codename"]
        self.data["release-version"] = data["release-version"]

        self.domain = data["launch-type"] == "DOMAIN"
        if self.domain:
            self.data["local-host-name"] = data["local-host-name"]
            self.data["host"] = []
            self._fetch_host_data()
            self._fetch_server_group_data()
        else:
            standalone_data = self.data.copy()
            standalone_data["name"] = self.data["name"] + " - Standalone"
            standalone_data["master"] = True
            self.data["host"] = [Host(standalone_data, self)]

    def _fetch_host_data(self):
        hosts = self.invoke_cli({
            "operation": "read-children-resources",
            "child-type": "host",
            "recursive-depth": 1,
            "include-runtime": True
        })

        for key in hosts:
            host_data = hosts[key]
            self.data["host"].append(
                Host(host_data, controller=self)
            )

    def _fetch_server_group_data(self):

        data = self.invoke_cli({
            "operation": "read-children-resources",
            "child-type": "server-group",
            "recursive": True
        })

        server_groups = {}
        for key in data:
            group = data[key]
            group["name"] = key

            server_groups[key] = ServerGroup(group)


        self.data["server-groups"] = server_groups

class CliError(Exception):
    """CliError"""
    def __init__(self, msg, raw=None):
        self.msg = msg
        self.raw = raw if raw else self.msg

    def __str__(self):
        return repr(self.msg)


# @description When err na communicating with Domain ctrl or server standalone
class ServerError(Exception):
    def __init__(self, msg, raw=None):
        self.msg = msg
        self.raw = raw if raw else self.msg

    def __str__(self):
        return repr(self.msg)

class Host(object):
    """Represents a host, a container of server instances."""
    def __init__(self, data, controller=None):
        self.name = data["name"]
        self.product_name = data["product-name"]
        self.product_version = data["product-version"]
        self.release_codename = data["release-codename"]
        self.release_version = data["release-version"]
        self.master = data["master"]
        self.status = data["host-state"] if "host-state" in data else None
        self.controller = controller

        if not self.master:
            self.instances = [
                Instance(i, parent_host=self)
                for i in data["server-config"].values()
            ]
        else:
            self.instances = []

    def read_memory_status(self, instance=None):
        """
        returns a map with the memory state of the host or instance, if provided
        """

        command = {
            "operation": "read-resource",
            "include-runtime": "true",
            "address": [
                "core-service",
                "platform-mbean",
                "type",
                "memory"
            ]
        }

        if instance:
            command["address"] = ["host", self.name, "server", instance.name] + command["address"]

        return self.controller.invoke_cli(command)

class Instance(object):
    """Represents a server instance with runtime information"""
    def __init__(self, data, parent_host=None):
        self.name = data["name"]
        self.server_group_name = data["group"]
        self.status = data["status"]
        self.host = parent_host

    def __str__(self):
        return self.name

    def __repr__(self):
        return "Instance('{0}', '{1}')".format(self.name, self.server_group_name)

    def read_memory_status(self):
        """Return the current heap and non-heap memory status"""
        return self.host.read_memory_status(self)

    def running(self):
        return self.status == "STARTED"

class ServerGroup(object):
    """Represents a server group configuration"""
    def __init__(self, data):
        self.name = data["name"]
        self.profile = data["profile"]
        self.socket_binding_group = data["socket-binding-group"]
        self.socket_binding_port_offset = data["socket-binding-port-offset"]

        self.deployments = [Deployment(d) for d in data["deployment"].values()]

class Deployment(object):
    """Represents a Deployment in the server, enabled or not"""
    def __init__(self, data):
        self.name = data["name"]
        self.runtime_name = data["runtime-name"]
        self.enabled = data["enabled"]

    def __str__(self):
        return "{0} - {1} - {2}".format(
            self.name,
            self.runtime_name,
            'enabled' if self.enabled else 'disabled'
        )
    def __eq__(self, other):
        return self.name == other.name and \
        self.runtime_name == other.runtime_name and \
        self.enabled == other.enabled

## -- ##

def test(controller):
    antes = time.time()
    CLI = Jbosscli(controller, "jboss:jboss@123")
    depois = time.time()

    print "criar ", controller, depois - antes

    buffer = []
    antes = time.time()
    for host in CLI.data["host"]:
        if CLI.domain:
            for instance in host.instances:
                if instance.running():
                    buffer.append("{0} {1} {2}.".format(
                        host.name,
                        instance.name,
                        float(instance.read_memory_status()["heap-memory-usage"]["used"]) / 1024.0 / 1024.0 / 1024.0
                    ))
                else:
                    buffer.append("{0} {1} not running.".format(host.name, instance.name))
        else:
            buffer.append("standalone {0}".format(host.read_memory_status()["heap-memory-usage"]["used"]))
    depois = time.time()

    print "Memoria", controller, depois - antes
    #print '\n'.join(buffer)

if __name__ == "__main__":
    test("serie1cabrio:9990")
    test("audia1:9990")
    test("vmpassijuw:9990")
    test("vmpassijuw:19990")
    test("atron:29990")
