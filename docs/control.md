# Control

O módulo `control` contém as classes responsáveis pelo controle centralizado da rede: roteamento e compartilhamento de estado entre camadas.

---

## Importação

```python
from quantumnet.control import Controller, NetworkContext
```

---

## NetworkContext

O `NetworkContext` é um container leve de **injeção de dependência**. Agrupa o estado mutável compartilhado (`clock`, `graph`, `hosts`, `config`) e fornece métodos utilitários para que as camadas acessem o que precisam sem manter uma referência ao objeto `Network` completo.

Todos os atributos são referências aos mesmos objetos mutáveis mantidos pelo `Network` — alterações feitas pelas camadas são imediatamente visíveis em toda a simulação.

### Construtor

```python
NetworkContext(clock, graph, hosts, config)
```

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `clock` | `Clock` | Relógio de simulação por eventos discretos |
| `graph` | `nx.Graph` | Grafo NetworkX representando a topologia |
| `hosts` | `dict` | Dicionário de hosts (chave: ID inteiro) |
| `config` | `SimulationConfig` | Configuração da simulação |

### Atributos

| Atributo | Tipo | Descrição |
|---|---|---|
| `clock` | `Clock` | Relógio DES compartilhado |
| `graph` | `nx.Graph` | Grafo da topologia (mutável, compartilhado) |
| `hosts` | `dict` | Hosts por ID (mutável, compartilhado) |
| `config` | `SimulationConfig` | Configuração da rede |

### Métodos Públicos

#### `get_host(host_id)`

Retorna o host com o ID informado.

```python
host = context.get_host(0)
```

#### `generate_qubit_id() -> int`

Gera um ID único de qubit válido em todas as camadas. Cada chamada retorna um valor sequencial e incrementa o contador interno.

```python
qid = context.generate_qubit_id()  # 0, 1, 2, ...
```

#### `get_eprs_from_edge(alice, bob) -> list`

Retorna a lista de pares EPR associados à aresta entre `alice` e `bob` no grafo.

```python
eprs = context.get_eprs_from_edge(0, 1)
```

---

## Controller

O `Controller` é responsável pelo **roteamento**: constrói tabelas de menor caminho para cada host, valida rotas e anuncia decisões de roteamento.

### Construtor

```python
Controller(network)
```

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `network` | `Network` | Objeto da rede. Deve possuir `.graph` e `.hosts` |

### Métodos Públicos

#### `create_routing_table(host_id) -> dict`

Cria a tabela de roteamento para um nó usando `nx.shortest_path()`. Retorna um dicionário mapeando cada destino ao caminho completo (lista de IDs de nós).

```python
controller = Controller(net)
table = controller.create_routing_table(0)
# {0: [0], 1: [0, 1], 2: [0, 1, 2], ...}
```

#### `register_routing_tables()`

Registra tabelas de roteamento para **todos** os hosts da rede. Itera sobre `network.hosts`, chama `create_routing_table()` para cada um e armazena a tabela no respectivo host via `host.set_routing_table()`.

```python
controller = Controller(net)
controller.register_routing_tables()
```

#### `check_route(route) -> bool`

Valida uma rota verificando:
1. A rota não está vazia
2. Todos os nós existem no grafo
3. Existem arestas entre cada par consecutivo de nós

```python
controller.check_route([0, 1, 2])  # True se a rota é válida
```

#### `announce_to_route_nodes(route)`

Anuncia (via log) que cada nó na rota foi informado da decisão de roteamento.

#### `announce_to_alice_and_bob(route)`

Anuncia (via log) que Alice (`route[0]`) e Bob (`route[-1]`) foram informados.

---

## Fluxo Típico de Uso

O `NetworkContext` é criado automaticamente pelo `Network` e passado a todas as camadas. O `Controller` pode ser usado externamente para configurar roteamento:

```python
from quantumnet.runtime.clock import Clock
from quantumnet.topology.network import Network
from quantumnet.control import Controller

clock = Clock()
net = Network(clock=clock)
net.set_ready_topology('Line', 5)

# Registrar tabelas de roteamento
controller = Controller(net)
controller.register_routing_tables()

# Verificar uma rota
rota = [0, 1, 2, 3, 4]
if controller.check_route(rota):
    print("Rota válida!")

clock.run()
```

---

## Referência Rápida

| Classe | Responsabilidade |
|---|---|
| `NetworkContext` | Container de estado compartilhado entre camadas |
| `Controller` | Roteamento: tabelas de menor caminho, validação de rotas |

| Método (`NetworkContext`) | O que faz |
|---|---|
| `get_host(id)` | Retorna o host pelo ID |
| `generate_qubit_id()` | Gera ID único para qubit |
| `get_eprs_from_edge(a, b)` | Retorna EPRs da aresta |

| Método (`Controller`) | O que faz |
|---|---|
| `create_routing_table(id)` | Cria tabela de roteamento para um host |
| `register_routing_tables()` | Registra tabelas de todos os hosts |
| `check_route(rota)` | Valida uma rota |
| `announce_to_route_nodes(rota)` | Anuncia rota aos nós |
| `announce_to_alice_and_bob(rota)` | Anuncia rota a Alice e Bob |
