# Integração XML do Sistema de SAC e Patrimônio

## Documento técnico de estrutura validação e acoplamento

**Sistema:** SAC e Patrimônio  
**Integração principal:** Vendas para Patrimônio  
**Contrato:** `urn:uniavan:patrimonio:v1`  
**Versão:** 1.0  
**Data:** 16 de setembro de 2026

## 1 Resumo executivo

O Sistema de SAC e Patrimônio recebe vendas concluídas e transforma cada unidade de produto vendida em um registro patrimonial. A integração XML foi implementada com um contrato XSD formal e versionado. Um documento somente é processado quando está bem formado e atende integralmente ao esquema. Essa decisão evita que campos ausentes, datas inválidas, quantidades negativas, valores mal formatados ou estados de venda desconhecidos alcancem a regra de negócio e o banco de dados.

O XML pode ser enviado pela tela de importação ou pela API. O mesmo modelo interno já usado pelas entradas CSV, JSON e ZIP recebe os dados depois da validação, preservando idempotência, geração de unidades patrimoniais, auditoria e disponibilização das responsabilidades ao RH. A aplicação também exporta os patrimônios de Vendas em XML validado pelo mesmo XSD.

## 2 Objetivo e escopo

O objetivo do contrato é padronizar a troca de dados entre Vendas e SAC e Patrimônio sem compartilhar tabelas, banco de dados ou código interno. O sistema de Vendas informa a venda, o cliente, o colaborador responsável e os itens. O Sistema de Patrimônio valida o lote, registra uma unidade patrimonial para cada quantidade vendida e mantém os dados necessários ao pós-venda e ao fluxo com RH.

O escopo desta versão cobre vendas com estado confirmado. Os estados aceitos são `FATURADO`, `CONCLUIDO`, `APROVADO`, `FINALIZADO` e `VENDIDO`. O contrato não cobre cancelamentos, devoluções ou atualizações parciais de cadastro. Esses eventos devem ser modelados em uma futura versão do namespace para não alterar o significado da versão 1.0.

## 3 Arquivos e pontos de integração

| Artefato | Finalidade |
|---|---|
| `integracao_xml/modelo-vendas-patrimonio.xml` | Instância XML completa e válida para teste e homologação |
| `integracao_xml/patrimonio-vendas-v1.xsd` | Contrato formal que define estrutura, tipos, obrigatoriedade e limites |
| `POST /api/integracao/vendas/patrimonios.xml` | Recebe XML no corpo da requisição e valida antes de processar |
| `GET /api/integracao/vendas/patrimonios.xml` | Exporta os patrimônios originados de Vendas em XML válido |
| `GET /importacao/modelo.xml` | Download autenticado do modelo pela interface |
| `GET /importacao/esquema.xsd` | Download autenticado do XSD pela interface |
| `GET /exportacao/patrimonios.xml` | Download autenticado da exportação XML |

O envio pela API deve usar o cabeçalho HTTP `Content-Type: application/xml`. Em caso de sucesso, a API retorna JSON com o identificador do lote, o resultado da validação, a quantidade total e os números de inseridos, atualizados, ignorados e erros. Um XML inválido recebe HTTP 422 e `valido_xsd: false`.

## 4 Modelo XML completo

O elemento raiz identifica o contrato e sua versão. O cabeçalho identifica o lote e os sistemas envolvidos. A coleção de vendas contém uma ou mais vendas; cada venda possui cliente, colaborador e um ou mais itens.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<integracaoPatrimonio xmlns="urn:uniavan:patrimonio:v1"
                      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                      xsi:schemaLocation="urn:uniavan:patrimonio:v1 patrimonio-vendas-v1.xsd"
                      versao="1.0">
  <cabecalho>
    <identificadorLote>LOTE-2026-001</identificadorLote>
    <sistemaOrigem>VENDAS</sistemaOrigem>
    <sistemaDestino>PATRIMONIO</sistemaDestino>
    <dataGeracao>2026-09-16T19:00:00-03:00</dataGeracao>
  </cabecalho>
  <vendas>
    <venda id="VEN-2026-001">
      <dataVenda>2026-09-16</dataVenda>
      <status>FATURADO</status>
      <cliente documento="12345678901">
        <nome>Cliente Exemplo</nome>
      </cliente>
      <colaborador id="COL-001">
        <nome>Ana Souza</nome>
      </colaborador>
      <itens>
        <item id="ITEM-001">
          <produto sku="NOTE-001">
            <nome>Notebook Corporativo</nome>
            <descricao>Notebook destinado ao atendimento de pós-venda</descricao>
          </produto>
          <quantidade>2</quantidade>
          <valorUnitario moeda="BRL">3500.00</valorUnitario>
          <garantiaAte>2027-09-16</garantiaAte>
        </item>
      </itens>
    </venda>
  </vendas>
</integracaoPatrimonio>
```

O arquivo entregue contém um segundo item para demonstrar repetição, cardinalidade e produtos com descrição opcional.

## 5 Estrutura hierárquica

```text
integracaoPatrimonio [versao]
├── cabecalho
│   ├── identificadorLote
│   ├── sistemaOrigem
│   ├── sistemaDestino
│   └── dataGeracao
└── vendas
    └── venda [id] 1..1000
        ├── dataVenda
        ├── status
        ├── cliente [documento]
        │   └── nome
        ├── colaborador [id]
        │   └── nome
        └── itens
            └── item [id] 1..1000
                ├── produto [sku]
                │   ├── nome
                │   └── descricao 0..1
                ├── quantidade
                ├── valorUnitario [moeda]
                └── garantiaAte 0..1
```

Os atributos são reservados a identificadores e metadados curtos. Os elementos representam dados de negócio, pois podem crescer, receber documentação e ser estendidos em versões futuras. A hierarquia evita a repetição de cliente e colaborador em cada item da mesma venda e explicita o relacionamento entre lote, venda, item e produto.

## 6 XSD formal

O XSD usa `targetNamespace="urn:uniavan:patrimonio:v1"`, `elementFormDefault="qualified"` e versão 1.0. O namespace diferencia o contrato de outros documentos XML e permite publicar uma versão futura sem tornar ambíguos os documentos existentes. A ordem dos elementos é definida com `xs:sequence`; atributos obrigatórios usam `use="required"`; coleções informam `minOccurs` e `maxOccurs`.

O elemento global é declarado como:

```xml
<xs:element name="integracaoPatrimonio"
            type="pat:IntegracaoPatrimonioType"/>
```

Antes da regra de negócio, a aplicação compila o arquivo XSD com `lxml.etree.XMLSchema` e executa `assertValid`. Portanto, o XSD não é apenas documentação: ele participa do processamento real.

## 7 Tipos simples

Tipos simples restringem um único valor textual ou numérico. Eles concentram regras reutilizáveis e tornam as mensagens de validação independentes da regra de persistência.

| Tipo | Base | Restrições | Uso |
|---|---|---|---|
| `IdentificadorType` | `xs:string` | 2 a 64 caracteres; letras, números, ponto, sublinhado e hífen | lote, venda, item e colaborador |
| `SkuType` | `xs:string` | 1 a 64 caracteres; aceita também barra | código do produto |
| `NomeType` | `xs:string` | 2 a 150 caracteres | nomes de cliente, colaborador e produto |
| `DescricaoType` | `xs:string` | 1 a 500 caracteres | descrição opcional do produto |
| `DocumentoType` | `xs:string` | somente 5 a 20 dígitos | documento do cliente |
| `QuantidadeType` | `xs:positiveInteger` | mínimo implícito 1 e máximo 10000 | unidades do item |
| `ValorMonetarioType` | `xs:decimal` | não negativo, 2 casas e até 14 dígitos | valor unitário |
| `StatusVendaType` | `xs:string` | enumeração de cinco estados concluídos | estado aceito para patrimonialização |
| `SistemaOrigemType` | `xs:string` | valor fixo `VENDAS` | origem do lote |
| `SistemaDestinoType` | `xs:string` | valor fixo `PATRIMONIO` | destino do lote |
| `MoedaType` | `xs:string` | valor fixo `BRL` | moeda do valor unitário |
| `VersaoType` | `xs:string` | padrão `1.0` | versão do contrato |

Datas usam tipos nativos do XML Schema: `xs:date` para venda e garantia e `xs:dateTime` para geração do lote. Esses tipos rejeitam datas inexistentes e formatos diferentes de ISO 8601.

## 8 Tipos complexos

Tipos complexos descrevem elementos que contêm filhos, atributos ou conteúdo simples com atributos.

| Tipo | Conteúdo principal | Decisão de modelagem |
|---|---|---|
| `CabecalhoType` | lote, origem, destino e data de geração | rastreabilidade e roteamento explícitos |
| `ClienteType` | nome e atributo documento | documento identifica; nome descreve |
| `ColaboradorType` | nome e atributo id | liga o pós-venda ao responsável usado pelo RH |
| `ProdutoType` | nome, descrição opcional e atributo SKU | SKU permanece o identificador de integração |
| `ValorComMoedaType` | decimal com atributo moeda | impede interpretar o número sem unidade monetária |
| `ItemType` | produto, quantidade, valor e garantia | reúne os dados que geram unidades patrimoniais |
| `ItensType` | um ou mais itens | explicita a coleção e sua cardinalidade |
| `VendaType` | data, estado, cliente, colaborador e itens | representa o agregado de negócio |
| `VendasType` | uma ou mais vendas | permite processar um lote |
| `IntegracaoPatrimonioType` | cabeçalho, vendas e versão | define a raiz versionada do contrato |

## 9 Fluxo de validação e processamento

1. A interface ou API recebe o XML e aplica o limite de 10 MB.
2. O parser bloqueia `DOCTYPE`, entidades externas, acesso à rede e árvores excessivamente grandes.
3. O parser verifica se o documento está bem formado.
4. O XSD verifica namespace, ordem, elementos obrigatórios, atributos, tipos, padrões, enumerações e cardinalidades.
5. O adaptador XML transforma cada `item` em um registro interno do layout Vendas para Patrimônio.
6. A regra de negócio confirma venda, SKU e quantidade, e cria uma unidade patrimonial por unidade vendida.
7. A chave externa `VENDA-{venda}-ITEM-{item}` com o número da unidade garante idempotência: o reenvio atualiza os mesmos registros.
8. Cada registro usa um ponto de salvamento isolado. Um erro de negócio pode ser auditado sem corromper os registros já válidos do lote.
9. O resultado informa inseridos, atualizados, ignorados e erros. Os dados ficam disponíveis à interface, à API de consulta e ao arquivo destinado ao RH.

Há uma separação intencional entre validação estrutural e regra de negócio. O XSD responde se o documento está no contrato; a aplicação responde se o evento pode ser aplicado ao estado atual do sistema.

## 10 Mapeamento XML para o modelo interno

| Caminho XML | Campo interno | Uso no sistema |
|---|---|---|
| `venda/@id` | `venda_external_id` | identifica a venda de origem |
| `item/@id` | `item_external_id` | compõe a chave idempotente |
| `produto/@sku` | `produto_sku` | identifica o produto |
| `produto/nome` | `produto_nome` | nome do patrimônio |
| `produto/descricao` | `produto_descricao` | descrição opcional |
| `item/quantidade` | `quantidade` | número de unidades geradas |
| `item/valorUnitario` | `valor_unitario` | valor de cada patrimônio |
| `venda/dataVenda` | `data_venda` | data do evento comercial |
| `venda/status` | `status_venda` | libera a patrimonialização |
| `cliente/@documento` | `cliente_documento` | referência do cliente |
| `cliente/nome` | `cliente_nome` | identificação legível |
| `colaborador/@id` | `colaborador_external_id` | vínculo que será consultado pelo RH |
| `colaborador/nome` | `colaborador_nome` | responsável legível |
| `item/garantiaAte` | `garantia_ate` | apoio ao atendimento pós-venda |

O mapeamento funciona como uma camada anticorrupção: nomes, atributos e
hierarquia do contrato XML são convertidos para o modelo interno antes de a
regra de patrimônio ser chamada. Assim, alterações na biblioteca XML ou na
forma de navegar pelo documento permanecem na borda da aplicação.

Os dados do cabeçalho controlam rastreabilidade e versão do lote; eles não são
misturados aos campos do patrimônio. A combinação dos identificadores de venda
e item é mantida como chave externa, permitindo repetir uma transmissão sem
criar novas unidades.

## 11 Comparação técnica entre layout CSV e XML

Nesta análise, layout significa o arquivo tabular CSV já aceito pelo sistema. Ambos os formatos continuam disponíveis porque atendem necessidades diferentes.

| Critério | Layout CSV | XML com XSD |
|---|---|---|
| Estrutura | linhas e colunas planas | árvore com relações explícitas |
| Hierarquia | exige repetição ou vários arquivos relacionados | representa lote, vendas, itens e entidades aninhadas |
| Tipagem | valores chegam como texto | XSD diferencia data, decimal, inteiro e enumeração |
| Obrigatoriedade | depende de validação programada | declarada formalmente no XSD |
| Validação externa | limitada a cabeçalhos e regras próprias | ferramentas independentes validam o contrato |
| Extensibilidade | nova coluna pode afetar leitores posicionais | elementos opcionais e namespaces permitem evolução controlada |
| Legibilidade manual | excelente para planilhas e pequenos lotes | melhor para compreender relações complexas |
| Tamanho | menor e mais econômico | maior por repetir nomes de elementos |
| Ambiguidade | delimitador, encoding e decimal podem variar | encoding, tipos e estrutura são explícitos |
| Erros | frequentemente descobertos durante a importação | muitos erros são barrados antes da regra de negócio |
| Interoperabilidade | simples, mas dependente de convenções | padrão formal, autodescritivo e amplamente suportado |

O CSV continua indicado para operação manual, conferência em planilha e integrações simples. O XML é preferível quando a hierarquia e a validação formal são requisitos de entrega ou quando diferentes equipes precisam implementar o mesmo contrato sem acessar o código do sistema.

## 12 Flexibilidade e estratégia de evolução

Flexibilidade não significa aceitar qualquer estrutura. O contrato permite vários lotes, vendas e itens, uma descrição e uma garantia opcionais e diferentes estados concluídos. Ao mesmo tempo, mantém obrigatórios os dados necessários à rastreabilidade: identificadores, SKU, quantidade, valor, cliente e colaborador.

Mudanças compatíveis, como adicionar um elemento opcional ao final de uma sequência planejada, podem ser publicadas com revisão documentada. Mudanças incompatíveis, como renomear elementos, alterar significado, tornar um campo obrigatório ou aceitar novos tipos de evento, devem usar um novo namespace, por exemplo `urn:uniavan:patrimonio:v2`. O sistema pode manter adaptadores v1 e v2 durante a migração.

## 13 Análise de acoplamento

**Acoplamento de dados e sintaxe.** O produtor precisa conhecer o XSD, o namespace e os valores enumerados. Esse é um acoplamento contratual deliberado: mais rígido que um CSV permissivo, mas visível, testável e versionável. O adaptador XML impede que essa sintaxe se espalhe pelas regras internas.

**Acoplamento semântico.** Vendas e Patrimônio precisam concordar sobre o que é uma venda concluída, uma quantidade, um SKU, um colaborador e uma garantia. Esse acoplamento não pode ser eliminado por trocar o formato. Ele é reduzido com nomes explícitos, enumerações e documentação de cada decisão.

**Acoplamento temporal.** A importação por arquivo é assíncrona: os sistemas não precisam estar disponíveis simultaneamente. O POST pela API é síncrono e exige que Patrimônio esteja acessível no momento do envio. Manter os dois canais reduz dependência operacional.

**Acoplamento de plataforma.** XML, XSD e HTTP são padrões independentes de linguagem e banco. O sistema de Vendas pode usar qualquer tecnologia capaz de gerar XML. Não há acesso direto ao SQLite nem compartilhamento de classes Python.

**Acoplamento por persistência.** O banco pertence ao Sistema de Patrimônio. Sistemas externos usam apenas o contrato e as rotas públicas. Essa separação permite mudar tabelas e consultas internas sem alterar o XML, desde que o adaptador preserve o comportamento contratado.

**Acoplamento de versão.** O namespace e o atributo `versao` tornam a versão explícita. O XSD possui nome versionado e deve ser distribuído junto do modelo. Consumidores podem rejeitar versões desconhecidas em vez de interpretar dados silenciosamente.

O resultado é acoplamento baixo na tecnologia e na persistência, médio no tempo quando a API é usada e intencionalmente forte no contrato e no significado dos dados. Para interoperabilidade, esse perfil é mais seguro do que depender de convenções informais.

## 14 Segurança e robustez

- O parser não resolve entidades externas, não carrega DTD e não acessa a rede.
- Documentos com `DOCTYPE` são rejeitados para reduzir risco de XXE.
- O tamanho de entrada é limitado a 10 MB e o lote processa no máximo 1000 itens.
- Quantidades são positivas e limitadas; valores não podem ser negativos.
- O XML inteiro passa pelo XSD antes da primeira gravação.
- Registros são processados com transação, pontos de salvamento e log de integração.
- A idempotência evita duplicidade quando o mesmo evento é reenviado.
- O sistema devolve erro de validação sem expor instruções SQL ou detalhes do banco.

Autenticação e criptografia de transporte devem ser adicionadas antes de exposição em ambiente público. Na demonstração acadêmica em rede local ou VPN, o contrato e a validação estão implementados, mas HTTPS e credenciais por sistema continuam recomendações para produção.

## 15 Evidências de validação e testes

A suíte automatizada executa seis cenários e foi concluída sem falhas:

1. renderização das telas principais;
2. importação ZIP de Vendas com reenvio idempotente;
3. API JSON de Vendas e saída para RH;
4. exportações CSV existentes;
5. XML válido, importação pela interface, reenvio pela API e exportação validada pelo XSD;
6. XML inválido com status `PENDENTE`, rejeitado com HTTP 422 antes de qualquer gravação.

No caso válido, o modelo contém dois itens e quantidade total igual a três. A primeira importação gera três patrimônios. O reenvio atualiza os três registros existentes. O XML exportado é novamente validado pelo arquivo `patrimonio-vendas-v1.xsd`, comprovando que entrada e saída obedecem ao contrato.

Como evidência visual adicional, o mesmo validador foi executado duas vezes. Na primeira execução, o modelo original foi aceito. Na segunda, uma cópia recebeu propositalmente `<quantidade>banana</quantidade>`. O XSD rejeitou o documento porque `QuantidadeType` deriva de `xs:positiveInteger`, demonstrando que a validação detecta violações de tipo antes do processamento.

## 16 Como executar a demonstração

1. Inicie o sistema com `iniciar.bat` e faça login.
2. Abra `/importacao`.
3. Baixe o modelo XML e o XSD nos links da tela.
4. Selecione `modelo-vendas-patrimonio.xml` e processe a importação.
5. Confira o resumo com três novos patrimônios e abra a lista de patrimônios.
6. Volte à integração e use `Exportar XML`.
7. Para demonstrar a falha, altere o status para `PENDENTE`; o sistema exibirá a linha e a regra do XSD violada, sem inserir dados.

Exemplo de chamada pela API no PowerShell:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/integracao/vendas/patrimonios.xml `
  -Method Post `
  -ContentType application/xml `
  -InFile .\integracao_xml\modelo-vendas-patrimonio.xml
```

## 17 Conclusão

A integração XML está operacional e validada por um XSD formal. O contrato representa corretamente a hierarquia do negócio, usa tipos simples e complexos reutilizáveis, impede estruturas inválidas e preserva a regra idempotente do sistema. A abordagem mantém compatibilidade com os formatos existentes e adiciona uma interface mais rigorosa para interoperabilidade entre equipes. O XSD versionado reduz ambiguidades; o adaptador reduz impacto sobre o domínio; e a ausência de acesso direto ao banco mantém os sistemas independentes em tecnologia e persistência.
