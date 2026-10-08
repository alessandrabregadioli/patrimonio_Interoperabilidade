# Histórico do projeto

## Integração XML formal — setembro de 2026

- Contrato XML v1.0 com namespace próprio e modelo completo.
- XSD formal com tipos simples, tipos complexos, hierarquia e cardinalidades.
- Importação XML pela interface com validação integral antes da persistência.
- API XML de entrada e saída em `/api/integracao/vendas/patrimonios.xml`.
- Download do modelo, do XSD e da exportação XML pela central de integrações.
- Parser protegido contra DTD, entidades externas e acesso à rede.
- Limites de 10 MB e 1000 itens por lote.
- Testes de XML válido, idempotência, exportação válida e rejeição de XML
  incompatível com o XSD.
- Documento técnico com justificativas, comparação CSV versus XML e análise de
  acoplamento.

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
- Exportação `sac_para_rh.csv` ajustada ao modelo oficial do RH, com seis
  campos, delimitador ponto e vírgula e datas em `DD/MM/AAAA`.

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
