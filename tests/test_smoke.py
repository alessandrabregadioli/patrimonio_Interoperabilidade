import csv
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import app as application
from lxml import etree


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SistemaPatrimonioSmokeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        application.DB_PATH = Path(self.temp_dir.name) / "patrimonio-teste.db"
        application.init_db()
        application.app.config.update(TESTING=True)
        self.client = application.app.test_client()
        resposta = self.client.post(
            "/login",
            data={"email": "admin@mercado.com", "senha": "123456"},
            follow_redirects=True,
        )
        self.assertEqual(resposta.status_code, 200)

    def tearDown(self):
        self.temp_dir.cleanup()

    def importar(self, caminho):
        conteudo = caminho.read_bytes()
        return self.client.post(
            "/importacao",
            data={"arquivo": (io.BytesIO(conteudo), caminho.name)},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    def test_telas_principais_renderizam(self):
        rotas = [
            "/", "/patrimonios", "/patrimonios/novo", "/categorias",
            "/setores", "/movimentacoes", "/manutencoes", "/importacao",
            "/usuarios",
        ]
        for rota in rotas:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)

    def test_zip_vendas_e_idempotente(self):
        pacote = PROJECT_ROOT / "exemplos_integracao" / "vendas_pacote_exemplo.zip"
        primeira = self.importar(pacote)
        self.assertEqual(primeira.status_code, 200)
        vendas = self.client.get("/api/integracao/vendas/patrimonios").get_json()
        self.assertEqual(len(vendas), 10)

        segunda = self.importar(pacote)
        self.assertEqual(segunda.status_code, 200)
        vendas_reimportadas = self.client.get(
            "/api/integracao/vendas/patrimonios"
        ).get_json()
        self.assertEqual(len(vendas_reimportadas), 10)

    def test_api_vendas_e_saida_rh(self):
        venda = {
            "venda_external_id": "VEN-TESTE-001",
            "item_external_id": "ITEM-01",
            "produto_sku": "SKU-TESTE",
            "produto_nome": "Produto de teste",
            "quantidade": 2,
            "status_venda": "FATURADO",
            "cliente_documento": "12345678901",
            "cliente_nome": "Cliente de teste",
            "colaborador_external_id": "COL-01",
            "colaborador_nome": "Colaborador de teste",
        }
        primeira = self.client.post(
            "/api/integracao/vendas/patrimonios", json=venda
        )
        self.assertEqual(primeira.status_code, 201)
        self.assertEqual(primeira.get_json()["inseridos"], 2)

        segunda = self.client.post(
            "/api/integracao/vendas/patrimonios", json=venda
        )
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.get_json()["atualizados"], 2)

        responsabilidades = self.client.get(
            "/api/integracao/rh/responsabilidades"
        ).get_json()
        self.assertEqual(len(responsabilidades), 2)
        self.assertEqual(
            responsabilidades[0]["tipo_responsabilidade"],
            "POS_VENDA_PATRIMONIO",
        )

        exportacao_rh = self.client.get("/exportacao/rh_colaboradores.csv")
        conteudo_rh = exportacao_rh.data.decode("utf-8-sig")
        linhas_rh = list(csv.DictReader(io.StringIO(conteudo_rh), delimiter=";"))
        self.assertEqual(len(linhas_rh), 2)
        self.assertEqual(
            list(linhas_rh[0].keys()),
            [
                "id_evento", "id_colaborador", "data_evento", "tipo_evento",
                "descricao", "status_evento",
            ],
        )
        self.assertEqual(linhas_rh[0]["id_colaborador"], "COL-01")
        self.assertEqual(linhas_rh[0]["tipo_evento"], "ATENDIMENTO")
        self.assertEqual(linhas_rh[0]["status_evento"], "CONCLUIDO")

    def test_exportacoes_csv(self):
        for rota in [
            "/exportacao/patrimonios.csv",
            "/exportacao/rh_colaboradores.csv",
            "/exportacao/movimentacoes.csv",
            "/exportacao/logs.csv",
        ]:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.data.startswith(b"\xef\xbb\xbf"))

    def test_xml_xsd_importacao_api_e_exportacao(self):
        caminho_xml = (
            PROJECT_ROOT / "integracao_xml" / "modelo-vendas-patrimonio.xml"
        )
        caminho_xsd = PROJECT_ROOT / "integracao_xml" / "patrimonio-vendas-v1.xsd"
        schema = etree.XMLSchema(etree.parse(str(caminho_xsd)))
        self.assertTrue(schema.validate(etree.parse(str(caminho_xml))))

        primeira = self.importar(caminho_xml)
        self.assertEqual(primeira.status_code, 200)
        vendas = self.client.get("/api/integracao/vendas/patrimonios").get_json()
        self.assertEqual(len(vendas), 3)

        segunda = self.client.post(
            "/api/integracao/vendas/patrimonios.xml",
            data=caminho_xml.read_bytes(),
            content_type="application/xml",
        )
        self.assertEqual(segunda.status_code, 200)
        self.assertTrue(segunda.get_json()["valido_xsd"])
        self.assertEqual(segunda.get_json()["atualizados"], 3)

        exportacao = self.client.get("/api/integracao/vendas/patrimonios.xml")
        self.assertEqual(exportacao.status_code, 200)
        self.assertEqual(exportacao.mimetype, "application/xml")
        self.assertTrue(schema.validate(etree.fromstring(exportacao.data)))

        for rota, nome in [
            ("/importacao/modelo.xml", "modelo-vendas-patrimonio.xml"),
            ("/importacao/esquema.xsd", "patrimonio-vendas-v1.xsd"),
        ]:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn("attachment", resposta.headers["Content-Disposition"])
                self.assertIn(nome, resposta.headers["Content-Disposition"])
                resposta.close()

        pacote_resposta = self.client.get("/importacao/pacote-xml.zip")
        self.assertEqual(pacote_resposta.status_code, 200)
        self.assertIn("attachment", pacote_resposta.headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(pacote_resposta.data)) as pacote:
            self.assertEqual(
                set(pacote.namelist()),
                {"modelo-vendas-patrimonio.xml", "patrimonio-vendas-v1.xsd"},
            )
        pacote_resposta.close()

    def test_xml_invalido_e_rejeitado_antes_de_gravar(self):
        caminho_xml = (
            PROJECT_ROOT / "integracao_xml" / "modelo-vendas-patrimonio.xml"
        )
        xml_invalido = caminho_xml.read_bytes().replace(
            b"<status>FATURADO</status>", b"<status>PENDENTE</status>"
        )
        resposta = self.client.post(
            "/api/integracao/vendas/patrimonios.xml",
            data=xml_invalido,
            content_type="application/xml",
        )
        self.assertEqual(resposta.status_code, 422)
        self.assertFalse(resposta.get_json()["valido_xsd"])
        vendas = self.client.get("/api/integracao/vendas/patrimonios").get_json()
        self.assertEqual(vendas, [])


if __name__ == "__main__":
    unittest.main()
