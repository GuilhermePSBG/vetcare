"""Contrato neutro entre os adaptadores HTTP dos módulos e a fachada da API.

Os módulos descrevem suas rotas com `Rota` e recebem uma `Requisicao` já
autenticada. A fachada (vetcare/app.py) converte isso para Starlette e aplica
autenticação e autorização em todas as rotas, num só lugar (ADR-003).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from vetcare.compartilhado.excecoes import DadosInvalidos
from vetcare.compartilhado.tipos import Paginacao, UsuarioAutenticado


@dataclass
class Requisicao:
    parametros: dict[str, Any] = field(default_factory=dict)
    consulta: dict[str, str] = field(default_factory=dict)
    corpo: dict[str, Any] = field(default_factory=dict)
    usuario: UsuarioAutenticado | None = None
    ip: str | None = None

    def id(self, nome: str = "id") -> int:
        try:
            return int(self.parametros[nome])
        except (KeyError, ValueError):
            raise DadosInvalidos(f"Parâmetro '{nome}' inválido.")

    def paginacao(self) -> Paginacao:
        try:
            pagina = int(self.consulta.get("pagina", 1))
            tamanho = int(self.consulta.get("tamanho", 20))
        except ValueError:
            raise DadosInvalidos("Parâmetros de paginação inválidos.")
        return Paginacao(pagina, tamanho)


@dataclass
class Resposta:
    status: int
    corpo: Any = None


Manipulador = Callable[[Requisicao], Resposta]


@dataclass(frozen=True)
class Rota:
    metodo: str
    caminho: str
    manipulador: Manipulador
    permissao: str | None  # None = rota pública (ex.: login)


def pagina_para_json(pagina, serializar: Callable[[Any], dict]) -> dict:
    return {
        "itens": [serializar(item) for item in pagina.itens],
        "total": pagina.total,
        "pagina": pagina.pagina,
        "tamanho": pagina.tamanho,
    }
