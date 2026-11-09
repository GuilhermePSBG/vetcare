"""Fixtures de teste. Não dependem de bibliotecas além de pytest:
o cliente HTTP chama a aplicação ASGI diretamente (sem rede)."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, time, timedelta

import pytest

from vetcare.app import criar_app
from vetcare.infraestrutura.config import Configuracao


class ClienteASGI:
    def __init__(self, app) -> None:
        self.app = app
        self.token: str | None = None

    def requisicao(self, metodo: str, caminho: str, corpo=None, token: str | None = "padrao"):
        token = self.token if token == "padrao" else token
        caminho, _, query = caminho.partition("?")
        cabecalhos = [(b"host", b"teste")]
        dados = b""
        if corpo is not None:
            dados = json.dumps(corpo).encode()
            cabecalhos.append((b"content-type", b"application/json"))
        if token:
            cabecalhos.append((b"authorization", f"Bearer {token}".encode()))
        escopo = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo,
            "path": caminho, "raw_path": caminho.encode(), "query_string": query.encode(),
            "headers": cabecalhos, "client": ("127.0.0.1", 5000), "server": ("teste", 80),
            "scheme": "http", "root_path": "",
        }
        resposta = {"status": None, "headers": {}, "corpo": b""}
        enviado = False

        async def receive():
            nonlocal enviado
            if not enviado:
                enviado = True
                return {"type": "http.request", "body": dados, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(msg):
            if msg["type"] == "http.response.start":
                resposta["status"] = msg["status"]
                resposta["headers"] = {k.decode(): v.decode() for k, v in msg["headers"]}
            elif msg["type"] == "http.response.body":
                resposta["corpo"] += msg.get("body", b"")

        asyncio.run(self.app(escopo, receive, send))
        return Resultado(resposta["status"], resposta["headers"], resposta["corpo"])

    def get(self, caminho, **kw):
        return self.requisicao("GET", caminho, **kw)

    def post(self, caminho, corpo=None, **kw):
        return self.requisicao("POST", caminho, corpo, **kw)

    def put(self, caminho, corpo=None, **kw):
        return self.requisicao("PUT", caminho, corpo, **kw)

    def delete(self, caminho, **kw):
        return self.requisicao("DELETE", caminho, **kw)

    def login(self, email: str, senha: str) -> str:
        r = self.post("/api/auth/login", {"email": email, "senha": senha}, token=None)
        assert r.status == 200, r.json
        self.token = r.json["token"]
        return self.token


class Resultado:
    def __init__(self, status, headers, corpo) -> None:
        self.status, self.headers, self.corpo = status, headers, corpo

    @property
    def json(self):
        return json.loads(self.corpo) if self.corpo else None


def proximo_dia_util() -> date:
    dia = date.today() + timedelta(days=1)
    while dia.weekday() == 6:
        dia += timedelta(days=1)
    return dia


def em(hora: int, minuto: int = 0, dia: date | None = None) -> str:
    return datetime.combine(dia or proximo_dia_util(), time(hora, minuto)).isoformat(timespec="minutes")


CPF_A = "52998224725"
CPF_B = "11144477735"


@pytest.fixture
def config(tmp_path) -> Configuracao:
    return Configuracao(
        caminho_banco=str(tmp_path / "teste.db"), segredo_token="segredo-de-teste-com-32-bytes-ou-mais!",
        admin_email="admin@teste.com", admin_senha="Admin@123",
        custo_hash_log2=12,  # custo baixo só para os testes rodarem rápido
    )


@pytest.fixture
def app(config):
    return criar_app(config)


@pytest.fixture
def ctx(app):
    return app.state.contexto


@pytest.fixture
def cliente(app) -> ClienteASGI:
    c = ClienteASGI(app)
    c.login("admin@teste.com", "Admin@123")
    return c
