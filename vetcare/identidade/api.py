"""Interface pública do módulo Identidade e Acesso.

É o único ponto que outros módulos (e a fachada da API) podem importar.
Expõe a AutorizacaoPort: `pode(usuario, acao)` e `exigir(usuario, acao)`.
"""
from __future__ import annotations

from vetcare.compartilhado.excecoes import AcessoNegado
from vetcare.compartilhado.tipos import UsuarioAutenticado

from .aplicacao.servicos import AutenticacaoService
from .dominio import politica_acesso


class AutorizacaoPort:
    def pode(self, usuario: UsuarioAutenticado, acao: str) -> bool:
        return politica_acesso.pode(usuario.perfil, acao)

    def exigir(self, usuario: UsuarioAutenticado | None, acao: str) -> None:
        if usuario is None or not self.pode(usuario, acao):
            raise AcessoNegado("Seu perfil não tem permissão para esta operação.")


class IdentidadeAPI(AutorizacaoPort):
    def __init__(self, autenticacao: AutenticacaoService) -> None:
        self._autenticacao = autenticacao

    def autenticar(self, token: str) -> UsuarioAutenticado:
        return self._autenticacao.autenticar_token(token)
