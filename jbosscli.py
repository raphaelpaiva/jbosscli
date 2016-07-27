#!/usr/bin/python

import json
import logging
import requests

log = logging.getLogger("jbosscli")
log.addHandler(logging.NullHandler())

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

        launch_type_result = self._invoke_cli('{"operation":"read-attribute", "name":"launch-type"}')
        self.domain = launch_type_result['result'] == "DOMAIN"

        if (self.domain):
            self.profiles = list(result['profile'].keys())
            self.instances = self._discover_instances()
        else:
            self.profiles = ["default"]

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
            operation = '"restart"'
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
        if (not self.domain):
            return []

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
            deployments = self.get_assigned_deployments(item)
            group = ServerGroup(item, deployments)
            groups.append(group)

        return groups

    def get_assigned_deployments(self, server_group=None):
        if (self.domain and not server_group):
            return self._get_all_assigned_deployments()

        command = '{{"operation":"read-children-resources", "child-type":"deployment"{0}}}'

        server_group_name = server_group.name if (server_group.__class__.__name__ is 'ServerGroup') else server_group

        if (self.domain):
            command = command.format(', "address":["server-group","{0}"]'.format(server_group_name))
        else:
            command = command.format("")

        result = self._invoke_cli(command)

        deployments = []

        if result['outcome'] != "failed":
            result = result['result']

            for item in result.values():
                deployment = Deployment(item['name'], item['runtime-name'], item['enabled'], server_group=server_group)
                deployments.append(deployment)

        return deployments

    def _get_all_assigned_deployments(self):
        groups = self.get_server_groups()
        deployments = []

        for group in groups:
            deployments.extend(group.deployments)

        return deployments


    def get_deployments(self):
        assigned = self.get_assigned_deployments()

        if not self.domain:
            return assigned
        else:
            all_deployments = self._get_all_deployments()

            enabled = {}
            for a in assigned:
                enabled[a.name] = (a.enabled, a.server_group)

            for d in all_deployments:
                if d.name in enabled:
                    d.enabled, d.server_group = enabled[d.name]

            return all_deployments

    def _get_all_deployments(self):
        response = self._invoke_cli('{"operation":"read-children-resources", "child-type":"deployment"}')
        result = response['result']

        deployments = []

        for item in result.values():
            deployment = Deployment(item['name'], item['runtime-name'])
            deployments.append(deployment)

        return deployments

    def list_datasources(self):
        command = '{{"operation":"read-children-resources","child-type":"data-source","address":[{0}"subsystem","datasources"]}}'

        if(not self.domain):
            command = command.format("")
            response = self._invoke_cli(command)
            datasources = response['result']

            enabled_datasources = self._filter_enabled_datasources(datasources)

            return {ServerInstance('standalone', self.controller): enabled_datasources}
        else:
            datasources_by_server_instance = {}
            for instance in self.instances:
                address = '"host","{0}","server","{1}",'.format(instance.host, instance.name)
                response = self._invoke_cli(command.format(address))
                datasources = response['result']
                datasources_by_server_instance[instance] = self._filter_enabled_datasources(datasources)

            return datasources_by_server_instance

    def _filter_enabled_datasources(self, datasources):
        enabled_datasources = {}

        for key, value in datasources.iteritems():
            if value['enabled']:
                enabled_datasources[key] = value

        return enabled_datasources

    def read_datasource_statistics(self, datasource, server_instance=None):
        address = ""

        if (self.domain):
            address = '"host","{0}","server","{1}",'.format(server_instance.host, server_instance.name)

        command = '{{"operation":"read-resource","include-runtime":"true","address":[{0}"subsystem","datasources","data-source","{1}","statistics","pool"]}}'.format(address, datasource)

        response = self._invoke_cli(command)
        return response['result']

    def _discover_instances(self):
        hosts = self.list_domain_hosts()
        log.info("Found %i hosts: %s", len(hosts), ", ".join(hosts))

        instances = []
        for host in hosts:
            servers = []
            try:
                servers = self.list_servers(host)
            except CliError as e:
                log.warning("No servers found for host {0}. Reason: {1}".format(host, e.msg))
            for server in servers:
                instances.append(ServerInstance(server, host))

        log.info("Found %i instances.", len(instances))

        return instances

    def flush_idle_connections(self, ds, instance):
        command = '{{"operation":"flush-idle-connection-in-pool","address":[{0}"subsystem","datasources","data-source","{1}"]}}'
        target = ""

        if (self.domain):
            target = '"host","{0}","server","{1}",'.format(instance.host, instance.name)

        command = command.format(target, ds)

        return self._invoke_cli(command)

    def fecth_context_root(self, deployment):
        if self.domain:
            instances = self.instances
            for instance in instances:
                context_root = ""
                try:
                    command = '{{"operation":"read-attribute","name":"context-root","address":["host","{0}","server","{1}","deployment","{2}","subsystem","web"]}}'
                    command = command.format(instance.host, instance.name, deployment.name)
                    result = self._invoke_cli(command)
                    context_root = result['result']
                except:
                    pass
                if context_root:
                    return context_root
            return None
        else:
            command = '{{"operation":"read-attribute","name":"context-root","address":["deployment","{0}","subsystem","web"]}}'
            command = command.format(deployment.name)
            result = self._invoke_cli(command)
            return result['result']

class CliError(Exception):
    def __init__(self, msg, raw=None):
        self.msg = msg
        self.raw = raw if raw else self.msg
    def __str__(self):
        return repr(self.msg)

class Deployment:
    def __init__(self, name, runtime_name, enabled=False, path=None, server_group=None):
        self.name = name
        self.runtime_name = runtime_name
        self.enabled = enabled
        self.path = path
        self.server_group = server_group
    def __str__(self):
        return "{0} - {1} - {2}{3}".format(self.name, self.runtime_name, 'enabled' if self.enabled else 'disabled', " - " + self.server_group if self.server_group else "")

class ServerGroup:
    def __init__(self, name, deployments):
        self.name = name
        self.deployments = deployments
    def __str__(self):
        return self.name

class ServerInstance:
    def __init__(self, name, host):
        self.name = name
        self.host = host
    def __str__(self):
        return "[{0}, {1}]".format(self.host, self.name)
