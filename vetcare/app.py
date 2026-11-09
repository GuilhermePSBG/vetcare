"""Ponto de composição e fachada da API REST do VetCare.

- Instancia os adaptadores e liga as portas de cada módulo (injeção de dependência).
- Converte as `Rota`s dos módulos em rotas Starlette, aplicando autenticação por
  token e autorização por perfil (RBAC) em TODAS as rotas, num só lugar (ADR-003).
- Converte exceções de domínio em erros JSON padronizados.
- Serve o Portal Web (SPA) a partir de vetcare/web/static.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from vetcare.agenda.adaptadores import http as agenda_http
from vetcare.agenda.adaptadores.repositorio_sqlite import ESQUEMA as ESQUEMA_AGENDA
from vetcare.agenda.adaptadores.repositorio_sqlite import RepositorioDeConsultasSQLite
from vetcare.agenda.aplicacao.servicos import AgendamentoService
from vetcare.agenda.dominio.consulta import DisponibilidadeService, HorarioDeFuncionamento
from vetcare.auditoria.modulo import ESQUEMA as ESQUEMA_AUDITORIA
from vetcare.auditoria.modulo import TrilhaDeAuditoria
from vetcare.cadastro.adaptadores import http as cadastro_http
from vetcare.cadastro.adaptadores.repositorio_sqlite import ESQUEMA as ESQUEMA_CADASTRO
from vetcare.cadastro.adaptadores.repositorio_sqlite import (
    RepositorioDeAnimaisSQLite,
    RepositorioDeTutoresSQLite,
    RepositorioDeVeterinariosSQLite,
)
from vetcare.cadastro.aplicacao.servicos import AnimalService, TutorService, VeterinarioService
from vetcare.cadastro.api import CadastroPort
from vetcare.compartilhado.eventos import BarramentoDeEventos
from vetcare.compartilhado.excecoes import DadosInvalidos, ErroDeDominio, NaoAutenticado
from vetcare.compartilhado.tipos import Perfil
from vetcare.identidade.adaptadores import http as identidade_http
from vetcare.identidade.adaptadores.hash_scrypt import HashScrypt
from vetcare.identidade.adaptadores.repositorio_sqlite import ESQUEMA as ESQUEMA_IDENTIDADE
from vetcare.identidade.adaptadores.repositorio_sqlite import RepositorioDeUsuariosSQLite
from vetcare.identidade.adaptadores.token_jwt import TokenJWT
from vetcare.identidade.aplicacao.servicos import AutenticacaoService, UsuarioService
from vetcare.identidade.api import IdentidadeAPI
from vetcare.identidade.dominio.usuario import Usuario
from vetcare.infraestrutura.banco import BancoDeDados
from vetcare.infraestrutura.config import Configuracao
from vetcare.infraestrutura.http import Requisicao, Rota

log = logging.getLogger("vetcare")
PASTA_WEB = Path(__file__).parent / "web" / "static"


@dataclass
class Contexto:
    """Tudo o que foi montado - útil para testes e para o script de dados de exemplo."""

    config: Configuracao
    banco: BancoDeDados
    eventos: BarramentoDeEventos
    identidade: IdentidadeAPI
    usuarios: UsuarioService
    autenticacao: AutenticacaoService
    tutores: TutorService
    animais: AnimalService
    veterinarios: VeterinarioService
    agenda: AgendamentoService
    auditoria: TrilhaDeAuditoria
    rotas: list[Rota]


def montar(config: Configuracao | None = None) -> Contexto:
    config = config or Configuracao()
    banco = BancoDeDados(config.caminho_banco)
    # Ordem importa: Agenda referencia tabelas do Cadastro.
    banco.aplicar_esquema(ESQUEMA_IDENTIDADE, ESQUEMA_CADASTRO, ESQUEMA_AGENDA, ESQUEMA_AUDITORIA)

    eventos = BarramentoDeEventos()
    auditoria = TrilhaDeAuditoria(banco)
    eventos.inscrever("*", auditoria.registrar)

    # Identidade e Acesso
    repo_usuarios = RepositorioDeUsuariosSQLite(banco)
    hash_senha = HashScrypt(config.custo_hash_log2)
    usuarios = UsuarioService(repo_usuarios, hash_senha, eventos)
    autenticacao = AutenticacaoService(
        repo_usuarios, hash_senha, TokenJWT(config.segredo_token, config.horas_validade_token),
        eventos, config.max_tentativas_login, config.minutos_bloqueio,
    )
    identidade = IdentidadeAPI(autenticacao)

    # Cadastro (Tutores e Animais + Equipe Clínica)
    repo_tutores = RepositorioDeTutoresSQLite(banco)
    tutores = TutorService(repo_tutores, eventos)
    animais = AnimalService(RepositorioDeAnimaisSQLite(banco), repo_tutores, eventos)
    veterinarios = VeterinarioService(RepositorioDeVeterinariosSQLite(banco), eventos)
    cadastro_port = CadastroPort(tutores, animais, veterinarios)

    # Agenda - consome o Cadastro apenas pela interface pública (CadastroPort)
    agenda = AgendamentoService(
        RepositorioDeConsultasSQLite(banco),
        cadastro_port,
        DisponibilidadeService(
            HorarioDeFuncionamento(config.hora_abertura, config.hora_fechamento),
            config.duracao_consulta_min,
        ),
        eventos,
        unidade_de_trabalho=banco.transacao,
    )

    _garantir_administrador(repo_usuarios, hash_senha, config)

    rotas = [
        *identidade_http.criar_rotas(usuarios, autenticacao),
        *cadastro_http.criar_rotas(tutores, animais, veterinarios),
        *agenda_http.criar_rotas(agenda, cadastro_port),
        *auditoria.rotas(),
    ]
    return Contexto(config, banco, eventos, identidade, usuarios, autenticacao, tutores, animais,
                    veterinarios, agenda, auditoria, rotas)


def _garantir_administrador(repo, hash_senha, config: Configuracao) -> None:
    """Na primeira execução cria o administrador inicial (configurável por variáveis de ambiente)."""
    if repo.contar_admins_ativos() == 0 and repo.obter_por_email(config.admin_email) is None:
        repo.salvar(
            Usuario(nome="Administrador", email=config.admin_email, perfil=Perfil.ADMINISTRADOR,
                    hash_senha=hash_senha.gerar(config.admin_senha))
        )
        log.warning("Administrador inicial criado: %s (troque a senha!)", config.admin_email)


# --------------------------------------------------------------------- fachada HTTP
def _erro(status: int, codigo: str, mensagem: str, detalhes: dict | None = None) -> JSONResponse:
    return JSONResponse(
        {"erro": {"codigo": codigo, "mensagem": mensagem, "detalhes": detalhes or {}}}, status_code=status
    )


def _adaptar(rota: Rota, identidade: IdentidadeAPI):
    async def endpoint(request: Request) -> Response:
        try:
            corpo: dict = {}
            if request.method in ("POST", "PUT", "PATCH"):
                bruto = await request.body()
                if bruto:
                    try:
                        corpo = json.loads(bruto)
                    except json.JSONDecodeError:
                        raise DadosInvalidos("Corpo da requisição não é um JSON válido.")
                    if not isinstance(corpo, dict):
                        raise DadosInvalidos("O corpo da requisição deve ser um objeto JSON.")

            usuario = None
            if rota.permissao is not None:
                cabecalho = request.headers.get("authorization", "")
                if not cabecalho.lower().startswith("bearer "):
                    raise NaoAutenticado("Faça login para continuar.")
                usuario = await run_in_threadpool(identidade.autenticar, cabecalho[7:].strip())
                if rota.permissao != "autenticado":
                    identidade.exigir(usuario, rota.permissao)

            req = Requisicao(
                parametros=dict(request.path_params),
                consulta=dict(request.query_params),
                corpo=corpo,
                usuario=usuario,
                ip=request.client.host if request.client else None,
            )
            resposta = await run_in_threadpool(rota.manipulador, req)
            if resposta.status == 204:
                return Response(status_code=204)
            return JSONResponse(resposta.corpo, status_code=resposta.status)
        except ErroDeDominio as e:
            return _erro(e.status_http, e.codigo, e.mensagem, e.detalhes)
        except Exception:  # noqa: BLE001
            log.exception("Erro inesperado em %s %s", request.method, request.url.path)
            return _erro(500, "ERRO_INTERNO", "Ocorreu um erro inesperado. Tente novamente.")

    return endpoint


class CabecalhosDeSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
        )
        if request.url.path.startswith("/api/"):
            resposta.headers["Cache-Control"] = "no-store"
        return resposta


def criar_app(config: Configuracao | None = None) -> Starlette:
    ctx = montar(config)

    async def saude(_: Request) -> Response:
        try:
            with ctx.banco.transacao() as c:
                c.execute("SELECT 1")
            return JSONResponse({"status": "ok"})
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "erro"}, status_code=503)

    async def api_nao_encontrada(request: Request) -> Response:
        return _erro(404, "NAO_ENCONTRADO", "Rota da API não encontrada.")

    rotas_starlette = [Route("/api/saude", saude, methods=["GET"])]
    rotas_starlette += [
        Route(r.caminho, _adaptar(r, ctx.identidade), methods=[r.metodo]) for r in ctx.rotas
    ]
    rotas_starlette += [
        Route("/api/{resto:path}", api_nao_encontrada, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
        Mount("/", StaticFiles(directory=PASTA_WEB, html=True), name="web"),
    ]
    app = Starlette(routes=rotas_starlette, middleware=[Middleware(CabecalhosDeSeguranca)])
    app.state.contexto = ctx
    return app
