# Contrato XML Vendas para Patrimônio

Esta pasta contém a versão 1.0 do contrato XML usado pelo Sistema de SAC e Patrimônio.

- `modelo-vendas-patrimonio.xml`: instância completa e válida.
- `patrimonio-vendas-v1.xsd`: esquema formal de validação.

## Validar localmente

Com o ambiente virtual do projeto ativo:

```powershell
python -c "from lxml import etree; s=etree.XMLSchema(etree.parse('integracao_xml/patrimonio-vendas-v1.xsd')); d=etree.parse('integracao_xml/modelo-vendas-patrimonio.xml'); print(s.validate(d)); print(s.error_log)"
```

O resultado esperado é `True`.

## Enviar pela API

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/integracao/vendas/patrimonios.xml `
  -Method Post `
  -ContentType application/xml `
  -InFile .\integracao_xml\modelo-vendas-patrimonio.xml
```

O endpoint de saída é `GET /api/integracao/vendas/patrimonios.xml`.
