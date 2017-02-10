#!/usr/bin/python

import json
import logging
import requests
import copy
import re


log = logging.getLogger("jbosscli")
log.addHandler(logging.NullHandler())


class Jbosscli(object):
    def __init__(self, controller, auth):
        self.controller = controller
        self.credentials = auth.split(":")
        self._read_attributes()

    def _read_attributes(self): # pragma: no cover
        result = self._invoke_cli({"operation": "read-resource"})

        result = result['result']

        self.management_major_version = result['management-major-version']
        self.management_micro_version = result['management-micro-version']
        self.management_minor_version = result['management-minor-version']
        self.name = result['name']
        self.product_name = result['product-name']
        self.product_version = result['product-version']
        self.release_codename = result['release-codename']
        self.release_version = result['release-version']

        launch_type_result = self._invoke_cli(
            {"operation":"read-attribute", "name":"launch-type"}
        )
        self.domain = launch_type_result['result'] == "DOMAIN"

        if (self.domain):
            self.profiles = list(result['profile'].keys())
            self.instances = self._discover_instances()
        else:
            self.profiles = ["default"]

    def _invoke_cli(self, command):
        url = "http://{0}/management".format(self.controller)
        headers = {"Content-type": "application/json"}

        log.debug("Requesting %s -> %s", self.controller, command)

        try:
            r = requests.post(
                url,
                data=json.dumps(command),
                headers=headers,
                auth=requests.auth.HTTPDigestAuth(
                    self.credentials[0], self.credentials[1]
                )
            )

        except Exception as ex:
            raise ServerError(
                "Error requesting: {0} code".format(str(ex))
            )

        log.debug("Finished request with response code: %i", r.status_code)
        log.debug("Request body:\n%s", r.text)

        if (r.status_code >= 400 and not r.text):
            raise ServerError(
                "Request responded a {0} code".format(r.status_code)
            )

        response = r.json()

        if 'outcome' not in response:
            raise CliError("Unknown error: {0}".format(r.text), response)

        if response['outcome'] != "success":
            raise CliError(response['failure-description'], response)

        return response

    def read_used_heap(self, host=None, server=None):
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

        if (host and server):
            command["address"] = ["host", host, "server", server] + command["address"]

        result = self._invoke_cli(command)

        if result['outcome'] != "success":
            raise CliError(result)

        result = result['result']

        if 'heap-memory-usage' not in result:
            raise CliError(result)

        heap_memory_usage = result['heap-memory-usage']

        used_heap = heap_memory_usage['used']
        used_heap = float(used_heap) / 1024 / 1024 / 1024

        max_heap = heap_memory_usage['max']
        max_heap = float(max_heap) / 1024 / 1024 / 1024

        return (used_heap, max_heap)

    def restart(self, host=None, server=None):
        command = '{{"operation":{0}{1}}}'
        operation = ""
        address = ""

        if (host and server):
            address = ', "address": ["host", "{0}","server-config", "{1}"]' \
                .format(host, server)

            operation = '"restart"'
        else:
            operation = '"shutdown", "restart":"true"'

        command = command.format(operation, address)
        return self._invoke_cli(command)

    def list_domain_hosts(self):
        command = {"operation":"read-children-names", "child-type":"host"}
        result = self._invoke_cli(command)
        hosts = result['result']
        return hosts

    def list_servers(self, host):
        command = {
            "operation": "read-children-names",
            "child-type": "server",
            "address": ["host", host]
        }

        result = self._invoke_cli(command)

        if result['outcome'] == "failed":
            return []
        else:
            servers = result['result']
            return servers

    def list_server_groups(self):
        if (not self.domain):
            return []

        command = {
            "operation": "read-children-names",
            "child-type": "server-group"
        }

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

        command = '{{"operation":"read-children-resources", \
"child-type":"deployment"{0}}}'

        server_group_name = server_group.name if (
            server_group.__class__.__name__ is 'ServerGroup'
        ) else server_group

        if (self.domain):
            command = command.format(
                ', "address":["server-group","{0}"]'.format(server_group_name)
            )
        else:
            command = command.format("")

        result = self._invoke_cli(command)

        deployments = []

        if result['outcome'] != "failed":
            result = result['result']

            for item in result.values():
                deployment = Deployment(
                    item['name'],
                    item['runtime-name'],
                    item['enabled'],
                    server_group=server_group
                )

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
        response = self._invoke_cli(
            '{"operation":"read-children-resources",\
            "child-type":"deployment"}'
        )
        result = response['result']

        deployments = []

        for item in result.values():
            deployment = Deployment(item['name'], item['runtime-name'])
            deployments.append(deployment)

        return deployments

    def list_datasources(self):
        command = '{{"operation":"read-children-resources",\
"child-type":"data-source","address":[{0}"subsystem","datasources"]}}'

        if (not self.domain):
            command = command.format("")
            response = self._invoke_cli(command)
            datasources = response['result']

            enabled_datasources = self._filter_enabled_datasources(datasources)

            return {
                ServerInstance('standalone', self.controller):
                    enabled_datasources
            }
        else:
            datasources_by_server_instance = {}
            for instance in self.instances:
                address = '"host","{0}","server","{1}",'.format(
                    instance.host,
                    instance.name
                )
                response = self._invoke_cli(command.format(address))
                datasources = response['result']
                datasources_by_server_instance[instance] = \
                    self._filter_enabled_datasources(datasources)

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
            address = '"host","{0}","server","{1}",'.format(
                server_instance.host, server_instance.name
            )

        command = '{{"operation":"read-resource","include-runtime":"true",\
            "address":[{0}"subsystem","datasources","data-source",\
            "{1}","statistics","pool"]}}'.format(address, datasource)

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
                log.warning(
                    "No servers found for host {0}. Reason: {1}".format(
                        host, e.msg
                    )
                )
            for server in servers:
                instances.append(ServerInstance(server, host))

        log.info("Found %i instances.", len(instances))

        return instances

    def flush_idle_connections(self, ds, instance):
        command = '{{"operation":"flush-idle-connection-in-pool",\
"address":[{0}"subsystem","datasources","data-source","{1}"]}}'
        target = ""

        if (self.domain):
            target = '"host","{0}","server","{1}",'.format(
                instance.host, instance.name
            )

        command = command.format(target, ds)
        return self._invoke_cli(command)

    def fecth_context_root(self, deployment):
        if self.domain:
            instances = self.instances
            for instance in instances:
                context_root = ""
                try:
                    command = '{{"operation":"read-attribute",\
                        "name":"context-root",\
                        "address":["host","{0}","server","{1}",\
                        "deployment","{2}","subsystem","web"]}}'
                    command = command.format(
                        instance.host, instance.name, deployment.name
                    )
                    result = self._invoke_cli(command)
                    context_root = result['result']
                except:
                    pass
                if context_root:
                    return context_root
            return None
        else:
            command = '{{"operation":"read-attribute","name":"context-root",\
            "address":["deployment","{0}","subsystem","web"]}}'
            command = command.format(deployment.name)
            result = self._invoke_cli(command)
            return result['result']

    def get_system_properties(self):
        result = self._invoke_cli(
            '{"operation":"read-children-resources","child-type":"system-property"}'
        )
        return result['result']

    def is_server_state_started(self, host=None, instance=None):
        """Inform if the server(instance) is started
        :author: Luiz Antonio

        :param host(str): Host name
        :param instance(str): Server (instance) name
        :return(bool): True if "STARTED" otherwise False.
        """
        try:
            cmdo = ''
            if self.domain:
                cmdo += '{"operation":"read-attribute","address":[{"host":"'
                cmdo += host
                cmdo += '"},{"server-config":"'
                cmdo += instance
                cmdo += '"}],"name":"status","json.pretty":1}'
            else:
                cmdo = '{"operation":"read-attribute","name":"status","json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"] == "STARTED"
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error is_server_state_started({0},{1}): {2} code".format(host, instance, str(ex))
            )

    def get_datasource_state(self, dtasrc, host=None, instance=None):
        """Get a datasource state
        :author: Luiz Antonio

        :param dtasrc(str): Datasource name.
        :param host(str): Host name.
        :param instance(str): Server (instance) name.
        :return: A state(str) of the data source given.
        """
        try:
            cmdo = ''
            if self.domain:
                cmdo += '{"operation":"test-connection-in-pool","address":[{"host":"'
                cmdo += host
                cmdo += '"},{"server":"'
                cmdo += instance
                cmdo += '"},{"subsystem":"datasources"},{"data-source":"'
                cmdo += dtasrc
                cmdo += '"}],"json.pretty":1}'
            else:
                cmdo += '{"operation":"test-connection-in-pool","address":[{"subsystem":"datasources"},{"data-source":"'
                cmdo += dtasrc
                cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"][0]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error get_datasource_state({0},{1},{2}): {3} code".format(dtasrc, host,instance, str(ex))
            )

    def list_all_profiles(self):
        """List all profiles
        :author: Luiz Antonio

        :return: List of profiles
        """
        try:
            cmdo = '{"operation":"read-children-names","child-type":"profile","address":[],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error get_datasource_state: {0} code".format(str(ex))
            )

    def list_datasources_of_profile(self, profile):
        """List datasources of a profile
        :author: Luiz Antonio

        :param profile: Profile name (str)
        :return: List of datasource names
        """
        try:
            cmdo = '{"operation":"read-children-names","child-type":"data-source","address":['
            cmdo += '{"profile":"'
            cmdo += profile
            cmdo += '"},{"subsystem":"datasources"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise cli_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
              "Error list_datasources_of_profile({0}): {1} code".format(profile, str(ex))
            )

    def get_profile_of_server_group(self, group):
        """Get the profile of a given server group

        :param sg: Server group name (str)
        :return: The name of the profile
        """
        try:
            cmdo = '{"operation":"read-attribute","name":"profile","address":['
            cmdo += '{"server-group":"'
            cmdo += group
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
              "Error get_profile_of_server_group({0}): {1} code".format(group, str(ex))
            )

    def list_server_groups_of_profile(self, profile):
        """List the server groups of a given profile
        :author: Luiz Antonio

        :param profile: Profile name (str)
        :return: A list of server groups of a profile
        """
        try:
            sgs = self.list_server_groups()
            lst = []
            for sg in sgs:
                pf = self.get_profile_of_server_group(sg)
                if pf == profile:
                    lst.append(sg)
            return lst
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error list_server_groups_of_profile({0}): {1} code".format(profile, str(ex))
            )

    def get_server_group_of_host_instance(self, host, instance):
        """Get the server group of a given server group
        :author: Luiz Antonio

        :param host: Host name (str)
        :instance: Server (instance) name
        :return: The name of the profile
        """
        try:
            cmdo = '{"operation":"read-attribute","name":"group","address":['
            cmdo += '{"host":"'
            cmdo += host
            cmdo += '"},{"server-config":"'
            cmdo += instance
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error get_data_source_state({0},{1}): {2} code".format(host, instance, str(ex))
            )

    def list_data_sources_states_of_host_instance(self, host, instance):
        """List states of a instance datasources
        :author: Luiz Antonio

        :param host: Host name (str)
        :param instance: Server (instance) name
        :return: A tuple (host, server (instance), datasource, state)
        """
        lst = []
        try:
            svg = self.get_server_group_of_host_instance(host, instance)
            prof = self.get_profile_of_server_group(svg)
            dts = self.list_datasources_of_profile(prof)
            for ds in dts:
                state = self.get_datasource_state(ds, host, instance)
                lst.append((host, instance, ds, state))
            return lst
        except Exception as ex:
            raise CliError(
                "Error list_data_sources_states_of_host_instance({0}, {1}): {2} ".format(host, instance, str(ex))
            )

    def list_datas_sources_states_of_host(self, host):
        """List states of a instance datasources
        :author: Luiz Antonio

        :param host: Host name (str)
        :return: A tuple (host, server (instance), state)
        """
        try:
            lst = []
            insts = self.list_started_instances_of_a_host(host)
            for instance in insts:
                lst += self.list_data_sources_states_of_host_instance(host, instance)
            return lst
        except Exception as ex:
            raise CliError(
                "Error list_datas_sources_states_of_host({0}): {1} ".format(host, str(ex))
            )

    def list_hosts_ctrls(self):
        """List the host controllers
        :author: Luiz Antonio

        :return: List (list of str) of  host controllers names
        """
        try:
            domsrv = unicode(self.controller.split(":")[0])
            lsthsts = copy.copy(self.list_domain_hosts())
            regex = re.compile("^" + domsrv)
            return [x for i, x in enumerate(lsthsts) if not re.match(regex,x)]
        except Exception as ex:
            raise CliError(
                "Error list_datas_sources_states_of_host(): {0} ".format(str(ex))
            )

    def is_in_list_hosts_ctrls(self, host):
        """Ask if a given host is in the list o host controllers
         :author: Luiz Antonio

        :param host(str): Host name.
        :return: True if the given host name is in the list of host controllers
        """
        return host in self.list_hosts_ctrls()

    def list_instances_of_a_host(self, host):
        """List the server(instances) names of a given host
        :author: Luiz Antonio

        :param host:
        :return: A (list) of server names (str).
        """
        try:
            if not self.domain:
                raise CliError(
                    "Error list_instances_of_a_host: It is not a domain server."
                )
            if not self.is_in_list_hosts_ctrls(host):
                raise CliError(
                    "Error list_instances_of_a_host: host '{0}' is not started as a host controller.".format(host)
                )
            cmdo = '{"operation":"read-children-names","child-type":"server-config","address":[{"host":"'
            cmdo += host
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error list_instances_of_a_host({0}): {1} code".format(host, str(ex))
            )

    def list_started_instances_of_a_host(self, host):
        """List the started servers(instances) of a host
        :author: Luiz Antonio

        :param host(str): host name.
        :return: A (list) of started servers(str)
        """
        try:
            started = []
            for srvr in self.list_instances_of_a_host(host):
                if self.is_server_state_started(host, srvr):
                    started.append(srvr)
            return started
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error list_instances_of_a_host({0}): {1} code".format(host, str(ex))
            )

    def get_state_of_a_host_instance(self, host, instance):
        """ Get a state of a server(instance)
        :author: Luiz Antonio

        :param host(str): Host name.
        :param instance(str): Server Name (instance)
        :return: The state(str) of a given server(instance)
        """
        try:
            if not self.domain:
                raise CliError(
                    "Error get_state_of_host_instance: It is not a domain server."
                )
            if not self.is_in_list_hosts_ctrls(host):
                raise CliError(
                    "Error get_state_of_a_host_instance: host '{0}' is not started as a host controller.".format(host)
                )
            cmdo = '{"operation":"read-attribute","address":[{"host":"'
            cmdo += host
            cmdo += '"},{"server-config":"'
            cmdo += instance
            cmdo += '"}],"name":"status","json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error get_state_of_host_instance({0}, {1}): {2} code".format(host, instance, str(ex))
            )

    def list_instances_states_of_a_host(self, host):
        """List the states of all server(instances) of a host.
        :author: Luiz Antonio

        :param host(str): Host name.
        :return: The tuple (host(str), server(str), state(str))
        """
        if not self.is_in_list_hosts_ctrls(host):
            raise CliError(
                "Error list_instances_states_of_a_host: host '{0}' is not started as a host controller.".format(host)
            )
        res = []
        for inst in self.list_instances_of_a_host(host):
            state = self.get_state_of_a_host_instance(host, inst)
            res.append((host, inst, state))
        return res

    def stop_servers_of_a_host(self, host):
        """Stop all servers of a host
        :author: Luiz Antonio

        :param host(str): Hot name.
        :return: None
        """
        if not self.is_in_list_hosts_ctrls(host):
            raise CliError(
                "Error stop_servers_of_a_host({0}): Host '{0}' is not started as a host controller.".format(host)
            )
        for x in self.list_instances_states_of_a_host(host):
            (hst, inst, sts) = x
            if sts in ["STARTED", "STARTING"]:
                self.stop_host_instance(host,inst)

    def start_servers_of_a_host(self, host):
        """Start all servers of a host
              :author: Luiz Antonio

              :param host(str): Hot name.
              :return None
        """
        if not self.is_in_list_hosts_ctrls(host):
            raise CliError(
                "Error start_servers_of_a_host({0}): Host '{0}' is not started as a host controller.".format(host)
            )
        for x in self.list_instances_states_of_a_host(host):
            (hst, inst, sts) = x
            if sts not in ["STARTED", "STARTING"]:
                self.start_host_instance(host,inst)

    def shutdown_host(self, host):
        """Shutdown the host. Note: after that you can only start in the server
        :author: Luiz Antonio

        :param host(str): Host name
        :return: the result(str).
        """
        try:
            if not self.is_in_list_hosts_ctrls(host):
                raise CliError(
                    "Error shutdown_host {0}: Host '{0}' is not started as a host controller.".format(host)
                )
            if not self.domain:
                raise CliError(
                    "Error shutdown_host {0}: It is not a domain server.".format(host)
                )
            cmdo = '{"operation":"shutdown","child-type":"server","address":[{"host":"'
            cmdo += host
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error shutdown_host({0}): {1} code".format(host, str(ex))
            )

    def stop_host_instance(self, host, instance):
        """ Stop a server(instance) of a host
        :author: Luiz Antonio

        :param host(str): Host name.
        :param instance(str): Server(instance) name.
        :return: The result(str).
        """
        try:
            if not self.is_in_list_hosts_ctrls(host):
                raise CliError(
                    "Error stop_host_instance({0},{1}): host '{0}' is not started as a host controller."
                        .format(host,instance)
                )
            if not self.domain:
                raise CliError(
                    "Error stop_host_instance({0},{1}): It is not a domain server.".format(host, instance)
                )
            cmdo = '{"operation":"stop","address":[{"host":"'
            cmdo += host
            cmdo += '"},{"server-config":"'
            cmdo += instance
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            log.error(sv_error.msg)
            raise sv_error
        except CliError as cli_error:
            log.error(cli_error.msg)
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error stop_host_instance({0},{1}): {2} code".format(host, instance, str(ex))
            )

    def start_host_instance(self, host, instance):
        """Start a host server(instance).
        :author: Luiz Antonio

        :param host: A host name.
        :param instance: A server(instance) name
        :return: The result(str).
        """
        try:
            if not self.is_in_list_hosts_ctrls(host):
                raise CliError(
                    "Error start_host_instance: host '{0}' is not started as a host controller.".format(host)
                )
            if not self.domain:
                raise CliError(
                    "Error start_host_instance: It is not a domain server."
                )
            cmdo = '{"operation":"start","address":[{"host":"'
            cmdo += host
            cmdo += '"},{"server-config":"'
            cmdo += instance
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            raise sv_error
        except CliError as cli_error:
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error start_host_instance({0},{1}): {2} code".format(host, instance, ex)
            )

    def stop_servers(self):
        """Stop all servers(instances) of all hosts.
        :author: Luiz Antonio

        :return: Result(str).
        """
        try:
            if not self.domain:
                raise CliError(
                    "Error stop_host_instance: It is not a domain server."
                )
            cmdo = '{"operation":"stop-servers","address":[],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            raise sv_error
        except CliError as cli_error:
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error stop_servers: {0} .".format(str(ex))
            )

    def start_servers(self):
        """Start all servers(instances) of all hosts.
        :author: Luiz Antonio

        :return: Result(str)
        """
        try:
            if not self.domain:
                raise CliError(
                    "Error start-servers: It is not a domain server."
                )
            cmdo = '{"operation":"start-servers","address":[],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            raise sv_error
        except CliError as cli_error:
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error stop_servers: {0} .".format(str(ex))
            )

    def is_server_group(self, name):
        """Ask if the name given is a server group of the current domain.
        :author: Luiz Antonio

        :param name(str): Server group name.
        :return: True if the name given is a sever group name, otherwise False.
        """
        return name in self.list_server_groups()

    def stop_server_group(self, srvrgrp):
        """Stop all servers(instances) of this server group in all hosts.
         :author: Luiz Antonio

        :param srvrgrp(str):
        :return: Result(str)
        """
        try:
            if not self.is_server_group(srvrgrp):
                raise CliError(
                    "Error stop_server_group: Server group {0} does no exist on this domain".format(srvrgrp)
                )
            cmdo = '{"operation":"stop-servers","address":[{"server-group":"'
            cmdo += srvrgrp
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            raise sv_error
        except CliError as cli_error:
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error stop_server_group({0}): {1} .".format(srvrgrp, str(ex))
            )

    def start_server_group(self, srvrgrp):
        """Start all severs(instances) o this server group in all hosts.
        :author: Luiz Antonio

        :param srvrgrp(str): Server group name.
        :return: Result(str)
        """
        try:
            if not self.is_server_group(srvrgrp):
                raise CliError(
                    "Error stop_server_group: Server group {0} does no exist on this domain".format(srvrgrp)
                )
            cmdo = '{"operation":"start-servers","address":[{"server-group":"'
            cmdo += srvrgrp
            cmdo += '"}],"json.pretty":1}'
            res = self._invoke_cli(cmdo)
            return res["result"]
        except ServerError as sv_error:
            raise sv_error
        except CliError as cli_error:
            raise cli_error
        except Exception as ex:
            raise CliError(
                "Error stop_server_group({0}): {1}.".format(srvrgrp, str(ex))
            )

# When err "failed" received from Domain ctrl or server standalone
class CliError(Exception):
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


class Deployment:
    def __init__(
            self, name, runtime_name, enabled=False, path=None, server_group=None
    ):
        self.name = name
        self.runtime_name = runtime_name
        self.enabled = enabled
        self.path = path
        self.server_group = server_group

    def __str__(self):
        return "{0} - {1} - {2}{3}".format(
            self.name,
            self.runtime_name,
            'enabled' if self.enabled else 'disabled',
            " - " + self.server_group if self.server_group else ""
        )


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
