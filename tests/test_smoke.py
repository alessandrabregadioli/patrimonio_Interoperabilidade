import csv
import io
import tempfile
import unittest
from pathlib import Path

import app as application


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


if __name__ == "__main__":
    unittest.main()
