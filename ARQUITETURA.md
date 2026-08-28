# Arquitetura do Sistema

## Visão geral

O projeto utiliza uma arquitetura Flask monolítica adequada ao escopo acadêmico:

```text
Navegador / outro sistema
          │
          ├── HTML + formulários ──→ rotas Flask ──→ SQLite
          │
          ├── CSV / JSON / ZIP ────→ importadores ─→ SQLite + logs
          │
          └── API JSON ────────────→ regras ───────→ SQLite + logs
```

O arquivo `app.py` concentra a inicialização do banco, regras de negócio,
importadores, páginas e API. As telas ficam em `templates/`, enquanto o design e
o comportamento do menu/upload ficam em `static/`.

## Camadas lógicas

### Persistência

- `get_db()` abre conexões SQLite com retorno por nome de coluna.
- `init_db()` cria tabelas, dados iniciais e migra bancos de versões anteriores.
- Chaves estrangeiras são habilitadas em cada conexão.
- O índice `ux_patrimonio_integracao` garante a identidade de cada unidade
  importada.

### Regras patrimoniais

- Cadastro manual de bens.
- Geração automática de um código patrimonial por unidade importada.
- Baixa patrimonial sem remoção do histórico.
- Movimentações entre setores.
- Manutenções com status e custo.

### Interoperabilidade

- Detecção automática do layout CSV pelo cabeçalho.
- Leitura de vírgula ou ponto e vírgula.
- Compatibilidade com UTF-8 BOM e Latin-1 na entrada.
- Processamento de ZIP de Vendas completamente em memória.
- Limites de segurança para quantidade e tamanho dos arquivos do ZIP.
- Importação transacional por registro com `SAVEPOINT`.
- Log de sucesso, erro ou evento ignorado.

### Apresentação

- Templates Jinja renderizados no servidor.
- Layout responsivo sem framework frontend.
- Fonte Manrope e Tabler Icons hospedados localmente.
- JavaScript pequeno e progressivo para menu móvel e área de upload.

## Modelo de dados

| Tabela | Responsabilidade |
|---|---|
| `usuarios` | Login, nome e perfil de acesso. |
| `categorias` | Classificação dos bens. |
| `setores` | Localização/responsabilidade interna. |
| `patrimonios` | Bem patrimonial e vínculos de venda, cliente, produto e colaborador. |
| `movimentacoes` | Transferências entre setores. |
| `manutencoes` | Problema, período, custo e situação da manutenção. |
| `importacoes` | Resumo de cada arquivo processado. |
| `integracao_logs` | Auditoria detalhada por evento/unidade. |

Campos de integração importantes em `patrimonios`:

- `origem_sistema`;
- `produto_sku`;
- `external_id`;
- `unidade_origem`;
- `venda_external_id`;
- `cliente_documento` e `cliente_nome`;
- `colaborador_external_id` e `colaborador_nome`;
- `data_venda` e `garantia_ate`.

## Fluxo Vendas → Patrimônio

### Entrada consolidada

Uma linha de venda contém a venda, o item, o SKU e a quantidade. A função
`importar_venda_patrimonio()`:

1. normaliza nomes de campos e aliases;
2. valida venda, SKU e quantidade;
3. aceita somente status concluídos/faturados;
4. calcula `VENDA-{venda}-ITEM-{item}` como identificador externo;
5. cria ou atualiza uma unidade patrimonial para cada unidade vendida;
6. vincula cliente, vendedor/colaborador e garantia;
7. registra `REGISTRAR_POS_VENDA` no log.

### Pacote ZIP

`carregar_pacote_vendas()` identifica as tabelas pelo cabeçalho, e não pelo nome
do arquivo. Em seguida cruza:

```text
pedidos.id_cliente  → clientes.id_cliente
pedidos.id_vendedor → vendedores.id_vendedor
itens.id_pedido     → pedidos.id_pedido
itens.id_produto    → produtos.id_produto
```

O resultado interno usa o mesmo contrato da entrada consolidada, evitando duas
implementações diferentes da regra patrimonial.

### API

`POST /api/integracao/vendas/patrimonios` chama a mesma regra usada pelos
arquivos. A API aceita:

- um objeto de venda;
- uma lista de objetos;
- `{ "vendas": [...] }`;
- `{ "patrimonios": [...] }`.

Até mil registros podem ser processados por requisição. Registros válidos e
inválidos são isolados com `SAVEPOINT`; uma falha não desfaz os anteriores.

## Idempotência

A identidade de uma unidade é:

```text
origem_sistema + external_id + unidade_origem
```

Exemplo para dez unidades do mesmo item:

```text
VENDAS + VENDA-1-ITEM-1 + 1
VENDAS + VENDA-1-ITEM-1 + 2
...
VENDAS + VENDA-1-ITEM-1 + 10
```

Reenviar o mesmo item localiza as unidades existentes e executa atualização.

## Fluxo Patrimônio → RH

As responsabilidades originadas em Vendas são disponibilizadas em:

```text
GET /api/integracao/rh/responsabilidades
GET /exportacao/rh_colaboradores.csv
```

O contrato inclui venda, patrimônio, produto, cliente, colaborador, status,
data da venda e garantia.

## Decisões de design

As três direções visuais aprovadas foram aplicadas em conjunto:

- Dashboard: centro de comando e fluxo entre os módulos.
- Patrimônios: inventário pesquisável com filtros e tabela compacta.
- Integrações: processo em três etapas, entrada por arquivo, API e auditoria.

Um único sistema visual conecta as páginas: Manrope, Tabler Icons, verde
floresta, superfícies quentes, divisores leves e estados semânticos.

## Limites conhecidos

- SQLite atende à apresentação e a pequenos grupos, não a alta concorrência.
- O servidor Flask embutido é de desenvolvimento.
- As APIs não possuem token/autenticação nesta versão acadêmica.
- A chave secreta e a senha inicial precisam ser trocadas em uma publicação
  externa.
- A listagem ainda não utiliza paginação no servidor.

## Evolução recomendada

Para produção, separar configuração por ambiente, usar servidor WSGI, adicionar
autenticação da API, aplicar CSRF nos formulários, migrar para PostgreSQL e
adicionar testes automatizados permanentes.
