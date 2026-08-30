from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
import sqlite3
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile

app = Flask(__name__)
app.secret_key = "chave-academica-patrimonio-mercado"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "patrimonio.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        perfil TEXT NOT NULL DEFAULT 'ADMIN'
    );

    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS setores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS patrimonios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo TEXT UNIQUE NOT NULL,
        nome TEXT NOT NULL,
        descricao TEXT,
        marca TEXT,
        modelo TEXT,
        numero_serie TEXT,
        data_aquisicao TEXT,
        valor REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ATIVO',
        categoria_id INTEGER,
        setor_id INTEGER,
        origem_sistema TEXT NOT NULL DEFAULT 'Manual',
        produto_sku TEXT,
        external_id TEXT,
        unidade_origem INTEGER,
        venda_external_id TEXT,
        cliente_documento TEXT,
        cliente_nome TEXT,
        colaborador_external_id TEXT,
        colaborador_nome TEXT,
        data_venda TEXT,
        garantia_ate TEXT,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (categoria_id) REFERENCES categorias(id),
        FOREIGN KEY (setor_id) REFERENCES setores(id)
    );

    CREATE TABLE IF NOT EXISTS movimentacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patrimonio_id INTEGER NOT NULL,
        setor_origem_id INTEGER,
        setor_destino_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        observacao TEXT,
        usuario_id INTEGER,
        FOREIGN KEY (patrimonio_id) REFERENCES patrimonios(id),
        FOREIGN KEY (setor_origem_id) REFERENCES setores(id),
        FOREIGN KEY (setor_destino_id) REFERENCES setores(id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    );

    CREATE TABLE IF NOT EXISTS manutencoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patrimonio_id INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        data_inicio TEXT NOT NULL,
        data_fim TEXT,
        custo REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'ABERTA',
        FOREIGN KEY (patrimonio_id) REFERENCES patrimonios(id)
    );
    
    CREATE TABLE IF NOT EXISTS importacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        arquivo TEXT NOT NULL,
        formato TEXT NOT NULL,
        total INTEGER NOT NULL DEFAULT 0,
        inseridos INTEGER NOT NULL DEFAULT 0,
        atualizados INTEGER NOT NULL DEFAULT 0,
        ignorados INTEGER NOT NULL DEFAULT 0,
        erros INTEGER NOT NULL DEFAULT 0,
        data TEXT NOT NULL,
        usuario_id INTEGER,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    );

    CREATE TABLE IF NOT EXISTS integracao_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT,
        sistema_origem TEXT NOT NULL,
        sistema_destino TEXT NOT NULL DEFAULT 'PATRIMONIO',
        arquivo TEXT,
        tipo_registro TEXT NOT NULL,
        operacao TEXT NOT NULL,
        status TEXT NOT NULL,
        mensagem TEXT,
        patrimonio_id INTEGER,
        criado_em TEXT NOT NULL,
        usuario_id INTEGER,
        FOREIGN KEY (patrimonio_id) REFERENCES patrimonios(id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    );
    """)

    # Atualiza bancos antigos sem apagar os dados já cadastrados.
    colunas_patrimonio = [
        linha["name"] for linha in conn.execute("PRAGMA table_info(patrimonios)").fetchall()
    ]
    if "origem_sistema" not in colunas_patrimonio:
        conn.execute(
            "ALTER TABLE patrimonios ADD COLUMN origem_sistema TEXT NOT NULL DEFAULT 'Manual'"
        )

    migracoes_patrimonio = {
        "produto_sku": "TEXT",
        "external_id": "TEXT",
        "unidade_origem": "INTEGER",
        "venda_external_id": "TEXT",
        "cliente_documento": "TEXT",
        "cliente_nome": "TEXT",
        "colaborador_external_id": "TEXT",
        "colaborador_nome": "TEXT",
        "data_venda": "TEXT",
        "garantia_ate": "TEXT",
    }
    for coluna, definicao in migracoes_patrimonio.items():
        if coluna not in colunas_patrimonio:
            conn.execute(f"ALTER TABLE patrimonios ADD COLUMN {coluna} {definicao}")

    colunas_importacao = [
        linha["name"] for linha in conn.execute("PRAGMA table_info(importacoes)").fetchall()
    ]
    if "ignorados" not in colunas_importacao:
        conn.execute(
            "ALTER TABLE importacoes ADD COLUMN ignorados INTEGER NOT NULL DEFAULT 0"
        )

    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_patrimonio_integracao
        ON patrimonios (origem_sistema, external_id, unidade_origem)
        WHERE external_id IS NOT NULL AND external_id != ''
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS ix_integracao_logs_external
        ON integracao_logs (sistema_origem, external_id, operacao, status)
    """)

    if not conn.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
            ("Administrador", "admin@mercado.com", generate_password_hash("123456"), "ADMIN")
        )

    categorias = ["Informática", "Móveis", "Refrigeração", "Equipamentos", "Segurança"]
    for nome in categorias:
        conn.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (nome,))

    setores = ["Administrativo", "Caixas", "Açougue", "Padaria", "Estoque", "Depósito"]
    for nome in setores:
        conn.execute("INSERT OR IGNORE INTO setores (nome) VALUES (?)", (nome,))

    if not conn.execute("SELECT 1 FROM patrimonios LIMIT 1").fetchone():
        cat_info = conn.execute("SELECT id FROM categorias WHERE nome='Informática'").fetchone()["id"]
        cat_ref = conn.execute("SELECT id FROM categorias WHERE nome='Refrigeração'").fetchone()["id"]
        set_adm = conn.execute("SELECT id FROM setores WHERE nome='Administrativo'").fetchone()["id"]
        set_ac = conn.execute("SELECT id FROM setores WHERE nome='Açougue'").fetchone()["id"]
        conn.execute("""
            INSERT INTO patrimonios
            (codigo, nome, descricao, marca, modelo, numero_serie, data_aquisicao, valor, status, categoria_id, setor_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("PAT-001", "Computador Administrativo", "Computador do setor administrativo",
              "Dell", "OptiPlex", "SN001", "2026-01-10", 3200.00, "ATIVO", cat_info, set_adm))
        conn.execute("""
            INSERT INTO patrimonios
            (codigo, nome, descricao, marca, modelo, numero_serie, data_aquisicao, valor, status, categoria_id, setor_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("PAT-002", "Freezer Horizontal", "Freezer do açougue",
              "Metalfrio", "DA550", "SN002", "2025-11-15", 5900.00, "MANUTENCAO", cat_ref, set_ac))

    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("usuario_perfil") != "ADMIN":
            flash("Acesso permitido apenas para administradores.", "erro")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        conn = get_db()
        usuario = conn.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
        conn.close()
        if usuario and check_password_hash(usuario["senha"], senha):
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            session["usuario_perfil"] = usuario["perfil"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha inválidos.", "erro")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS qtd FROM patrimonios").fetchone()["qtd"]
    ativos = conn.execute("SELECT COUNT(*) AS qtd FROM patrimonios WHERE status='ATIVO'").fetchone()["qtd"]
    manutencao = conn.execute("SELECT COUNT(*) AS qtd FROM patrimonios WHERE status='MANUTENCAO'").fetchone()["qtd"]
    baixados = conn.execute("SELECT COUNT(*) AS qtd FROM patrimonios WHERE status='BAIXADO'").fetchone()["qtd"]
    pendentes = conn.execute("SELECT COUNT(*) AS qtd FROM patrimonios WHERE status='PENDENTE'").fetchone()["qtd"]
    valor_total = conn.execute("SELECT COALESCE(SUM(valor),0) AS total FROM patrimonios WHERE status != 'BAIXADO'").fetchone()["total"]
    recentes = conn.execute("""
        SELECT p.*, c.nome AS categoria, s.nome AS setor
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id = p.categoria_id
        LEFT JOIN setores s ON s.id = p.setor_id
        ORDER BY p.id DESC LIMIT 5
    """).fetchall()
    atividades_integracao = conn.execute("""
        SELECT l.*, p.codigo AS codigo_patrimonio
        FROM integracao_logs l
        LEFT JOIN patrimonios p ON p.id=l.patrimonio_id
        ORDER BY l.id DESC LIMIT 4
    """).fetchall()
    ultima_integracao = conn.execute("""
        SELECT data, arquivo, formato, inseridos, atualizados, ignorados, erros
        FROM importacoes
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    return render_template(
        "dashboard.html", total=total, ativos=ativos, manutencao=manutencao,
        baixados=baixados, pendentes=pendentes, valor_total=valor_total,
        recentes=recentes, atividades_integracao=atividades_integracao,
        ultima_integracao=ultima_integracao,
        agora=datetime.now().strftime("%d/%m/%Y %H:%M")
    )


@app.route("/patrimonios")
@login_required
def patrimonios():
    busca = request.args.get("busca", "").strip()
    status_filtro = request.args.get("status", "").strip().upper()
    setor_filtro = request.args.get("setor", "").strip()
    conn = get_db()
    filtros = []
    parametros = []
    if busca:
        termo = f"%{busca}%"
        filtros.append("""(
            p.codigo LIKE ? OR p.nome LIKE ? OR p.marca LIKE ? OR
            p.produto_sku LIKE ? OR p.colaborador_nome LIKE ? OR
            c.nome LIKE ? OR s.nome LIKE ?
        )""")
        parametros.extend([termo] * 7)
    if status_filtro:
        filtros.append("p.status=?")
        parametros.append(status_filtro)
    if setor_filtro:
        filtros.append("CAST(p.setor_id AS TEXT)=?")
        parametros.append(setor_filtro)

    where = " WHERE " + " AND ".join(filtros) if filtros else ""
    itens = conn.execute(f"""
        SELECT p.*, c.nome AS categoria, s.nome AS setor
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id = p.categoria_id
        LEFT JOIN setores s ON s.id = p.setor_id
        {where}
        ORDER BY p.id DESC
    """, parametros).fetchall()
    resumo = conn.execute("""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='ATIVO' THEN 1 ELSE 0 END) AS ativos,
               SUM(CASE WHEN status='MANUTENCAO' THEN 1 ELSE 0 END) AS manutencao,
               COALESCE(SUM(CASE WHEN status!='BAIXADO' THEN valor ELSE 0 END), 0) AS valor_total
        FROM patrimonios
    """).fetchone()
    setores_filtro = conn.execute("SELECT id, nome FROM setores ORDER BY nome").fetchall()
    conn.close()
    return render_template(
        "patrimonios.html", itens=itens, busca=busca,
        status_filtro=status_filtro, setor_filtro=setor_filtro,
        resumo=resumo, setores_filtro=setores_filtro,
    )


def carregar_opcoes(conn):
    categorias = conn.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    setores = conn.execute("SELECT * FROM setores ORDER BY nome").fetchall()
    return categorias, setores


@app.route("/patrimonios/novo", methods=["GET", "POST"])
@login_required
def patrimonio_novo():
    conn = get_db()
    categorias, setores = carregar_opcoes(conn)
    if request.method == "POST":
        try:
            conn.execute("""
                INSERT INTO patrimonios
                (codigo, nome, descricao, marca, modelo, numero_serie, data_aquisicao,
                 valor, status, categoria_id, setor_id, produto_sku, venda_external_id,
                 cliente_documento, cliente_nome, colaborador_external_id,
                 colaborador_nome, data_venda, garantia_ate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form["codigo"].strip(),
                request.form["nome"].strip(),
                request.form.get("descricao", "").strip(),
                request.form.get("marca", "").strip(),
                request.form.get("modelo", "").strip(),
                request.form.get("numero_serie", "").strip(),
                request.form.get("data_aquisicao") or None,
                float(request.form.get("valor") or 0),
                request.form.get("status", "ATIVO"),
                request.form.get("categoria_id") or None,
                request.form.get("setor_id") or None,
                request.form.get("produto_sku", "").strip() or None,
                request.form.get("venda_external_id", "").strip() or None,
                request.form.get("cliente_documento", "").strip() or None,
                request.form.get("cliente_nome", "").strip() or None,
                request.form.get("colaborador_external_id", "").strip() or None,
                request.form.get("colaborador_nome", "").strip() or None,
                request.form.get("data_venda") or None,
                request.form.get("garantia_ate") or None,
            ))
            conn.commit()
            flash("Patrimônio cadastrado com sucesso.", "sucesso")
            return redirect(url_for("patrimonios"))
        except sqlite3.IntegrityError:
            flash("Já existe um patrimônio com esse código.", "erro")
    conn.close()
    return render_template("patrimonio_form.html", item=None, categorias=categorias, setores=setores)


@app.route("/patrimonios/<int:id>/editar", methods=["GET", "POST"])
@login_required
def patrimonio_editar(id):
    conn = get_db()
    item = conn.execute("SELECT * FROM patrimonios WHERE id=?", (id,)).fetchone()
    if not item:
        conn.close()
        return "Patrimônio não encontrado", 404

    categorias, setores = carregar_opcoes(conn)
    if request.method == "POST":
        try:
            conn.execute("""
                UPDATE patrimonios SET
                    codigo=?, nome=?, descricao=?, marca=?, modelo=?, numero_serie=?,
                    data_aquisicao=?, valor=?, status=?, categoria_id=?, setor_id=?
                    , produto_sku=?, venda_external_id=?, cliente_documento=?,
                    cliente_nome=?, colaborador_external_id=?, colaborador_nome=?,
                    data_venda=?, garantia_ate=?
                WHERE id=?
            """, (
                request.form["codigo"].strip(),
                request.form["nome"].strip(),
                request.form.get("descricao", "").strip(),
                request.form.get("marca", "").strip(),
                request.form.get("modelo", "").strip(),
                request.form.get("numero_serie", "").strip(),
                request.form.get("data_aquisicao") or None,
                float(request.form.get("valor") or 0),
                request.form.get("status", "ATIVO"),
                request.form.get("categoria_id") or None,
                request.form.get("setor_id") or None,
                request.form.get("produto_sku", "").strip() or None,
                request.form.get("venda_external_id", "").strip() or None,
                request.form.get("cliente_documento", "").strip() or None,
                request.form.get("cliente_nome", "").strip() or None,
                request.form.get("colaborador_external_id", "").strip() or None,
                request.form.get("colaborador_nome", "").strip() or None,
                request.form.get("data_venda") or None,
                request.form.get("garantia_ate") or None,
                id
            ))
            conn.commit()
            flash("Patrimônio atualizado.", "sucesso")
            return redirect(url_for("patrimonios"))
        except sqlite3.IntegrityError:
            flash("Já existe outro patrimônio com esse código.", "erro")
    conn.close()
    return render_template("patrimonio_form.html", item=item, categorias=categorias, setores=setores)


@app.post("/patrimonios/<int:id>/baixar")
@login_required
def patrimonio_baixar(id):
    conn = get_db()
    conn.execute("UPDATE patrimonios SET status='BAIXADO' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Patrimônio baixado.", "sucesso")
    return redirect(url_for("patrimonios"))


@app.route("/categorias", methods=["GET", "POST"])
@login_required
def categorias():
    conn = get_db()
    if request.method == "POST":
        nome = request.form["nome"].strip()
        if nome:
            try:
                conn.execute("INSERT INTO categorias (nome) VALUES (?)", (nome,))
                conn.commit()
                flash("Categoria cadastrada.", "sucesso")
            except sqlite3.IntegrityError:
                flash("Essa categoria já existe.", "erro")
        return redirect(url_for("categorias"))
    itens = conn.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    conn.close()
    return render_template("cadastro_simples.html", titulo="Categorias", itens=itens, rota="categorias")


@app.route("/setores", methods=["GET", "POST"])
@login_required
def setores():
    conn = get_db()
    if request.method == "POST":
        nome = request.form["nome"].strip()
        if nome:
            try:
                conn.execute("INSERT INTO setores (nome) VALUES (?)", (nome,))
                conn.commit()
                flash("Setor cadastrado.", "sucesso")
            except sqlite3.IntegrityError:
                flash("Esse setor já existe.", "erro")
        return redirect(url_for("setores"))
    itens = conn.execute("SELECT * FROM setores ORDER BY nome").fetchall()
    conn.close()
    return render_template("cadastro_simples.html", titulo="Setores", itens=itens, rota="setores")


@app.route("/movimentacoes", methods=["GET", "POST"])
@login_required
def movimentacoes():
    conn = get_db()
    if request.method == "POST":
        patrimonio_id = int(request.form["patrimonio_id"])
        destino_id = int(request.form["setor_destino_id"])
        atual = conn.execute("SELECT setor_id FROM patrimonios WHERE id=?", (patrimonio_id,)).fetchone()
        origem_id = atual["setor_id"] if atual else None

        conn.execute("""
            INSERT INTO movimentacoes
            (patrimonio_id, setor_origem_id, setor_destino_id, data, observacao, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            patrimonio_id, origem_id, destino_id,
            request.form.get("data") or datetime.now().strftime("%Y-%m-%d"),
            request.form.get("observacao", "").strip(),
            session.get("usuario_id")
        ))
        conn.execute("UPDATE patrimonios SET setor_id=? WHERE id=?", (destino_id, patrimonio_id))
        conn.commit()
        flash("Movimentação registrada.", "sucesso")
        return redirect(url_for("movimentacoes"))

    patrimonios_lista = conn.execute("SELECT id, codigo, nome FROM patrimonios WHERE status != 'BAIXADO' ORDER BY nome").fetchall()
    setores_lista = conn.execute("SELECT * FROM setores ORDER BY nome").fetchall()
    itens = conn.execute("""
        SELECT m.*, p.codigo, p.nome AS patrimonio,
               so.nome AS origem, sd.nome AS destino, u.nome AS usuario
        FROM movimentacoes m
        JOIN patrimonios p ON p.id=m.patrimonio_id
        LEFT JOIN setores so ON so.id=m.setor_origem_id
        JOIN setores sd ON sd.id=m.setor_destino_id
        LEFT JOIN usuarios u ON u.id=m.usuario_id
        ORDER BY m.id DESC
    """).fetchall()
    conn.close()
    return render_template("movimentacoes.html", itens=itens, patrimonios=patrimonios_lista, setores=setores_lista)


@app.route("/manutencoes", methods=["GET", "POST"])
@login_required
def manutencoes():
    conn = get_db()
    if request.method == "POST":
        patrimonio_id = int(request.form["patrimonio_id"])
        status = request.form.get("status", "ABERTA")
        conn.execute("""
            INSERT INTO manutencoes
            (patrimonio_id, descricao, data_inicio, data_fim, custo, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            patrimonio_id,
            request.form["descricao"].strip(),
            request.form.get("data_inicio") or datetime.now().strftime("%Y-%m-%d"),
            request.form.get("data_fim") or None,
            float(request.form.get("custo") or 0),
            status
        ))
        if status != "CONCLUIDA":
            conn.execute("UPDATE patrimonios SET status='MANUTENCAO' WHERE id=?", (patrimonio_id,))
        conn.commit()
        flash("Manutenção registrada.", "sucesso")
        return redirect(url_for("manutencoes"))

    patrimonios_lista = conn.execute("SELECT id, codigo, nome FROM patrimonios WHERE status != 'BAIXADO' ORDER BY nome").fetchall()
    itens = conn.execute("""
        SELECT m.*, p.codigo, p.nome AS patrimonio
        FROM manutencoes m
        JOIN patrimonios p ON p.id=m.patrimonio_id
        ORDER BY m.id DESC
    """).fetchall()
    conn.close()
    return render_template("manutencoes.html", itens=itens, patrimonios=patrimonios_lista)


@app.post("/manutencoes/<int:id>/concluir")
@login_required
def manutencao_concluir(id):
    conn = get_db()
    m = conn.execute("SELECT * FROM manutencoes WHERE id=?", (id,)).fetchone()
    if m:
        conn.execute(
            "UPDATE manutencoes SET status='CONCLUIDA', data_fim=COALESCE(data_fim, ?) WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d"), id)
        )
        conn.execute("UPDATE patrimonios SET status='ATIVO' WHERE id=?", (m["patrimonio_id"],))
        conn.commit()
        flash("Manutenção concluída.", "sucesso")
    conn.close()
    return redirect(url_for("manutencoes"))


@app.route("/usuarios", methods=["GET", "POST"])
@admin_required
def usuarios():
    conn = get_db()

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        perfil = request.form.get("perfil", "FUNCIONARIO")

        if not nome or not email or not senha:
            flash("Preencha nome, e-mail e senha.", "erro")
            conn.close()
            return redirect(url_for("usuarios"))

        if perfil not in ("ADMIN", "FUNCIONARIO"):
            perfil = "FUNCIONARIO"

        try:
            conn.execute(
                "INSERT INTO usuarios (nome, email, senha, perfil) VALUES (?, ?, ?, ?)",
                (nome, email, generate_password_hash(senha), perfil)
            )
            conn.commit()
            flash("Usuário cadastrado com sucesso.", "sucesso")
        except sqlite3.IntegrityError:
            flash("Já existe um usuário com esse e-mail.", "erro")

        conn.close()
        return redirect(url_for("usuarios"))

    itens = conn.execute(
        "SELECT id, nome, email, perfil FROM usuarios ORDER BY nome"
    ).fetchall()
    conn.close()
    return render_template("usuarios.html", itens=itens)


@app.post("/usuarios/<int:id>/excluir")
@admin_required
def usuario_excluir(id):
    if id == session.get("usuario_id"):
        flash("Você não pode excluir o usuário que está conectado.", "erro")
        return redirect(url_for("usuarios"))

    conn = get_db()
    conn.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Usuário excluído.", "sucesso")
    return redirect(url_for("usuarios"))




# ---------------------------
# IMPORTAÇÃO / INTEGRAÇÃO
# ---------------------------

def chave_normalizada(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.replace(" ", "_").replace("-", "_")


def normalizar_linha(linha):
    """Aceita pequenas variações nos nomes das colunas vindas de outros sistemas."""
    bruto = {chave_normalizada(k): v for k, v in linha.items() if k is not None}

    aliases = {
        "codigo": ["codigo", "codigo_patrimonio", "cod_patrimonio", "patrimonio_codigo"],
        "nome": ["nome", "nome_patrimonio", "patrimonio", "item"],
        "descricao": ["descricao", "descricao_item"],
        "marca": ["marca"],
        "modelo": ["modelo"],
        "numero_serie": ["numero_serie", "n_serie", "serie"],
        "data_aquisicao": ["data_aquisicao", "aquisicao", "data_compra"],
        "valor": ["valor", "valor_aquisicao", "preco"],
        "status": ["status", "situacao"],
        "categoria": ["categoria", "nome_categoria"],
        "setor": ["setor", "nome_setor", "localizacao"],
        "origem_sistema": ["origem_sistema", "origem", "sistema_origem"],
        "produto_sku": ["produto_sku", "sku", "codigo_produto"],
        "external_id": ["external_id", "id_externo", "id_origem"],
        "unidade_origem": ["unidade_origem", "numero_unidade"],
        "venda_external_id": ["venda_external_id", "id_venda", "id_pedido", "pedido_id"],
        "cliente_documento": ["cliente_documento", "cpf_cnpj", "cliente_cpf", "cliente_cnpj"],
        "cliente_nome": ["cliente_nome", "nome_cliente"],
        "colaborador_external_id": ["colaborador_external_id", "id_vendedor", "vendedor_id", "colaborador_id"],
        "colaborador_nome": ["colaborador_nome", "nome_vendedor", "vendedor_nome", "responsavel_nome"],
        "data_venda": ["data_venda", "data_pedido"],
        "garantia_ate": ["garantia_ate", "data_garantia", "validade_do_produto"],
    }

    resultado = {}
    for campo, opcoes in aliases.items():
        for opcao in opcoes:
            if opcao in bruto:
                resultado[campo] = bruto[opcao]
                break

    return resultado


def converter_valor(valor):
    if valor in (None, ""):
        return 0.0

    texto = str(valor).strip().replace("R$", "").replace(" ", "")

    # Exemplos aceitos: 3500.50 / 3500,50 / 3.500,50
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    return float(texto)


def normalizar_status(status):
    status = chave_normalizada(status).upper()

    mapa = {
        "": "ATIVO",
        "ATIVO": "ATIVO",
        "EM_USO": "ATIVO",
        "PENDENTE": "PENDENTE",
        "AGUARDANDO_PATRIMONIALIZACAO": "PENDENTE",
        "VENDIDO": "VENDIDO",
        "FATURADO": "VENDIDO",
        "MANUTENCAO": "MANUTENCAO",
        "EM_MANUTENCAO": "MANUTENCAO",
        "DANIFICADO": "DANIFICADO",
        "BAIXADO": "BAIXADO",
        "INATIVO": "BAIXADO",
    }

    return mapa.get(status, "ATIVO")


def obter_ou_criar_id(conn, tabela, nome):
    nome = str(nome or "").strip()
    if not nome:
        return None

    registro = conn.execute(
        f"SELECT id FROM {tabela} WHERE lower(nome) = lower(?)",
        (nome,)
    ).fetchone()

    if registro:
        return registro["id"]

    cursor = conn.execute(
        f"INSERT INTO {tabela} (nome) VALUES (?)",
        (nome,)
    )
    return cursor.lastrowid


def importar_patrimonio(conn, linha, origem_padrao):
    dados = normalizar_linha(linha)

    codigo = str(dados.get("codigo") or "").strip()
    nome = str(dados.get("nome") or "").strip()

    if not codigo:
        raise ValueError("campo 'codigo' vazio")
    if not nome:
        raise ValueError(f"patrimônio {codigo}: campo 'nome' vazio")

    categoria_id = obter_ou_criar_id(conn, "categorias", dados.get("categoria"))
    setor_id = obter_ou_criar_id(conn, "setores", dados.get("setor"))
    origem = str(dados.get("origem_sistema") or origem_padrao).strip()
    status = normalizar_status(dados.get("status"))
    produto_sku = str(dados.get("produto_sku") or "").strip() or None
    external_id = str(dados.get("external_id") or "").strip() or None
    venda_external_id = str(dados.get("venda_external_id") or "").strip() or None
    cliente_documento = str(dados.get("cliente_documento") or "").strip() or None
    cliente_nome = str(dados.get("cliente_nome") or "").strip() or None
    colaborador_external_id = str(dados.get("colaborador_external_id") or "").strip() or None
    colaborador_nome = str(dados.get("colaborador_nome") or "").strip() or None
    data_venda = str(dados.get("data_venda") or "").strip() or None
    garantia_ate = str(dados.get("garantia_ate") or "").strip() or None
    try:
        unidade_origem = int(dados.get("unidade_origem") or 1) if external_id else None
    except (TypeError, ValueError):
        raise ValueError("campo 'unidade_origem' inválido")

    atual = conn.execute(
        "SELECT * FROM patrimonios WHERE codigo = ?",
        (codigo,)
    ).fetchone()
    if not atual and external_id:
        atual = conn.execute("""
            SELECT * FROM patrimonios
            WHERE origem_sistema=? AND external_id=? AND unidade_origem=?
        """, (origem, external_id, unidade_origem)).fetchone()

    if atual:
        # Campos ausentes no arquivo mantêm o valor que já estava no sistema.
        def valor_ou_atual(campo, valor_atual):
            valor = dados.get(campo)
            return valor_atual if valor in (None, "") else str(valor).strip()

        valor = atual["valor"]
        if dados.get("valor") not in (None, ""):
            valor = converter_valor(dados.get("valor"))

        categoria_final = categoria_id if categoria_id is not None else atual["categoria_id"]
        setor_final = setor_id if setor_id is not None else atual["setor_id"]

        conn.execute("""
            UPDATE patrimonios SET
                nome=?,
                descricao=?,
                marca=?,
                modelo=?,
                numero_serie=?,
                data_aquisicao=?,
                valor=?,
                status=?,
                categoria_id=?,
                setor_id=?,
                origem_sistema=?,
                produto_sku=?,
                external_id=?,
                unidade_origem=?,
                venda_external_id=?,
                cliente_documento=?,
                cliente_nome=?,
                colaborador_external_id=?,
                colaborador_nome=?,
                data_venda=?,
                garantia_ate=?
            WHERE id=?
        """, (
            nome,
            valor_ou_atual("descricao", atual["descricao"]),
            valor_ou_atual("marca", atual["marca"]),
            valor_ou_atual("modelo", atual["modelo"]),
            valor_ou_atual("numero_serie", atual["numero_serie"]),
            valor_ou_atual("data_aquisicao", atual["data_aquisicao"]),
            valor,
            status if dados.get("status") not in (None, "") else atual["status"],
            categoria_final,
            setor_final,
            origem,
            produto_sku if produto_sku is not None else atual["produto_sku"],
            external_id if external_id is not None else atual["external_id"],
            unidade_origem if unidade_origem is not None else atual["unidade_origem"],
            venda_external_id if venda_external_id is not None else atual["venda_external_id"],
            cliente_documento if cliente_documento is not None else atual["cliente_documento"],
            cliente_nome if cliente_nome is not None else atual["cliente_nome"],
            colaborador_external_id if colaborador_external_id is not None else atual["colaborador_external_id"],
            colaborador_nome if colaborador_nome is not None else atual["colaborador_nome"],
            data_venda if data_venda is not None else atual["data_venda"],
            garantia_ate if garantia_ate is not None else atual["garantia_ate"],
            atual["id"]
        ))
        return "atualizado"

    conn.execute("""
        INSERT INTO patrimonios
        (
            codigo, nome, descricao, marca, modelo, numero_serie,
            data_aquisicao, valor, status, categoria_id, setor_id, origem_sistema,
            produto_sku, external_id, unidade_origem, venda_external_id,
            cliente_documento, cliente_nome, colaborador_external_id,
            colaborador_nome, data_venda, garantia_ate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        codigo,
        nome,
        str(dados.get("descricao") or "").strip(),
        str(dados.get("marca") or "").strip(),
        str(dados.get("modelo") or "").strip(),
        str(dados.get("numero_serie") or "").strip(),
        str(dados.get("data_aquisicao") or "").strip() or None,
        converter_valor(dados.get("valor")),
        status,
        categoria_id,
        setor_id,
        origem,
        produto_sku,
        external_id,
        unidade_origem,
        venda_external_id,
        cliente_documento,
        cliente_nome,
        colaborador_external_id,
        colaborador_nome,
        data_venda,
        garantia_ate
    ))
    return "inserido"


def normalizar_registro(linha):
    return {
        chave_normalizada(chave): valor
        for chave, valor in linha.items()
        if chave is not None
    }


def converter_quantidade(valor):
    texto = str(valor or "1").strip().replace(",", ".")
    try:
        quantidade = int(float(texto))
    except (TypeError, ValueError):
        raise ValueError("campo 'quantidade' inválido")
    if quantidade < 1:
        raise ValueError("a quantidade deve ser maior que zero")
    if quantidade > 1000:
        raise ValueError("a quantidade máxima por registro é 1000")
    return quantidade


def codigo_seguro(texto):
    texto = chave_normalizada(texto).upper()
    texto = re.sub(r"[^A-Z0-9]+", "-", texto).strip("-")
    return texto[:24] or "ITEM"


def gerar_codigo_patrimonio(conn, sku, unidade):
    base = f"PAT-{codigo_seguro(sku)}-{unidade:03d}"
    codigo = base
    sufixo = 2
    while conn.execute(
        "SELECT 1 FROM patrimonios WHERE codigo=?", (codigo,)
    ).fetchone():
        codigo = f"{base}-{sufixo}"
        sufixo += 1
    return codigo


def registrar_log(
    conn,
    *,
    external_id,
    sistema_origem,
    arquivo,
    tipo_registro,
    operacao,
    status,
    mensagem,
    usuario_id,
    patrimonio_id=None,
):
    conn.execute("""
        INSERT INTO integracao_logs
        (external_id, sistema_origem, sistema_destino, arquivo, tipo_registro,
         operacao, status, mensagem, patrimonio_id, criado_em, usuario_id)
        VALUES (?, ?, 'PATRIMONIO', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(external_id or "").strip() or None,
        str(sistema_origem or "DESCONHECIDO").strip().upper(),
        arquivo,
        tipo_registro,
        operacao,
        status,
        mensagem,
        patrimonio_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        usuario_id,
    ))


def detectar_layout_csv(fieldnames):
    colunas = {chave_normalizada(nome) for nome in (fieldnames or []) if nome}
    campos_venda = {"venda_external_id", "id_venda", "id_pedido", "pedido_id"}
    campos_produto = {"produto_sku", "sku", "id_produto"}
    if colunas.intersection(campos_venda) and colunas.intersection(campos_produto):
        return "VENDAS_PATRIMONIO"
    if {"produto_sku", "tipo", "quantidade", "origem"}.issubset(colunas):
        return "MOVIMENTACOES_ESTOQUE"
    if {"sku", "nome", "quantidade"}.issubset(colunas):
        return "PRODUTOS_ESTOQUE"
    return "PATRIMONIOS"


def ler_csv_bytes(conteudo_bytes):
    try:
        conteudo = conteudo_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        conteudo = conteudo_bytes.decode("latin-1")
    amostra = conteudo[:2048]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=",;")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.DictReader(io.StringIO(conteudo), dialect=dialeto)
    return list(leitor), leitor.fieldnames


def identificar_tabela_vendas(fieldnames):
    colunas = {chave_normalizada(nome) for nome in (fieldnames or []) if nome}
    if {"id_cliente", "cpf_cnpj"}.issubset(colunas):
        return "clientes"
    if {"id_vendedor", "cpf"}.issubset(colunas):
        return "vendedores"
    if {"id_produto", "sku"}.issubset(colunas):
        return "produtos"
    if {"id_pedido", "id_cliente", "id_vendedor"}.issubset(colunas):
        return "pedidos"
    if {"id_pedido_item", "id_pedido", "id_produto"}.issubset(colunas):
        return "itens"
    if {"id_faturamento", "id_pedido"}.issubset(colunas):
        return "faturamentos"
    return None


def carregar_pacote_vendas(conteudo_bytes):
    tabelas = {}
    with zipfile.ZipFile(io.BytesIO(conteudo_bytes)) as pacote:
        arquivos = [info for info in pacote.infolist() if not info.is_dir()]
        if len(arquivos) > 50:
            raise ValueError("o pacote possui arquivos demais")
        if sum(info.file_size for info in arquivos) > 10 * 1024 * 1024:
            raise ValueError("o conteúdo descompactado ultrapassa 10 MB")

        for info in arquivos:
            if not info.filename.lower().endswith(".csv"):
                continue
            linhas, fieldnames = ler_csv_bytes(pacote.read(info))
            tabela = identificar_tabela_vendas(fieldnames)
            if tabela:
                tabelas[tabela] = linhas

    obrigatorias = {"clientes", "vendedores", "produtos", "pedidos", "itens"}
    ausentes = sorted(obrigatorias - set(tabelas))
    if ausentes:
        raise ValueError(
            "pacote de Vendas incompleto; tabelas ausentes: " + ", ".join(ausentes)
        )

    clientes = {
        str(linha.get("id_cliente")): linha for linha in tabelas["clientes"]
    }
    vendedores = {
        str(linha.get("id_vendedor")): linha for linha in tabelas["vendedores"]
    }
    produtos = {
        str(linha.get("id_produto")): linha for linha in tabelas["produtos"]
    }
    pedidos = {
        str(linha.get("id_pedido")): linha for linha in tabelas["pedidos"]
    }

    resultado = []
    for item in tabelas["itens"]:
        pedido = pedidos.get(str(item.get("id_pedido")))
        produto = produtos.get(str(item.get("id_produto")))
        if not pedido:
            raise ValueError(f"item {item.get('id_pedido_item')}: pedido não encontrado")
        if not produto:
            raise ValueError(f"item {item.get('id_pedido_item')}: produto não encontrado")
        cliente = clientes.get(str(pedido.get("id_cliente")), {})
        vendedor = vendedores.get(str(pedido.get("id_vendedor")), {})
        resultado.append({
            "venda_external_id": pedido.get("id_pedido"),
            "item_external_id": item.get("id_pedido_item"),
            "produto_sku": produto.get("sku"),
            "produto_nome": produto.get("nome"),
            "produto_descricao": produto.get("descricao"),
            "quantidade": item.get("quantidade"),
            "valor_unitario": item.get("preco_unitario") or produto.get("preco_unitario"),
            "data_venda": pedido.get("data_pedido"),
            "status_venda": pedido.get("status"),
            "cliente_documento": cliente.get("cpf_cnpj"),
            "cliente_nome": cliente.get("nome"),
            "colaborador_external_id": vendedor.get("id_vendedor"),
            "colaborador_nome": vendedor.get("nome"),
            "garantia_ate": item.get("validade_do_produto"),
        })
    return resultado


def importar_produto_estoque(conn, linha, arquivo, usuario_id):
    dados = normalizar_registro(linha)
    sku = str(dados.get("sku") or "").strip()
    nome = str(dados.get("nome") or "").strip()
    if not sku:
        raise ValueError("campo 'sku' vazio")
    if not nome:
        raise ValueError(f"produto {sku}: campo 'nome' vazio")

    external_id = str(dados.get("external_id") or dados.get("id") or sku).strip()
    quantidade = converter_quantidade(dados.get("quantidade"))
    descricao = str(dados.get("descricao") or "").strip()
    valor = converter_valor(dados.get("preco") or dados.get("preco_unitario"))
    categoria_id = obter_ou_criar_id(conn, "categorias", "Produtos importados")
    setor_id = obter_ou_criar_id(conn, "setores", "Estoque")

    inseridos = 0
    atualizados = 0
    for unidade in range(1, quantidade + 1):
        atual = conn.execute("""
            SELECT * FROM patrimonios
            WHERE origem_sistema='ESTOQUE' AND external_id=? AND unidade_origem=?
        """, (external_id, unidade)).fetchone()

        if atual:
            conn.execute("""
                UPDATE patrimonios SET
                    nome=?, descricao=?, valor=?, produto_sku=?, categoria_id=COALESCE(categoria_id, ?),
                    setor_id=COALESCE(setor_id, ?)
                WHERE id=?
            """, (nome, descricao, valor, sku, categoria_id, setor_id, atual["id"]))
            atualizados += 1
            patrimonio_id = atual["id"]
        else:
            codigo = gerar_codigo_patrimonio(conn, sku, unidade)
            cursor = conn.execute("""
                INSERT INTO patrimonios
                (codigo, nome, descricao, valor, status, categoria_id, setor_id,
                 origem_sistema, produto_sku, external_id, unidade_origem)
                VALUES (?, ?, ?, ?, 'PENDENTE', ?, ?, 'ESTOQUE', ?, ?, ?)
            """, (
                codigo, nome, descricao, valor, categoria_id, setor_id,
                sku, external_id, unidade,
            ))
            patrimonio_id = cursor.lastrowid
            inseridos += 1

        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem="ESTOQUE",
            arquivo=arquivo,
            tipo_registro="PRODUTO",
            operacao="SINCRONIZAR_PRODUTO",
            status="SUCESSO",
            mensagem=f"SKU {sku}, unidade {unidade} processada",
            usuario_id=usuario_id,
            patrimonio_id=patrimonio_id,
        )

    return {"inseridos": inseridos, "atualizados": atualizados, "ignorados": 0}


def primeiro_valor(dados, *campos):
    for campo in campos:
        valor = dados.get(campo)
        if valor not in (None, ""):
            return valor
    return None


def importar_venda_patrimonio(conn, linha, arquivo, usuario_id):
    dados = normalizar_registro(linha)
    venda_id = str(primeiro_valor(
        dados, "venda_external_id", "id_venda", "id_pedido", "pedido_id"
    ) or "").strip()
    item_id = str(primeiro_valor(
        dados, "item_external_id", "id_item", "id_pedido_item"
    ) or "").strip()
    sku = str(primeiro_valor(
        dados, "produto_sku", "sku", "codigo_produto", "id_produto"
    ) or "").strip()
    nome = str(primeiro_valor(
        dados, "produto_nome", "nome_produto", "nome", "produto"
    ) or "").strip()
    if not venda_id:
        raise ValueError("identificador da venda vazio")
    if not sku:
        raise ValueError(f"venda {venda_id}: SKU do produto vazio")
    if not nome:
        nome = f"Produto {sku}"

    quantidade = converter_quantidade(dados.get("quantidade"))
    status_venda = chave_normalizada(primeiro_valor(
        dados, "status_venda", "status"
    )).upper()
    external_id = f"VENDA-{venda_id}-ITEM-{item_id or sku}"
    status_confirmados = {"", "FATURADO", "CONCLUIDO", "APROVADO", "FINALIZADO", "VENDIDO"}
    if status_venda not in status_confirmados:
        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem="VENDAS",
            arquivo=arquivo,
            tipo_registro="VENDA",
            operacao="REGISTRAR_POS_VENDA",
            status="IGNORADO",
            mensagem=f"Venda com status '{status_venda}' ainda não concluída",
            usuario_id=usuario_id,
        )
        return {"inseridos": 0, "atualizados": 0, "ignorados": 1}

    descricao = str(primeiro_valor(
        dados, "produto_descricao", "descricao_produto", "descricao"
    ) or "").strip()
    valor = converter_valor(primeiro_valor(
        dados, "valor_unitario", "preco_unitario", "preco", "valor"
    ))
    cliente_documento = str(primeiro_valor(
        dados, "cliente_documento", "cpf_cnpj", "cliente_cpf", "cliente_cnpj"
    ) or "").strip() or None
    cliente_nome = str(primeiro_valor(
        dados, "cliente_nome", "nome_cliente"
    ) or "").strip() or None
    colaborador_id = str(primeiro_valor(
        dados, "colaborador_external_id", "id_vendedor", "vendedor_id", "colaborador_id"
    ) or "").strip() or None
    colaborador_nome = str(primeiro_valor(
        dados, "colaborador_nome", "nome_vendedor", "vendedor_nome", "responsavel_nome"
    ) or "").strip() or None
    data_venda = str(primeiro_valor(
        dados, "data_venda", "data_pedido", "data"
    ) or "").strip() or None
    garantia_ate = str(primeiro_valor(
        dados, "garantia_ate", "data_garantia", "validade_do_produto"
    ) or "").strip() or None
    categoria_id = obter_ou_criar_id(conn, "categorias", "Produtos vendidos")
    setor_id = obter_ou_criar_id(conn, "setores", "Pós-venda")

    inseridos = 0
    atualizados = 0
    for unidade in range(1, quantidade + 1):
        atual = conn.execute("""
            SELECT * FROM patrimonios
            WHERE origem_sistema='VENDAS' AND external_id=? AND unidade_origem=?
        """, (external_id, unidade)).fetchone()
        if atual:
            conn.execute("""
                UPDATE patrimonios SET
                    nome=?, descricao=?, valor=?, status='VENDIDO', produto_sku=?,
                    venda_external_id=?, cliente_documento=?, cliente_nome=?,
                    colaborador_external_id=?, colaborador_nome=?, data_venda=?,
                    garantia_ate=?, categoria_id=COALESCE(categoria_id, ?),
                    setor_id=COALESCE(setor_id, ?)
                WHERE id=?
            """, (
                nome, descricao, valor, sku, venda_id, cliente_documento,
                cliente_nome, colaborador_id, colaborador_nome, data_venda,
                garantia_ate, categoria_id, setor_id, atual["id"],
            ))
            patrimonio_id = atual["id"]
            atualizados += 1
        else:
            codigo = gerar_codigo_patrimonio(conn, f"VENDA-{sku}", unidade)
            cursor = conn.execute("""
                INSERT INTO patrimonios
                (codigo, nome, descricao, valor, status, categoria_id, setor_id,
                 origem_sistema, produto_sku, external_id, unidade_origem,
                 venda_external_id, cliente_documento, cliente_nome,
                 colaborador_external_id, colaborador_nome, data_venda, garantia_ate)
                VALUES (?, ?, ?, ?, 'VENDIDO', ?, ?, 'VENDAS', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                codigo, nome, descricao, valor, categoria_id, setor_id, sku,
                external_id, unidade, venda_id, cliente_documento, cliente_nome,
                colaborador_id, colaborador_nome, data_venda, garantia_ate,
            ))
            patrimonio_id = cursor.lastrowid
            inseridos += 1

        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem="VENDAS",
            arquivo=arquivo,
            tipo_registro="VENDA",
            operacao="REGISTRAR_POS_VENDA",
            status="SUCESSO",
            mensagem=f"Venda {venda_id}, SKU {sku}, unidade {unidade} registrada",
            usuario_id=usuario_id,
            patrimonio_id=patrimonio_id,
        )

    return {"inseridos": inseridos, "atualizados": atualizados, "ignorados": 0}


def operacao_movimentacao(dados):
    operacao = chave_normalizada(dados.get("operacao")).upper()
    if operacao:
        return operacao

    tipo = chave_normalizada(dados.get("tipo")).upper()
    if tipo in {"PATRIMONIAL", "PATRIMONIALIZACAO", "AQUISICAO", "COMPRA", "ENTRADA_PATRIMONIO"}:
        return "PATRIMONIALIZAR"
    if tipo in {"BAIXA_PATRIMONIO", "DESCARTE_PATRIMONIO"}:
        return "BAIXAR"
    return "IGNORAR"


def external_id_movimentacao(dados):
    informado = str(dados.get("external_id") or "").strip()
    if informado:
        return informado
    base = "|".join(str(dados.get(campo) or "").strip() for campo in (
        "produto_sku", "tipo", "quantidade", "origem", "created_at"
    ))
    return "AUTO-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16].upper()


def importar_movimentacao_estoque(conn, linha, arquivo, usuario_id):
    dados = normalizar_registro(linha)
    sku = str(dados.get("produto_sku") or "").strip()
    if not sku:
        raise ValueError("campo 'produto_sku' vazio")

    quantidade = converter_quantidade(dados.get("quantidade"))
    origem = str(dados.get("origem") or "ESTOQUE").strip().upper()
    external_id = external_id_movimentacao(dados)
    operacao = operacao_movimentacao(dados)

    ja_processado = conn.execute("""
        SELECT 1 FROM integracao_logs
        WHERE sistema_origem=? AND external_id=? AND operacao=? AND status='SUCESSO'
        LIMIT 1
    """, (origem, external_id, operacao)).fetchone()
    if ja_processado:
        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem=origem,
            arquivo=arquivo,
            tipo_registro="MOVIMENTACAO",
            operacao=operacao,
            status="IGNORADO",
            mensagem="Evento já processado anteriormente",
            usuario_id=usuario_id,
        )
        return {"inseridos": 0, "atualizados": 0, "ignorados": 1}

    if operacao == "IGNORAR":
        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem=origem,
            arquivo=arquivo,
            tipo_registro="MOVIMENTACAO",
            operacao=operacao,
            status="IGNORADO",
            mensagem=f"Tipo '{dados.get('tipo')}' não representa movimentação patrimonial",
            usuario_id=usuario_id,
        )
        return {"inseridos": 0, "atualizados": 0, "ignorados": 1}

    if operacao == "BAIXAR":
        patrimonios = conn.execute("""
            SELECT id FROM patrimonios
            WHERE produto_sku=? AND status != 'BAIXADO'
            ORDER BY id LIMIT ?
        """, (sku, quantidade)).fetchall()
        for patrimonio in patrimonios:
            conn.execute(
                "UPDATE patrimonios SET status='BAIXADO' WHERE id=?",
                (patrimonio["id"],),
            )
        status = "SUCESSO" if patrimonios else "IGNORADO"
        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem=origem,
            arquivo=arquivo,
            tipo_registro="MOVIMENTACAO",
            operacao=operacao,
            status=status,
            mensagem=f"{len(patrimonios)} patrimônio(s) baixado(s) para o SKU {sku}",
            usuario_id=usuario_id,
        )
        return {
            "inseridos": 0,
            "atualizados": len(patrimonios),
            "ignorados": 0 if patrimonios else 1,
        }

    if operacao not in {"PATRIMONIALIZAR", "CADASTRAR", "ENTRADA"}:
        raise ValueError(f"operação '{operacao}' não suportada")

    produto_base = conn.execute("""
        SELECT * FROM patrimonios
        WHERE produto_sku=?
        ORDER BY id LIMIT 1
    """, (sku,)).fetchone()
    categoria_id = produto_base["categoria_id"] if produto_base else obter_ou_criar_id(
        conn, "categorias", "Produtos importados"
    )
    setor_id = obter_ou_criar_id(conn, "setores", "Estoque")
    nome = produto_base["nome"] if produto_base else f"Produto {sku}"
    descricao = produto_base["descricao"] if produto_base else "Importado por movimentação do Estoque"
    valor = produto_base["valor"] if produto_base else 0

    inseridos = 0
    atualizados = 0
    for unidade in range(1, quantidade + 1):
        atual = conn.execute("""
            SELECT * FROM patrimonios
            WHERE origem_sistema=? AND external_id=? AND unidade_origem=?
        """, (origem, external_id, unidade)).fetchone()
        if atual:
            atualizados += 1
            patrimonio_id = atual["id"]
        else:
            codigo = gerar_codigo_patrimonio(conn, sku, unidade)
            cursor = conn.execute("""
                INSERT INTO patrimonios
                (codigo, nome, descricao, valor, status, categoria_id, setor_id,
                 origem_sistema, produto_sku, external_id, unidade_origem)
                VALUES (?, ?, ?, ?, 'PENDENTE', ?, ?, ?, ?, ?, ?)
            """, (
                codigo, nome, descricao, valor, categoria_id, setor_id,
                origem, sku, external_id, unidade,
            ))
            patrimonio_id = cursor.lastrowid
            inseridos += 1

        registrar_log(
            conn,
            external_id=external_id,
            sistema_origem=origem,
            arquivo=arquivo,
            tipo_registro="MOVIMENTACAO",
            operacao=operacao,
            status="SUCESSO",
            mensagem=f"SKU {sku}, unidade {unidade} patrimonializada",
            usuario_id=usuario_id,
            patrimonio_id=patrimonio_id,
        )

    return {"inseridos": inseridos, "atualizados": atualizados, "ignorados": 0}


@app.route("/importacao", methods=["GET", "POST"])
@admin_required
def importacao():
    conn = get_db()
    resultado = None

    if request.method == "POST":
        arquivo = request.files.get("arquivo")

        if not arquivo or not arquivo.filename:
            flash("Selecione um arquivo CSV, JSON ou ZIP de Vendas.", "erro")
            conn.close()
            return redirect(url_for("importacao"))

        nome_arquivo = arquivo.filename
        extensao = Path(nome_arquivo).suffix.lower()

        if extensao not in (".csv", ".json", ".zip"):
            flash("Formato inválido. Utilize CSV, JSON ou ZIP de Vendas.", "erro")
            conn.close()
            return redirect(url_for("importacao"))

        try:
            conteudo_bytes = arquivo.read()

            if extensao == ".csv":
                linhas, fieldnames = ler_csv_bytes(conteudo_bytes)
                layout = detectar_layout_csv(fieldnames)
                formato = f"CSV/{layout}"
            elif extensao == ".zip":
                linhas = carregar_pacote_vendas(conteudo_bytes)
                layout = "VENDAS_PATRIMONIO"
                formato = "ZIP/VENDAS_PATRIMONIO"
            else:
                try:
                    conteudo = conteudo_bytes.decode("utf-8-sig")
                except UnicodeDecodeError:
                    conteudo = conteudo_bytes.decode("latin-1")
                dados_json = json.loads(conteudo)

                if isinstance(dados_json, list):
                    linhas = dados_json
                elif isinstance(dados_json, dict) and isinstance(dados_json.get("patrimonios"), list):
                    linhas = dados_json["patrimonios"]
                elif isinstance(dados_json, dict):
                    linhas = [dados_json]
                else:
                    raise ValueError("estrutura JSON não reconhecida")

                layout = "PATRIMONIOS"
                formato = "JSON/PATRIMONIOS"

            if not linhas:
                raise ValueError("o arquivo não possui registros")

            inseridos = 0
            atualizados = 0
            ignorados = 0
            erros = []
            origem_padrao = f"Importação {formato}"
            usuario_id = session.get("usuario_id")

            for numero, linha in enumerate(linhas, start=2 if extensao == ".csv" else 1):
                if not isinstance(linha, dict):
                    erros.append(f"Registro {numero}: formato inválido")
                    continue

                conn.execute("SAVEPOINT registro_importacao")
                try:
                    if layout == "PRODUTOS_ESTOQUE":
                        resumo = importar_produto_estoque(
                            conn, linha, nome_arquivo, usuario_id
                        )
                    elif layout == "MOVIMENTACOES_ESTOQUE":
                        resumo = importar_movimentacao_estoque(
                            conn, linha, nome_arquivo, usuario_id
                        )
                    elif layout == "VENDAS_PATRIMONIO":
                        resumo = importar_venda_patrimonio(
                            conn, linha, nome_arquivo, usuario_id
                        )
                    else:
                        acao = importar_patrimonio(conn, linha, origem_padrao)
                        dados_log = normalizar_linha(linha)
                        registrar_log(
                            conn,
                            external_id=dados_log.get("external_id") or dados_log.get("codigo"),
                            sistema_origem=dados_log.get("origem_sistema") or origem_padrao,
                            arquivo=nome_arquivo,
                            tipo_registro="PATRIMONIO",
                            operacao="CADASTRAR" if acao == "inserido" else "ATUALIZAR",
                            status="SUCESSO",
                            mensagem=f"Registro {numero} processado",
                            usuario_id=usuario_id,
                        )
                        resumo = {
                            "inseridos": 1 if acao == "inserido" else 0,
                            "atualizados": 1 if acao == "atualizado" else 0,
                            "ignorados": 0,
                        }

                    inseridos += resumo["inseridos"]
                    atualizados += resumo["atualizados"]
                    ignorados += resumo["ignorados"]
                    conn.execute("RELEASE SAVEPOINT registro_importacao")
                except Exception as e:
                    conn.execute("ROLLBACK TO SAVEPOINT registro_importacao")
                    conn.execute("RELEASE SAVEPOINT registro_importacao")
                    erros.append(f"Registro {numero}: {e}")
                    dados_erro = normalizar_registro(linha)
                    registrar_log(
                        conn,
                        external_id=dados_erro.get("external_id") or dados_erro.get("id"),
                        sistema_origem=dados_erro.get("origem") or origem_padrao,
                        arquivo=nome_arquivo,
                        tipo_registro=layout,
                        operacao=str(dados_erro.get("operacao") or "IMPORTAR").upper(),
                        status="ERRO",
                        mensagem=f"Registro {numero}: {e}",
                        usuario_id=usuario_id,
                    )

            conn.execute("""
                INSERT INTO importacoes
                (arquivo, formato, total, inseridos, atualizados, ignorados, erros, data, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nome_arquivo,
                formato,
                len(linhas),
                inseridos,
                atualizados,
                ignorados,
                len(erros),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                usuario_id
            ))
            conn.commit()

            resultado = {
                "total": len(linhas),
                "inseridos": inseridos,
                "atualizados": atualizados,
                "ignorados": ignorados,
                "erros": len(erros),
                "mensagens_erros": erros[:8],
                "layout": layout,
            }

            if erros:
                flash("Importação concluída, mas alguns registros apresentaram erro.", "erro")
            else:
                flash("Importação concluída com sucesso.", "sucesso")

        except Exception as e:
            conn.rollback()
            flash(f"Não foi possível importar o arquivo: {e}", "erro")

    historico = conn.execute("""
        SELECT i.*, u.nome AS usuario
        FROM importacoes i
        LEFT JOIN usuarios u ON u.id = i.usuario_id
        ORDER BY i.id DESC
        LIMIT 10
    """).fetchall()

    conn.close()
    return render_template(
        "importacao.html", historico=historico, resultado=resultado,
        agora=datetime.now().strftime("%d/%m/%Y")
    )


@app.get("/importacao/modelo.csv")
@admin_required
def modelo_importacao_csv():
    conteudo = (
        "codigo;nome;descricao;marca;modelo;numero_serie;data_aquisicao;"
        "valor;status;categoria;setor;origem_sistema\n"
        "PAT-100;Notebook do Financeiro;Notebook para uso administrativo;"
        "Dell;Latitude 5420;ABC123;2026-08-27;3500,00;ATIVO;"
        "Informática;Administrativo;Sistema Financeiro\n"
    )

    return Response(
        "\ufeff" + conteudo,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=modelo_importacao_patrimonios.csv"
        }
    )


def resposta_csv(nome_arquivo, cabecalho, linhas, delimitador=","):
    saida = io.StringIO(newline="")
    escritor = csv.writer(saida, delimiter=delimitador, lineterminator="\n")
    escritor.writerow(cabecalho)
    escritor.writerows(linhas)
    return Response(
        "\ufeff" + saida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={nome_arquivo}"
        },
    )


@app.get("/exportacao/patrimonios.csv")
@admin_required
def exportar_patrimonios_csv():
    conn = get_db()
    linhas = conn.execute("""
        SELECT p.codigo, p.produto_sku, p.nome, p.descricao, p.marca, p.modelo,
               p.numero_serie, p.data_aquisicao, p.valor, p.status,
               c.nome AS categoria, s.nome AS setor, p.origem_sistema,
               p.external_id, p.unidade_origem, p.venda_external_id,
               p.cliente_documento, p.cliente_nome, p.colaborador_external_id,
               p.colaborador_nome, p.data_venda, p.garantia_ate, p.criado_em
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id=p.categoria_id
        LEFT JOIN setores s ON s.id=p.setor_id
        ORDER BY p.id
    """).fetchall()
    conn.close()
    return resposta_csv(
        "patrimonios_exportados.csv",
        [
            "codigo", "produto_sku", "nome", "descricao", "marca", "modelo",
            "numero_serie", "data_aquisicao", "valor", "status", "categoria",
            "setor", "origem_sistema", "external_id", "unidade_origem",
            "venda_external_id", "cliente_documento", "cliente_nome",
            "colaborador_external_id", "colaborador_nome", "data_venda",
            "garantia_ate", "criado_em",
        ],
        ([linha[campo] for campo in linha.keys()] for linha in linhas),
    )


@app.get("/exportacao/movimentacoes.csv")
@admin_required
def exportar_movimentacoes_csv():
    conn = get_db()
    linhas = conn.execute("""
        SELECT m.id, p.codigo, p.produto_sku, m.data,
               so.nome AS setor_origem, sd.nome AS setor_destino,
               m.observacao, u.nome AS usuario
        FROM movimentacoes m
        JOIN patrimonios p ON p.id=m.patrimonio_id
        LEFT JOIN setores so ON so.id=m.setor_origem_id
        JOIN setores sd ON sd.id=m.setor_destino_id
        LEFT JOIN usuarios u ON u.id=m.usuario_id
        ORDER BY m.id
    """).fetchall()
    conn.close()
    return resposta_csv(
        "movimentacoes_patrimonio.csv",
        [
            "movimentacao_id", "codigo_patrimonio", "produto_sku", "data",
            "setor_origem", "setor_destino", "observacao", "usuario",
        ],
        ([linha[campo] for campo in linha.keys()] for linha in linhas),
    )


@app.get("/exportacao/rh_colaboradores.csv")
@admin_required
def exportar_rh_colaboradores_csv():
    conn = get_db()
    linhas = conn.execute("""
        SELECT printf('SAC-%04d', p.id) AS id_evento,
               p.colaborador_external_id AS id_colaborador,
               COALESCE(
                   strftime('%d/%m/%Y', p.data_venda),
                   strftime('%d/%m/%Y', p.criado_em),
                   ''
               ) AS data_evento,
               'ATENDIMENTO' AS tipo_evento,
               'Atendimento vinculado ao colaborador responsável' AS descricao,
               'CONCLUIDO' AS status_evento
        FROM patrimonios p
        WHERE p.origem_sistema='VENDAS'
          AND p.colaborador_external_id IS NOT NULL
          AND trim(p.colaborador_external_id) != ''
        ORDER BY p.id
    """).fetchall()
    conn.close()
    return resposta_csv(
        "sac_para_rh.csv",
        [
            "id_evento", "id_colaborador", "data_evento", "tipo_evento",
            "descricao", "status_evento",
        ],
        ([linha[campo] for campo in linha.keys()] for linha in linhas),
        delimitador=";",
    )


@app.get("/exportacao/logs.csv")
@admin_required
def exportar_logs_csv():
    conn = get_db()
    linhas = conn.execute("""
        SELECT l.id, l.external_id, l.sistema_origem, l.sistema_destino,
               l.arquivo, l.tipo_registro, l.operacao, l.status, l.mensagem,
               p.codigo AS codigo_patrimonio, l.criado_em, u.nome AS usuario
        FROM integracao_logs l
        LEFT JOIN patrimonios p ON p.id=l.patrimonio_id
        LEFT JOIN usuarios u ON u.id=l.usuario_id
        ORDER BY l.id
    """).fetchall()
    conn.close()
    return resposta_csv(
        "log_integracao.csv",
        [
            "log_id", "external_id", "sistema_origem", "sistema_destino",
            "arquivo", "tipo_registro", "operacao", "status", "mensagem",
            "codigo_patrimonio", "criado_em", "usuario",
        ],
        ([linha[campo] for campo in linha.keys()] for linha in linhas),
    )



# ---------------------------
# API REST
# ---------------------------

def row_to_dict(row):
    return dict(row) if row else None


@app.get("/api/patrimonios")
def api_listar_patrimonios():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, c.nome AS categoria, s.nome AS setor
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id=p.categoria_id
        LEFT JOIN setores s ON s.id=p.setor_id
        ORDER BY p.id
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/integracao/vendas/patrimonios")
def api_patrimonios_vendas():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, c.nome AS categoria, s.nome AS setor
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id=p.categoria_id
        LEFT JOIN setores s ON s.id=p.setor_id
        WHERE p.origem_sistema='VENDAS'
        ORDER BY p.id
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.post("/api/integracao/vendas/patrimonios")
def api_receber_patrimonios_vendas():
    dados = request.get_json(silent=True)
    if isinstance(dados, dict) and isinstance(dados.get("vendas"), list):
        registros = dados["vendas"]
    elif isinstance(dados, dict) and isinstance(dados.get("patrimonios"), list):
        registros = dados["patrimonios"]
    elif isinstance(dados, list):
        registros = dados
    elif isinstance(dados, dict):
        registros = [dados]
    else:
        return jsonify({"erro": "Envie um objeto JSON ou uma lista de vendas."}), 400

    if not registros:
        return jsonify({"erro": "A lista de vendas está vazia."}), 400
    if len(registros) > 1000:
        return jsonify({"erro": "Envie no máximo 1000 registros por requisição."}), 400

    conn = get_db()
    resumo_total = {"total": len(registros), "inseridos": 0, "atualizados": 0,
                    "ignorados": 0, "erros": []}
    try:
        for numero, registro in enumerate(registros, start=1):
            conn.execute("SAVEPOINT registro_api_vendas")
            try:
                if not isinstance(registro, dict):
                    raise ValueError("o registro deve ser um objeto JSON")
                resumo = importar_venda_patrimonio(
                    conn, registro, "API /api/integracao/vendas/patrimonios", None
                )
                for campo in ("inseridos", "atualizados", "ignorados"):
                    resumo_total[campo] += resumo[campo]
                conn.execute("RELEASE SAVEPOINT registro_api_vendas")
            except Exception as erro:
                conn.execute("ROLLBACK TO SAVEPOINT registro_api_vendas")
                conn.execute("RELEASE SAVEPOINT registro_api_vendas")
                resumo_total["erros"].append({"registro": numero, "mensagem": str(erro)})

        conn.commit()
    finally:
        conn.close()

    processados = resumo_total["inseridos"] + resumo_total["atualizados"] + resumo_total["ignorados"]
    if resumo_total["erros"] and not processados:
        status_http = 422
    elif resumo_total["erros"]:
        status_http = 207
    elif resumo_total["inseridos"]:
        status_http = 201
    else:
        status_http = 200
    return jsonify(resumo_total), status_http


@app.get("/api/integracao/rh/responsabilidades")
def api_responsabilidades_rh():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.external_id, p.codigo AS patrimonio_codigo,
               p.venda_external_id, p.produto_sku, p.nome AS produto_nome,
               p.cliente_documento, p.cliente_nome,
               p.colaborador_external_id, p.colaborador_nome,
               'POS_VENDA_PATRIMONIO' AS tipo_responsabilidade,
               p.status, p.data_venda, p.garantia_ate, p.origem_sistema,
               p.criado_em
        FROM patrimonios p
        WHERE p.origem_sistema='VENDAS'
        ORDER BY p.id
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/patrimonios/<int:id>")
def api_patrimonio(id):
    conn = get_db()
    row = conn.execute("""
        SELECT p.*, c.nome AS categoria, s.nome AS setor
        FROM patrimonios p
        LEFT JOIN categorias c ON c.id=p.categoria_id
        LEFT JOIN setores s ON s.id=p.setor_id
        WHERE p.id=?
    """, (id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"erro": "Patrimônio não encontrado"}), 404
    return jsonify(dict(row))


@app.post("/api/patrimonios")
def api_criar_patrimonio():
    data = request.get_json(silent=True) or {}
    obrigatorios = ["codigo", "nome"]
    faltando = [campo for campo in obrigatorios if not data.get(campo)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios: {', '.join(faltando)}"}), 400

    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO patrimonios
            (codigo, nome, descricao, marca, modelo, numero_serie, data_aquisicao,
             valor, status, categoria_id, setor_id, origem_sistema, produto_sku,
             external_id, unidade_origem, venda_external_id, cliente_documento,
             cliente_nome, colaborador_external_id, colaborador_nome, data_venda,
             garantia_ate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["codigo"], data["nome"], data.get("descricao", ""),
            data.get("marca", ""), data.get("modelo", ""), data.get("numero_serie", ""),
            data.get("data_aquisicao"), float(data.get("valor", 0)),
            data.get("status", "ATIVO"), data.get("categoria_id"), data.get("setor_id"),
            data.get("origem_sistema", "API"), data.get("produto_sku"),
            data.get("external_id"), data.get("unidade_origem"),
            data.get("venda_external_id"), data.get("cliente_documento"),
            data.get("cliente_nome"), data.get("colaborador_external_id"),
            data.get("colaborador_nome"), data.get("data_venda"),
            data.get("garantia_ate")
        ))
        conn.commit()
        novo_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"erro": "Código de patrimônio já cadastrado"}), 409
    conn.close()
    return jsonify({"mensagem": "Patrimônio criado", "id": novo_id}), 201


@app.put("/api/patrimonios/<int:id>")
def api_atualizar_patrimonio(id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    atual = conn.execute("SELECT * FROM patrimonios WHERE id=?", (id,)).fetchone()
    if not atual:
        conn.close()
        return jsonify({"erro": "Patrimônio não encontrado"}), 404

    campos = [
        "codigo", "nome", "descricao", "marca", "modelo", "numero_serie",
        "data_aquisicao", "valor", "status", "categoria_id", "setor_id",
        "origem_sistema", "produto_sku", "external_id", "unidade_origem",
        "venda_external_id", "cliente_documento", "cliente_nome",
        "colaborador_external_id", "colaborador_nome", "data_venda", "garantia_ate",
    ]
    valores = {campo: data.get(campo, atual[campo]) for campo in campos}

    try:
        conn.execute("""
            UPDATE patrimonios SET codigo=?, nome=?, descricao=?, marca=?, modelo=?,
            numero_serie=?, data_aquisicao=?, valor=?, status=?, categoria_id=?, setor_id=?,
            origem_sistema=?, produto_sku=?, external_id=?, unidade_origem=?,
            venda_external_id=?, cliente_documento=?, cliente_nome=?,
            colaborador_external_id=?, colaborador_nome=?, data_venda=?, garantia_ate=?
            WHERE id=?
        """, tuple(valores[c] for c in campos) + (id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"erro": "Código de patrimônio já cadastrado"}), 409
    conn.close()
    return jsonify({"mensagem": "Patrimônio atualizado"})


@app.delete("/api/patrimonios/<int:id>")
def api_excluir_patrimonio(id):
    conn = get_db()
    existe = conn.execute("SELECT 1 FROM patrimonios WHERE id=?", (id,)).fetchone()
    if not existe:
        conn.close()
        return jsonify({"erro": "Patrimônio não encontrado"}), 404
    conn.execute("UPDATE patrimonios SET status='BAIXADO' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"mensagem": "Patrimônio baixado com sucesso"})


@app.get("/api/categorias")
def api_categorias():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categorias ORDER BY nome").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/setores")
def api_setores():
    conn = get_db()
    rows = conn.execute("SELECT * FROM setores ORDER BY nome").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
