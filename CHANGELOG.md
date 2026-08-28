# Histórico do projeto

## Versão integrada e redesenhada — agosto de 2026

### Recuperação do sistema herdado

- Projeto original preservado; o trabalho foi realizado em uma cópia separada.
- Código Flask e banco SQLite analisados para descobrir o comportamento do
  sistema recebido no meio do desenvolvimento.
- Migrações compatíveis adicionadas para bancos existentes.

### Interoperabilidade

- Importação genérica de patrimônios por CSV e JSON.
- Detecção automática de CSV por cabeçalho.
- Compatibilidade com `produtos.csv` e `movimentacoes.csv` do Estoque.
- Processamento de movimentações patrimoniais e registro de eventos comerciais
  ignorados.
- Importação do pacote ZIP real de Vendas, cruzando clientes, vendedores,
  produtos, pedidos e itens.
- CSV consolidado de Vendas com produto, cliente, responsável e garantia.
- POST específico para Vendas e GET específico para RH.
- Criação de uma unidade patrimonial para cada unidade vendida.
- Idempotência de arquivos e API sem duplicar registros.
- Histórico resumido e log detalhado de sucesso, erro e evento ignorado.
- Exportações de patrimônios, movimentações, RH e logs em UTF-8 com BOM.

### Gestão patrimonial

- Campos de SKU, venda, cliente, colaborador, data de venda e garantia.
- Novos status `PENDENTE` e `VENDIDO`.
- Busca ampliada por código, nome, marca, SKU, categoria, setor e responsável.
- Filtros de status e setor.
- Dashboard com indicadores e atividade de integração.

### Redesign

- Três conceitos visuais combinados em uma única interface.
- Dashboard orientado ao fluxo Vendas → Patrimônio → RH.
- Inventário compacto e pesquisável.
- Central de integração com etapas, upload, rotas da API, exportações e auditoria.
- Login reformulado.
- Navegação ativa, menu móvel e responsividade.
- Upload por seleção ou arrastar/soltar.
- Fonte Manrope e Tabler Icons armazenados localmente.
- Símbolos/emoji removidos da navegação.
- Validação visual documentada em `design-qa.md`.

### Verificação

- ZIP real de Vendas: dez patrimônios criados.
- CSV consolidado: duas unidades criadas.
- API de Vendas: uma unidade criada.
- Reenvios: nenhuma duplicidade.
- APIs e exportações verificadas.
- Dez rotas autenticadas renderizadas com sucesso.
- Filtros e menu móvel testados no navegador.
- Console do navegador sem erros.
