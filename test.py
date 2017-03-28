import time

from jbosscli2 import Jbosscli

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
    #print '\n'.join(output_buffer)

    #deployments = []
    deployments = cli.hosts[0].deployments
    #for group in cli.server_groups:
    #    deployments.extend(group.deployments)

    ctx_roots = [(d.name, d.enabled, d.get_context_root()) for d in deployments]

    print ctx_roots

if __name__ == "__main__":
    test("serie1cabrio:9990")
    #test("audia1:9990")
    #test("vmpassijuw:9990")
    #test("vmpassijuw:19990")
    #test("atron:29990")
    #test("classea:19990")
