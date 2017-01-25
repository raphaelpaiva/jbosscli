jbosscli
========

A python frontend to JBoss wildfly  HTTP management API

Usage
-----

```python
from jbosscli import Jbosscli
cli = cli = Jbosscli("host:port", "user:password")
print cli.name
print cli.read_used_heap(host="ahost", server="aserver")
```

For api reference, please refer to jbosscli.py itself. I'll be working on some docs in the future.
