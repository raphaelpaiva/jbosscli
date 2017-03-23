# -*- coding: utf-8 -*-
"""
Jbosscli
"""

# apagar estes imports
import time

import json
import types
import requests

class Jbosscli(object):
    """Jbosscli"""
    def __init__(self, controller, auth):
        self.controller = controller
        self.credentials = auth.split(":")
        self.data = {}
        self._fetch_domain_data()

    def invoke_cli(self, command):
        """Calls Jboss management interface"""
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

        self.name = data["name"]
        self.product_name = data["product-name"]
        self.product_version = data["product-version"]
        self.release_codename = data["release-codename"]
        self.release_version = data["release-version"]

        self.domain = data["launch-type"] == "DOMAIN"
        if self.domain:
            self.local_host_name = data["local-host-name"]
            self.hosts = []
            self._fetch_host_data()
            self._fetch_server_group_data()
        else:
            standalone_data = data.copy()
            standalone_data["name"] = self.name + " - Standalone"
            standalone_data["master"] = True
            self.hosts = [Host(standalone_data, self)]

    def _fetch_host_data(self):
        hosts = self.invoke_cli({
            "operation": "read-children-resources",
            "child-type": "host",
            "recursive-depth": 1,
            "include-runtime": True
        })

        for key in hosts:
            host_data = hosts[key]
            self.hosts.append(
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
    """Generic class representing runtime errors in the server"""
    def __init__(self, msg, raw=None):
        super(CliError, self).__init__()
        self.msg = msg
        self.raw = raw if raw else self.msg

    def __str__(self):
        return repr(self.msg)

class ServerError(Exception):
    """Represents unrecoverable error in the communicating with the controller"""
    def __init__(self, msg, raw=None):
        super(ServerError, self).__init__()
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
        self.datasources = self._read_datasources()

    def _read_datasources(self):
        command = {
            "operation": "read-children-resources",
            "child-type": "data-source",
            "include-runtime": True,
            "recursive": True,
            "address": [
                "host", self.host.name,
                "server", self.name,
                "subsystem", "datasources"
            ]
        }

        resp = self.host.controller.invoke_cli(command)

        datasources = []
        for name, ds_data in resp.iteritems():
            ds_data["name"] = name
            datasources.append(DataSource(ds_data))

        return datasources

    def __str__(self):
        return self.name

    def __repr__(self):
        return "Instance('{0}', '{1}')".format(self.name, self.server_group_name)

    def read_memory_status(self):
        """Return the current heap and non-heap memory status"""
        return self.host.read_memory_status(self)

    def running(self):
        """Return True if status is \"STARTED\""""
        return self.status == "STARTED"

class DataSource(object):
    """Represents a datasource and some of its runtime metrics"""
    def __init__(self, data):
        self.name = data["name"]
        self.connection_url = data["connection-url"]
        self.jndi_name = data["jndi-name"]
        self.driver_class = data["driver-class"]
        self.driver_name = data["driver-name"]
        self.enabled = data["enabled"]
        self.jta = data["jta"]
        self.max_pool_size = data["max-pool-size"]
        self.min_pool_size = data["min-pool-size"]
        self.username = data["user-name"]

        pool_stats = data["statistics"]["pool"]

        self.active_connections = pool_stats["ActiveCount"]
        self.available_connections = pool_stats["AvailableCount"]
        self.created_connections = pool_stats["CreatedCount"]
        self.destroyed_connections = pool_stats["DestroyedCount"]
        self.in_use_connections = pool_stats["InUseCount"]
        self.max_used_connections = pool_stats["MaxUsedCount"]
        self.max_wait_time = pool_stats["MaxWaitTime"]

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.__str__()


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
    """ugly test function"""
    antes = time.time()
    cli = Jbosscli(controller, "jboss:jboss@123")
    depois = time.time()

    print "criar ", controller, depois - antes

    output_buffer = []
    antes = time.time()
    for host in cli.hosts:
        if cli.domain:
            for instance in host.instances:
                if instance.running():
                    output_buffer.append("{0} {1} {2}.".format(
                        host.name,
                        instance.name,
                        float(
                            instance.read_memory_status()["heap-memory-usage"]["used"]
                        ) / 1024.0 / 1024.0 / 1024.0
                    ))

                    output_buffer.append("datasources: {0}".format(instance.datasources))
                else:
                    output_buffer.append("{0} {1} not running.".format(host.name, instance.name))
        else:
            output_buffer.append(
                "standalone {0}".format(
                    host.read_memory_status()["heap-memory-usage"]["used"]
                )
            )
    depois = time.time()

    print "Memoria", controller, depois - antes
    print '\n'.join(output_buffer)

if __name__ == "__main__":
    test("serie1cabrio:9990")
    test("audia1:9990")
    test("vmpassijuw:9990")
    test("vmpassijuw:19990")
    test("atron:29990")
