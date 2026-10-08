# Mapa verificado das integrações

Verificação realizada nas interfaces disponíveis em 30/08/2026.

## Fluxo real observado

```text
Estoque ── produtos ────────┬──→ Marketing
                            ├──→ Compras
                            └──→ Vendas

Vendas ── movimentações ───────→ Estoque
Vendas ── ENTRADA 0/1/9 ───────→ Financeiro
Vendas ── itens vendidos ──────→ Marketing
Vendas ── pacote de venda ─────→ Patrimônio

Compras ── pedidos ──→ Adaptador ── SAIDA 0/1/9 ──→ Financeiro
Patrimônio ── eventos do SAC ──→ RH
RH ── equipe de Marketing ─────→ Marketing
```

## Contratos

### Estoque

- Exporta produtos em `/api/csv/produtos`.
- Importa e exporta movimentações em `/api/csv/movimentacoes`.
- Movimentação: `produto_sku,tipo,quantidade,origem,external_id,operacao`.

### Compras

- Importa do Estoque: `SKU,Nome,Quantidade,Preço,Fornecedor`.
- Fornecedor é opcional e os itens são agrupados por fornecedor.
- Exporta pedidos, itens, recebimentos e movimentações com itens em colunas.
- O roteiro automatizado converte essa exportação para o contrato financeiro
  `SAIDA` 0/1/9.

### Financeiro

- Importa `ENTRADA`, `SAIDA`, `CLIENTES` e `FORNECEDORES`.
- Entrada: vendas/recebimentos agrupados por cliente, sem cabeçalho, registros
  0/1/9.
- Saída: despesas/pagamentos agrupados por fornecedor, sem cabeçalho, registros
  0/1/9.
- Clientes e fornecedores usam o cabeçalho
  `nome,documento,email,telefone`.
- Exporta relatórios de entradas, saídas e balanço.

### Vendas

- Importa produtos do Estoque usando o SKU como chave.
- Importa clientes do Financeiro no formato
  `nome,documento,email,telefone`.
- Exporta movimentações para o Estoque.
- Exporta ENTRADA financeira no contrato 0/1/9.
- Exporta itens para Marketing com SKU, data de emissão, quantidade e preço.
- Mantém clientes, vendedores, produtos, pedidos, itens e faturamentos que o
  Patrimônio consegue receber em pacote ZIP.

### Marketing

- Importa produtos do Estoque.
- Importa itens vendidos de Vendas.
- Exporta campanhas e ações em CSV.
- Importa a equipe enviada pelo RH em `/colaboradores/importar`.
- Exporta campanhas para Vendas; a interface de Vendas ainda não mostra um
  importador específico para esse arquivo.

### Patrimônio

- Importa CSV, JSON ou pacote ZIP de Vendas.
- Cria uma unidade patrimonial para cada unidade vendida.
- Exporta `sac_para_rh.csv`.

### RH

- Importa eventos do Patrimônio no contrato:
  `id_evento;id_colaborador;data_evento;tipo_evento;descricao;status_evento`.
- Exige que `id_colaborador` exista na base.
- Exporta a equipe de Marketing e referências mínimas para os demais setores.
