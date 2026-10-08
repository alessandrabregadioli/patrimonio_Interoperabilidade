"""Cliente TCP para o servidor de troca de mensagens e arquivos da turma."""

from collections import deque
from pathlib import Path
import os
import re
import socket
import threading
import uuid


class SocketGateway:
    HOST = "electronicsystems.com.br"
    PORT = 5000
    CHUNK_SIZE = 4096
    MAX_CHUNK_SIZE = 1024 * 1024
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(self, received_dir):
        self.received_dir = Path(received_dir)
        self.received_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._socket = None
        self._thread = None
        self._desired = False
        self._name = "patrimonio"
        self._state = "desconectado"
        self._last_error = None
        self._next_event_id = 1
        self._events = deque(maxlen=500)
        self._files = {}
        self._assemblies = {}

    @staticmethod
    def validar_nome(nome):
        nome = str(nome or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", nome):
            raise ValueError("Use um nome de sistema com 2 a 40 letras, números, ponto, hífen ou sublinhado.")
        return nome

    @staticmethod
    def validar_destino(destino):
        destino = str(destino or "").strip().lstrip("#")
        if not destino:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", destino):
            raise ValueError("O destinatário deve ser o nome ou o ID, sem # e sem espaços.")
        return destino

    def _emit(self, tipo, **dados):
        with self._lock:
            evento = {"id": self._next_event_id, "tipo": tipo, **dados}
            self._next_event_id += 1
            self._events.append(evento)
            return evento

    def status(self):
        with self._lock:
            return {
                "estado": self._state,
                "nome": self._name,
                "host": self.HOST,
                "porta": self.PORT,
                "erro": self._last_error,
            }

    def iniciar(self, nome="patrimonio"):
        nome = self.validar_nome(nome)
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._desired and self._name == nome:
                    return self.status()
                raise RuntimeError("Desconecte a sessão atual antes de trocar o nome do sistema.")
            self._name = nome
            self._desired = True
            self._stop_event.clear()
            self._state = "conectando"
            self._last_error = None
            self._thread = threading.Thread(
                target=self._executar, name="socket-patrimonio", daemon=True
            )
            self._thread.start()
        self._emit("sistema", mensagem=f"Conectando como {nome}...")
        return self.status()

    def parar(self):
        with self._lock:
            self._desired = False
            self._state = "desconectando"
            conexao = self._socket
            self._stop_event.set()
        if conexao:
            try:
                conexao.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conexao.close()
            except OSError:
                pass
        self._emit("sistema", mensagem="Desconexão solicitada.")
        return self.status()

    def _executar(self):
        espera = 1
        while not self._stop_event.is_set():
            conexao = None
            leitor = None
            try:
                with self._lock:
                    nome = self._name
                    self._state = "conectando"
                conexao = socket.create_connection((self.HOST, self.PORT), timeout=10)
                conexao.settimeout(None)
                with self._lock:
                    if self._stop_event.is_set():
                        conexao.close()
                        break
                    self._socket = conexao
                    self._state = "conectado"
                    self._last_error = None
                with self._send_lock:
                    conexao.sendall(f"/nome {nome}\n".encode("utf-8"))
                self._emit("sistema", mensagem=f"Conectado ao servidor como {nome}.")
                espera = 1
                leitor = conexao.makefile("rb")
                while not self._stop_event.is_set():
                    linha = leitor.readline()
                    if not linha:
                        raise ConnectionError("O servidor encerrou a conexão.")
                    self._processar_linha(leitor, linha)
            except Exception as erro:
                if not self._stop_event.is_set():
                    mensagem = str(erro).strip() or erro.__class__.__name__
                    with self._lock:
                        self._state = "reconectando"
                        self._last_error = mensagem
                    self._emit("erro", mensagem=f"Conexão interrompida: {mensagem}")
            finally:
                if leitor:
                    try:
                        leitor.close()
                    except OSError:
                        pass
                if conexao:
                    try:
                        conexao.close()
                    except OSError:
                        pass
                with self._lock:
                    if self._socket is conexao:
                        self._socket = None
                    if not self._desired:
                        self._state = "desconectado"
                    self._limpar_transferencias_incompletas()
            if not self._stop_event.is_set():
                self._stop_event.wait(espera)
                espera = min(espera * 2, 20)
        with self._lock:
            self._socket = None
            self._state = "desconectado"
        self._emit("sistema", mensagem="Cliente socket desconectado.")

    def _ler_exatamente(self, leitor, quantidade):
        partes = []
        restante = quantidade
        while restante:
            parte = leitor.read(restante)
            if not parte:
                raise ConnectionError("Conexão encerrada durante a transferência de um arquivo.")
            partes.append(parte)
            restante -= len(parte)
        return b"".join(partes)

    def _processar_linha(self, leitor, linha):
        texto = linha.decode("utf-8", errors="replace").rstrip("\r\n")
        if not texto.startswith("/arquivo "):
            self._emit("mensagem", mensagem=texto)
            return

        partes = texto.split(" ", 3)
        if len(partes) != 4:
            self._emit("erro", mensagem=f"Cabeçalho de arquivo inválido: {texto[:180]}")
            return
        _, remetente, tamanho_texto, nome_original = partes
        try:
            tamanho = int(tamanho_texto)
        except ValueError:
            self._emit("erro", mensagem="O servidor enviou um tamanho de bloco inválido.")
            return
        if tamanho < 0 or tamanho > self.MAX_CHUNK_SIZE:
            raise ValueError("O servidor enviou um bloco acima do limite de 1 MB.")
        nome = Path(nome_original).name.strip()
        if not nome or nome in {".", ".."}:
            raise ValueError("O servidor enviou um nome de arquivo inválido.")

        chave = (remetente, nome)
        with self._lock:
            transferencia = self._assemblies.get(chave)
            if transferencia is None:
                token = uuid.uuid4().hex
                temporario = self.received_dir / f".{token}.part"
                arquivo = temporario.open("wb")
                transferencia = {
                    "token": token,
                    "temporario": temporario,
                    "arquivo": arquivo,
                    "total": 0,
                }
                self._assemblies[chave] = transferencia

        if tamanho:
            dados = self._ler_exatamente(leitor, tamanho)
            with self._lock:
                transferencia = self._assemblies[chave]
                novo_total = transferencia["total"] + len(dados)
                if novo_total > self.MAX_FILE_SIZE:
                    raise ValueError("Arquivo recebido ultrapassou 10 MB.")
                transferencia["arquivo"].write(dados)
                transferencia["total"] = novo_total
            return

        with self._lock:
            transferencia = self._assemblies.pop(chave)
            transferencia["arquivo"].close()
            destino = self.received_dir / f"{transferencia['token']}_{nome}"
            os.replace(transferencia["temporario"], destino)
            arquivo_info = {
                "token": transferencia["token"],
                "nome": nome,
                "remetente": remetente,
                "tamanho": transferencia["total"],
                "caminho": destino,
            }
            self._files[transferencia["token"]] = arquivo_info
        self._emit(
            "arquivo",
            mensagem=f'Arquivo "{nome}" recebido de {remetente}.',
            arquivo={k: v for k, v in arquivo_info.items() if k != "caminho"},
        )

    def _limpar_transferencias_incompletas(self):
        for transferencia in self._assemblies.values():
            try:
                transferencia["arquivo"].close()
            except OSError:
                pass
            try:
                transferencia["temporario"].unlink(missing_ok=True)
            except OSError:
                pass
        self._assemblies.clear()

    def eventos_desde(self, cursor=0):
        try:
            cursor = max(0, int(cursor))
        except (TypeError, ValueError):
            cursor = 0
        with self._lock:
            eventos = [dict(item) for item in self._events if item["id"] > cursor]
            ultimo = self._next_event_id - 1
        return eventos, ultimo

    def listar_arquivos(self):
        with self._lock:
            return [
                {k: v for k, v in info.items() if k != "caminho"}
                for info in self._files.values()
            ]

    def caminho_arquivo(self, token):
        with self._lock:
            info = self._files.get(str(token))
            return info["caminho"] if info else None

    def enviar_mensagem(self, mensagem, destino=None):
        mensagem = str(mensagem or "").strip()
        if not mensagem:
            raise ValueError("Digite uma mensagem antes de enviar.")
        if "\n" in mensagem or "\r" in mensagem:
            raise ValueError("Envie uma mensagem por vez, sem quebra de linha.")
        if len(mensagem.encode("utf-8")) > 4096:
            raise ValueError("A mensagem ultrapassa 4096 bytes.")
        destino = self.validar_destino(destino)
        linha = f"#{destino} {mensagem}\n" if destino else f"{mensagem}\n"
        self._enviar_bytes(linha.encode("utf-8"))
        self._emit(
            "enviada",
            mensagem=mensagem,
            destinatario=destino or "todos",
        )

    def enviar_arquivo(self, nome, conteudo, destino=None):
        conteudo = bytes(conteudo)
        if len(conteudo) > self.MAX_FILE_SIZE:
            raise ValueError("O arquivo ultrapassa o limite de 10 MB.")
        nome = Path(str(nome or "arquivo.bin")).name.strip()
        nome = re.sub(r"\s+", "_", nome)
        if not nome or nome in {".", ".."}:
            raise ValueError("Nome de arquivo inválido.")
        destino = self.validar_destino(destino)
        prefixo = f"#{destino} " if destino else ""
        with self._send_lock:
            conexao = self._obter_socket()
            for inicio in range(0, len(conteudo), self.CHUNK_SIZE):
                pedaco = conteudo[inicio:inicio + self.CHUNK_SIZE]
                cabecalho = (
                    f"{prefixo}/arquivo {len(pedaco)} {nome}\n".encode("utf-8")
                )
                conexao.sendall(cabecalho + pedaco)
            cabecalho_final = f"{prefixo}/arquivo 0 {nome}\n".encode("utf-8")
            conexao.sendall(cabecalho_final)
        self._emit(
            "enviada",
            mensagem=f'Arquivo "{nome}" enviado ({len(conteudo)} bytes).',
            destinatario=destino or "todos",
        )

    def _obter_socket(self):
        with self._lock:
            conexao = self._socket
            estado = self._state
        if not conexao or estado != "conectado":
            raise RuntimeError("O cliente não está conectado ao servidor socket.")
        return conexao

    def _enviar_bytes(self, dados):
        with self._send_lock:
            conexao = self._obter_socket()
            conexao.sendall(dados)


gateway_socket = SocketGateway(Path(__file__).resolve().parent / "socket_recebidos")
