#!/usr/bin/python
import subprocess
import json
import logging

log = logging.getLogger("jbosscli")

def invoke_cli(controller, auth, command):
    process = subprocess.Popen(["curl", "-s", "--digest", "http://{0}/management".format(controller), "--header", "Content-Type: application/json",  "-d", command, "-u", auth], stdout=subprocess.PIPE)
    log.debug("Running on %s -> %s", controller, command)
    stdout = process.communicate()[0]
    log.debug("Process executed with return code: %i", process.returncode)
    log.debug(stdout)

    if (process.returncode > 0):
        raise CliError(stdout)

    return json.loads(stdout)

def read_used_heap(controller, auth, host=None, server=None):
    command = '{{"operation":"read-resource", "include-runtime":"true", "address":[{0}"core-service", "platform-mbean", "type", "memory"]}}'
    address = ""

    if (host and server):
        address = '"host","{0}","server","{1}", '.format(host,server)
   
    command = command.format(address)

    result = invoke_cli(controller, auth, command)

    heap_memory_usage = result['result']['heap-memory-usage']

    used_heap = heap_memory_usage['used']
    used_heap = float(used_heap)/1024/1024/1024
    
    max_heap = heap_memory_usage['max']
    max_heap = float(max_heap)/1024/1024/1024

    return (used_heap, max_heap)

def restart(controller, auth, host=None, server=None):
    command = '{{"operation":{0}{1}}}'
    operation = ""
    address = ""

    if (host and server):
        address = ', "address": ["host", "{0}","server-config", "{1}"]'.format(host, server)
        operation = 'restart'
    else:
        operation = '"shutdown", "restart":"true"'

    command = command.format(operation, address)
    return invoke_cli(controller, auth, command)

def list_domain_hosts(controller, auth):
    command = '{"operation":"read-children-names", "child-type":"host"}'
    result = invoke_cli(controller, auth, command)
    hosts = result['result']
    return hosts

def list_servers(controller, auth, host):
    command = '{{"operation":"read-children-names", "child-type":"server", "address":["host","{0}"]}}'.format(host)
    result = invoke_cli(controller, auth, command)

    if result['outcome'] == "failed":
        return []
    else:
        servers = result['result']
        return servers


class CliError(Exception):
    def __init__(self, stdout):
        self.stdout = stdout
    def __str__(self):
        return repr(self.stdout)


