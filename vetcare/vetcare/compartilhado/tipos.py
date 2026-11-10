"""Tipos comuns e utilidades de validação usadas por mais de um módulo."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Generic, TypeVar

from .excecoes import DadosInvalidos

T = TypeVar("T")


class Perfil(str, Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    RECEPCIONISTA = "RECEPCIONISTA"
    VETERINARIO = "VETERINARIO"


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Identidade do usuário que faz a requisição, repassada aos módulos."""

    id: int
    nome: str
    email: str
    perfil: Perfil


@dataclass(frozen=True)
class Pagina(Generic[T]):
    itens: list[T]
    total: int
    pagina: int
    tamanho: int


@dataclass(frozen=True)
class Paginacao:
    pagina: int = 1
    tamanho: int = 20

    def __post_init__(self) -> None:
        if self.pagina < 1:
            raise DadosInvalidos("A página deve ser maior ou igual a 1.")
        if not 1 <= self.tamanho <= 100:
            raise DadosInvalidos("O tamanho da página deve estar entre 1 e 100.")

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.tamanho


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def texto_obrigatorio(valor: object, campo: str, maximo: int = 120) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise DadosInvalidos(f"O campo '{campo}' é obrigatório.", {"campo": campo})
    valor = valor.strip()
    if len(valor) > maximo:
        raise DadosInvalidos(
            f"O campo '{campo}' deve ter no máximo {maximo} caracteres.", {"campo": campo}
        )
    return valor


def texto_opcional(valor: object, campo: str, maximo: int = 120) -> str | None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    return texto_obrigatorio(valor, campo, maximo)


def validar_email(valor: object, campo: str = "email") -> str:
    email = texto_obrigatorio(valor, campo, 160).lower()
    if not _EMAIL_RE.match(email):
        raise DadosInvalidos("E-mail inválido.", {"campo": campo})
    return email


def validar_cpf(valor: object) -> str:
    """Valida CPF pelos dígitos verificadores e devolve só os números."""
    cpf = re.sub(r"\D", "", str(valor or ""))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise DadosInvalidos("CPF inválido.", {"campo": "cpf"})
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            raise DadosInvalidos("CPF inválido.", {"campo": "cpf"})
    return cpf


def validar_telefone(valor: object) -> str:
    telefone = re.sub(r"\D", "", str(valor or ""))
    if not 10 <= len(telefone) <= 11:
        raise DadosInvalidos(
            "Telefone deve ter DDD + número (10 ou 11 dígitos).", {"campo": "telefone"}
        )
    return telefone


def validar_data(valor: object, campo: str) -> date:
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        raise DadosInvalidos(f"O campo '{campo}' deve ser uma data AAAA-MM-DD.", {"campo": campo})


def validar_data_hora(valor: object, campo: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        raise DadosInvalidos(
            f"O campo '{campo}' deve ser data e hora no formato AAAA-MM-DDTHH:MM.", {"campo": campo}
        )
    return dt.replace(second=0, microsecond=0, tzinfo=None)


def inteiro_positivo(valor: object, campo: str) -> int:
    try:
        numero = int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise DadosInvalidos(f"O campo '{campo}' deve ser um número inteiro.", {"campo": campo})
    if numero <= 0:
        raise DadosInvalidos(f"O campo '{campo}' deve ser positivo.", {"campo": campo})
    return numero
