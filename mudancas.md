Pessoal,

Estive revendo o código do jbosscli e fiz umas anotações. Melhorei um pouco a cobertura de teste dele para poder começar a correção de algumas coisas.

Ressalto a importância de fazer os testes antes, tanto para que não sejam viciados quanto para evitar pequenos erros. [Tinham alguns métodos que não compilavam](http://gogs.jfrj.jus.br/seinap/jbosscli/commit/aa0c2e75dae4ab8f0593e58167673dd3ebd92e0f).

Aproveitei pra fazer uma modificação que simplifica bastante a montagem dos comandos em json. Eles não precisam mais ser strings, podem ser dicionários. Dessa forma não precisamos ficar fazendo malabarismos com `str.format()` pra montar os comandos passados pro `_invoke_cli()`. Manti a compatibilidade com comandos em forma de string para que não quebre os métodos que ainda não foram refatorados.

Temos que ter cuidado especial com esse projeto pois todos os scritps de automação dependem dele.

Considerações
-------------

```python
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
```

O trecho de código acima pode virar um método pra tratamento de erro, já que é bastante repetido e basicamente o que muda é a mensagem.

* [V] `invoke_cli()` -> retornar direto o campo 'result', já que o campo 'outcome' é sempre 'success'.
* `fecth_context_root()` -> `fetch_context_root()` -> Pode se tornar uma propriedade de Deployment, evitando a necessidade de ir no servidor buscar.
* `is_server_state_started()` -> `is_server_started()`
* `list_all_profiles()` -> `list_profiles()`
* `list_datasources_of_profile()` -> datasource pode virar uma classe com o atributo profile, assim como ServerGroup ou Deployment. Desse modo, basta chamar o `list_data_sources() (ou get_data_sources())` e filtrar a própria lista.
* `get_profile_of_server_group()` -> profile pode se tornar uma propriedade de `ServerGroup`, eliminando a necessidade de ir no servidor buscar.
* `list_server_groups_of_profile()` -> bastaria filtrar a lista, com a modificação acima
* `get_server_group_of_host_instance()` -> ServerInstance poderia ter uma propriedade chamada ServerGroup.
* `is_in_list_hosts_ctrls()` -> não seria guardar em `self` uma lista dos controllers para não ter que reconstruir a lista?
* `list_instances_of_a_host()` -> `self.instances` contém uma lista de instâncias com referências para seus respectivos hosts. Este método bastaria retornar `[i for i in self.instances if i.host is host]`
* `shutdown_host()` -> `"operation":"shutdown","child-type":"server"` child-type não é um parâmetro de shutdown. Esse método funciona?
* `'json-pretty': 1` -> não é necessário para a criação do dicionário feita pelo `_invoke_cli()`.
