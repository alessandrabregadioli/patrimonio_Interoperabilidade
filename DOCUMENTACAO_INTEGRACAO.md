# Documentação de Integração - Sistema de Patrimônio

Versão 2.1 - Agosto de 2026

## 1. Objetivo

Esta documentação define os contratos de comunicação do Sistema de Patrimônio
com os demais sistemas. A mesma informação pode circular por arquivos CSV/ZIP
ou pela API HTTP na rede/VPN, sem acesso direto ao banco de dados.

### Posição no ciclo dos grupos

```text
Marketing → Estoque → Compras → Financeiro → Vendas
                                              ↓
                               SAC e Patrimônio → RH/Colaborador → Marketing
```

O trecho implementado por este projeto é `Vendas → SAC e Patrimônio →
RH/Colaborador`. Os demais grupos continuam responsáveis por implementar os
outros elos do ciclo em seus próprios sistemas.

## 2. Regras gerais

- Extensão: `.csv`.
- Codificação: UTF-8; as exportações utilizam UTF-8 com BOM.
- Delimitador aceito na importação: vírgula ou ponto e vírgula.
- Primeira linha: cabeçalho obrigatório.
- Datas: `AAAA-MM-DD`.
- Data e hora: ISO 8601, por exemplo `2026-08-27T20:00:00-03:00`.
- Valor decimal: ponto ou vírgula são aceitos na importação; a exportação utiliza ponto.
- Identificadores locais de outro sistema não são usados como chave primária local.
- `external_id` identifica o evento no sistema de origem e evita duplicidade.
- Cada linha é processada em transação isolada. Uma falha não deixa aquela linha parcialmente gravada.

## 3. Vendas para o Patrimônio

Este é o fluxo principal do sistema. Uma venda concluída disponibiliza o produto vendido, o cliente e o colaborador responsável. O Patrimônio cria uma unidade para cada item vendido e mantém o vínculo necessário para pós-venda, garantia e envio ao RH.

### CSV consolidado

```csv
venda_external_id,item_external_id,produto_sku,produto_nome,produto_descricao,quantidade,valor_unitario,data_venda,status_venda,cliente_documento,cliente_nome,colaborador_external_id,colaborador_nome,garantia_ate
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---:|---|
| `venda_external_id` | Texto | Sim | Identificador da venda no sistema de Vendas. |
| `item_external_id` | Texto | Não | Identificador da linha/item vendido. |
| `produto_sku` | Texto | Sim | Código compartilhado do produto. |
| `produto_nome` | Texto | Não | Nome do produto; na ausência, utiliza o SKU. |
| `quantidade` | Inteiro | Sim | Uma unidade patrimonial é gerada para cada unidade vendida. |
| `valor_unitario` | Decimal | Não | Valor unitário do produto vendido. |
| `data_venda` | Data | Não | Data da venda. |
| `status_venda` | Texto | Não | São processadas vendas faturadas, concluídas, aprovadas, finalizadas ou vendidas. |
| `cliente_documento` | Texto | Não | CPF ou CNPJ do cliente. |
| `cliente_nome` | Texto | Não | Nome do cliente. |
| `colaborador_external_id` | Texto | Não | Identificador do vendedor/colaborador responsável. |
| `colaborador_nome` | Texto | Não | Nome do colaborador responsável. |
| `garantia_ate` | Data | Não | Data de garantia ou validade, conforme o contrato com Vendas. |

### Pacote ZIP de Vendas

O sistema também aceita diretamente um ZIP contendo CSVs com estas entidades:

- clientes: `id_cliente`, `nome`, `cpf_cnpj`;
- vendedores: `id_vendedor`, `nome`, `cpf`;
- produtos: `id_produto`, `sku`, `nome`;
- pedidos: `id_pedido`, `id_cliente`, `id_vendedor`, `data_pedido`, `status`;
- itens: `id_pedido_item`, `id_pedido`, `id_produto`, `quantidade`, `preco_unitario`.

Os arquivos são identificados pelo cabeçalho, não pelo nome. O importador cruza os IDs e produz registros equivalentes ao CSV consolidado.

### Envio ao vivo pela API

Vendas também pode enviar um registro ou uma lista no mesmo formato do CSV
consolidado:

```http
POST /api/integracao/vendas/patrimonios
Content-Type: application/json
```

```json
{
  "venda_external_id": "VEN-2026-001",
  "item_external_id": "ITEM-01",
  "produto_sku": "SKU001",
  "produto_nome": "Produto Exemplo",
  "quantidade": 1,
  "status_venda": "FATURADO",
  "cliente_documento": "12345678000190",
  "cliente_nome": "Cliente Exemplo Ltda",
  "colaborador_external_id": "COL-001",
  "colaborador_nome": "Ana Souza"
}
```

Reenviar a mesma venda e o mesmo item atualiza o registro existente, sem criar
duplicidade. Para consultar o que foi recebido:

```text
GET /api/integracao/vendas/patrimonios
```

Na rede/VPN, prefixe a rota com o endereço do computador que executa o sistema,
por exemplo `http://10.8.0.25:5000`.

## 4. Produtos do Estoque para o Patrimônio

### Cabeçalho reconhecido

```csv
id,sku,nome,descricao,quantidade,preco,estoque_minimo,created_at,updated_at
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---:|---|
| `id` | Texto | Não | Usado como `external_id`; na ausência, utiliza o SKU. |
| `sku` | Texto | Sim | Código compartilhado do produto. |
| `nome` | Texto | Sim | Nome do produto. |
| `descricao` | Texto | Não | Descrição livre. |
| `quantidade` | Inteiro | Sim | Quantidade de unidades físicas, entre 1 e 1000. |
| `preco` | Decimal | Não | Valor unitário de aquisição. |
| `estoque_minimo` | Inteiro | Não | Recebido, mas não utilizado pelo Patrimônio. |
| `created_at` | Data/hora | Não | Data do sistema de origem. |
| `updated_at` | Data/hora | Não | Data da última atualização. |

Cada unidade gera um patrimônio com status `PENDENTE`. O usuário completa número de série, setor e demais informações na tela de edição.

## 5. Movimentações do Estoque para o Patrimônio

### Cabeçalho reconhecido

```csv
produto_sku,tipo,quantidade,origem,external_id,operacao,created_at
```

| Campo | Tipo | Obrigatório | Regra |
|---|---|---:|---|
| `produto_sku` | Texto | Sim | Relaciona o evento ao produto. |
| `tipo` | Texto | Sim | Tipo informativo do movimento. |
| `quantidade` | Inteiro | Sim | Número de unidades afetadas. |
| `origem` | Texto | Sim | Sistema remetente, normalmente `ESTOQUE`. |
| `external_id` | Texto | Recomendado | Identificador único do evento. Se vazio, é calculado a partir da linha. |
| `operacao` | Texto | Condicional | `PATRIMONIALIZAR`, `CADASTRAR`, `ENTRADA` ou `BAIXAR`. |
| `created_at` | Data/hora | Não | Momento do evento na origem. |

Se `operacao` estiver vazia, alguns tipos patrimoniais conhecidos são convertidos automaticamente. Uma `VENDA` comercial é ignorada e registrada no log, pois não representa um bem de uso da empresa.

## 6. Patrimônio genérico

Campos obrigatórios:

```csv
codigo,nome
```

Campos opcionais:

```text
descricao,marca,modelo,numero_serie,data_aquisicao,valor,status,
categoria,setor,origem_sistema,produto_sku,external_id,unidade_origem
```

Se o código já existir, o registro é atualizado. Campos ausentes preservam o valor atual.

## 7. Exportação de patrimônios

Arquivo: `patrimonios_exportados.csv`.

```csv
codigo,produto_sku,nome,descricao,marca,modelo,numero_serie,data_aquisicao,valor,status,categoria,setor,origem_sistema,external_id,unidade_origem,venda_external_id,cliente_documento,cliente_nome,colaborador_external_id,colaborador_nome,data_venda,garantia_ate,criado_em
```

Esse arquivo pode ser consumido por Estoque, Compras, Financeiro ou RH, conforme o layout combinado entre os grupos.

## 8. Patrimônio para RH/Colaborador

Arquivo: `patrimonio_para_rh.csv`.

```csv
external_id,patrimonio_codigo,venda_external_id,produto_sku,produto_nome,cliente_documento,cliente_nome,colaborador_external_id,colaborador_nome,tipo_responsabilidade,status,data_venda,garantia_ate,origem_sistema,criado_em
```

O RH pode usar esse arquivo para registrar qual colaborador ficou responsável pelo atendimento, venda ou acompanhamento patrimonial. Os mesmos dados ficam disponíveis em JSON:

```text
GET /api/integracao/rh/responsabilidades
```

## 9. Exportação de movimentações

Arquivo: `movimentacoes_patrimonio.csv`.

```csv
movimentacao_id,codigo_patrimonio,produto_sku,data,setor_origem,setor_destino,observacao,usuario
```

## 10. Exportação de logs

Arquivo: `log_integracao.csv`.

```csv
log_id,external_id,sistema_origem,sistema_destino,arquivo,tipo_registro,operacao,status,mensagem,codigo_patrimonio,criado_em,usuario
```

Status possíveis: `SUCESSO`, `IGNORADO` e `ERRO`.

## 11. Idempotência

Uma unidade importada é identificada por:

```text
sistema_origem + external_id + unidade_origem
```

Importar o mesmo produto novamente atualiza as unidades existentes. Importar novamente a mesma movimentação confirmada não cria novos patrimônios.

## 12. Procedimento de demonstração

1. Iniciar o sistema e acessar pela VPN.
2. Abrir **Integrações**.
3. Importar `vendas_pacote_exemplo.zip` ou `vendas_patrimonio.csv`.
4. Conferir o produto vendido, cliente e colaborador na tela de patrimônios.
5. Importar o mesmo arquivo novamente e comprovar que a quantidade não aumenta.
6. Exportar `patrimonio_para_rh.csv`.
7. Consultar `/api/integracao/rh/responsabilidades`.
8. Exportar patrimônios e logs.
9. Apresentar `external_id`, operação, status e colaborador responsável.
