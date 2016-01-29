#!/usr/bin/python
import subprocess
import json
import logging

logging.basicConfig(format="%(asctime)s [jbosscli] %(message)s",
                        datefmt="%d/%m/%Y %H:%M:%S",
                        level=logging.DEBUG)

def invoke_cli(controller, command):
    process = subprocess.Popen(["/opt/jboss/bin/jboss-cli.sh", "--connect", "controller=%s"%controller, "--command=%s"%command], stdout=subprocess.PIPE)
    logging.debug("Running on %s -> %s", controller, command)
    stdout = process.communicate()[0]
    logging.debug("Process executed with return code: %i", process.returncode)
    logging.debug(stdout)

    if (process.returncode > 0):
        raise CliError(stdout)

    result = parse_output(stdout)

    return result

def read_used_heap(controller):
    command = "/core-service=platform-mbean/type=memory:read-resource(include-runtime=true)"

    result = invoke_cli(controller, command)

    used_heap = result['result']['heap-memory-usage']['used']
    used_heap = float(used_heap)/1024/1024/1024

    return used_heap

def restart(controller):
    command = ":shutdown(restart=true)"
    return invoke_cli(controller, command)

def parse_output(output):
    parsed = output.replace("=>", ":").replace("L", "") #I know. Silly.
    return json.loads(parsed)

def list_domain_hosts(controller):
    command = "ls /host"
    invoke_cli(controller, command)

class CliError(Exception):
    def __init__(self, stdout):
        self.stdout = stdout
    def __str__(self):
        return repr(self.stdout)


