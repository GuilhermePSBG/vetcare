"""Serviços de aplicação do módulo Identidade e Acesso (REQ 01 e REQ 02)."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from vetcare.compartilhado.eventos import EventoDeDominio, PublicadorDeEventos
from vetcare.compartilhado.excecoes import (
    Conflito,
    ContaBloqueada,
    DadosInvalidos,
    NaoAutenticado,
    NaoEncontrado,
)
from vetcare.compartilhado.tipos import (
    Pagina,
    Paginacao,
    Perfil,
    UsuarioAutenticado,
    texto_obrigatorio,
    validar_email,
)

from ..dominio.portas import GeradorDeHash, ProvedorDeToken, RepositorioDeUsuarios
from ..dominio.usuario import Usuario, validar_perfil, validar_senha

Relogio = Callable[[], datetime]


class UsuarioService:
    """REQ 01 - Manter Usuário: inclusão, alteração, exclusão e consulta."""

    def __init__(
        self,
        repositorio: RepositorioDeUsuarios,
        hash_senha: GeradorDeHash,
        eventos: PublicadorDeEventos,
    ) -> None:
        self._repo = repositorio
        self._hash = hash_senha
        self._eventos = eventos

    def criar(self, dados: dict, autor: UsuarioAutenticado | None) -> Usuario:
        senha = validar_senha(dados.get("senha"))
        usuario = Usuario.novo(dados.get("nome"), dados.get("email"), dados.get("perfil"), "")
        if self._repo.obter_por_email(usuario.email):
            raise Conflito("Já existe um usuário com este e-mail.", {"campo": "email"})
        usuario.hash_senha = self._hash.gerar(senha)
        usuario = self._repo.salvar(usuario)
        self._publicar("UsuarioCriado", usuario, autor)
        return usuario

    def alterar(self, id: int, dados: dict, autor: UsuarioAutenticado) -> Usuario:
        usuario = self.obter(id)
        if "nome" in dados:
            usuario.nome = texto_obrigatorio(dados["nome"], "nome")
        if "email" in dados:
            email = validar_email(dados["email"])
            existente = self._repo.obter_por_email(email)
            if existente and existente.id != usuario.id:
                raise Conflito("Já existe um usuário com este e-mail.", {"campo": "email"})
            usuario.email = email
        if "perfil" in dados:
            novo_perfil = validar_perfil(dados["perfil"])
            if usuario.perfil == Perfil.ADMINISTRADOR and novo_perfil != Perfil.ADMINISTRADOR:
                self._garantir_outro_admin(usuario)
            usuario.perfil = novo_perfil
        if "ativo" in dados:
            ativo = bool(dados["ativo"])
            if not ativo and usuario.id == autor.id:
                raise DadosInvalidos("Você não pode desativar o próprio usuário.")
            if not ativo and usuario.perfil == Perfil.ADMINISTRADOR:
                self._garantir_outro_admin(usuario)
            usuario.ativo = ativo
        if dados.get("senha"):
            usuario.hash_senha = self._hash.gerar(validar_senha(dados["senha"]))
            usuario.registrar_sucesso()
        usuario = self._repo.salvar(usuario)
        self._publicar("UsuarioAlterado", usuario, autor)
        return usuario

    def excluir(self, id: int, autor: UsuarioAutenticado) -> None:
        usuario = self.obter(id)
        if usuario.id == autor.id:
            raise DadosInvalidos("Você não pode excluir o próprio usuário.")
        if usuario.perfil == Perfil.ADMINISTRADOR:
            self._garantir_outro_admin(usuario)
        self._repo.excluir(id)
        self._publicar("UsuarioExcluido", usuario, autor)

    def obter(self, id: int) -> Usuario:
        usuario = self._repo.obter(id)
        if usuario is None:
            raise NaoEncontrado("Usuário não encontrado.")
        return usuario

    def listar(self, paginacao: Paginacao, busca: str | None = None) -> Pagina[Usuario]:
        return self._repo.listar(paginacao, busca)

    def _garantir_outro_admin(self, usuario: Usuario) -> None:
        if usuario.ativo and self._repo.contar_admins_ativos() <= 1:
            raise Conflito("O sistema precisa manter pelo menos um administrador ativo.")

    def _publicar(self, nome: str, usuario: Usuario, autor: UsuarioAutenticado | None) -> None:
        self._eventos.publicar(
            EventoDeDominio(
                nome, {"usuario_id": usuario.id, "email": usuario.email}, autor.id if autor else None
            )
        )


class AutenticacaoService:
    """REQ 02 - Autenticar Usuário, com bloqueio temporário após falhas."""

    MENSAGEM_GENERICA = "E-mail ou senha inválidos."

    def __init__(
        self,
        repositorio: RepositorioDeUsuarios,
        hash_senha: GeradorDeHash,
        tokens: ProvedorDeToken,
        eventos: PublicadorDeEventos,
        max_tentativas: int = 5,
        minutos_bloqueio: int = 15,
        relogio: Relogio = datetime.now,
    ) -> None:
        self._repo = repositorio
        self._hash = hash_senha
        self._tokens = tokens
        self._eventos = eventos
        self._max = max_tentativas
        self._minutos = minutos_bloqueio
        self._agora = relogio
        # Hash real de uma senha aleatória: igualar o custo quando o e-mail não existe.
        self._hash_ficticio = hash_senha.gerar("senha-ficticia-para-tempo-constante")

    def login(self, email: object, senha: object, ip: str | None = None) -> tuple[str, Usuario]:
        if not isinstance(email, str) or not isinstance(senha, str) or not email or not senha:
            raise DadosInvalidos("Informe e-mail e senha.")
        usuario = self._repo.obter_por_email(email.strip().lower())
        agora = self._agora()
        if usuario is None or not usuario.ativo:
            # Mesmo custo e mesma mensagem: não revela se o e-mail existe.
            self._hash.verificar(senha, self._hash_ficticio)
            self._registrar("LoginFalhou", None, {"email": str(email)[:160], "ip": ip})
            raise NaoAutenticado(self.MENSAGEM_GENERICA)
        if usuario.esta_bloqueado(agora):
            raise ContaBloqueada(
                "Conta bloqueada temporariamente por excesso de tentativas. Tente mais tarde.",
                {"bloqueado_ate": usuario.bloqueado_ate.isoformat(timespec="minutes")},
            )
        if not self._hash.verificar(senha, usuario.hash_senha):
            usuario.registrar_falha(agora, self._max, self._minutos)
            self._repo.salvar(usuario)
            self._registrar("LoginFalhou", usuario.id, {"email": usuario.email, "ip": ip})
            if usuario.esta_bloqueado(agora):
                raise ContaBloqueada(
                    "Conta bloqueada temporariamente por excesso de tentativas. Tente mais tarde.",
                    {"bloqueado_ate": usuario.bloqueado_ate.isoformat(timespec="minutes")},
                )
            raise NaoAutenticado(self.MENSAGEM_GENERICA)
        usuario.registrar_sucesso()
        self._repo.salvar(usuario)
        self._registrar("LoginRealizado", usuario.id, {"email": usuario.email, "ip": ip})
        return self._tokens.emitir(usuario.id, usuario.perfil.value), usuario

    def autenticar_token(self, token: str) -> UsuarioAutenticado:
        declaracoes = self._tokens.validar(token)
        usuario = self._repo.obter(int(declaracoes["sub"]))
        # Revalida no banco: usuário desativado ou com perfil alterado perde o acesso.
        if usuario is None or not usuario.ativo:
            raise NaoAutenticado("Sessão inválida. Faça login novamente.")
        return UsuarioAutenticado(usuario.id, usuario.nome, usuario.email, usuario.perfil)

    def _registrar(self, nome: str, usuario_id: int | None, dados: dict) -> None:
        self._eventos.publicar(EventoDeDominio(nome, dados, usuario_id))
