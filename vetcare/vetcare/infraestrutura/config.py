"""Configuração externalizada (tática de manutenibilidade).

Tudo pode ser alterado por variáveis de ambiente, sem mexer no código.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


@dataclass(frozen=True)
class Configuracao:
    caminho_banco: str = field(default_factory=lambda: os.environ.get("VETCARE_DB", "vetcare.db"))
    segredo_token: str = field(
        default_factory=lambda: os.environ.get("VETCARE_SEGREDO") or secrets.token_urlsafe(48)
    )
    horas_validade_token: int = field(default_factory=lambda: _int("VETCARE_TOKEN_HORAS", 8))
    max_tentativas_login: int = field(default_factory=lambda: _int("VETCARE_MAX_TENTATIVAS", 5))
    minutos_bloqueio: int = field(default_factory=lambda: _int("VETCARE_MINUTOS_BLOQUEIO", 15))
    custo_hash_log2: int = field(default_factory=lambda: _int("VETCARE_CUSTO_HASH", 17))
    duracao_consulta_min: int = field(default_factory=lambda: _int("VETCARE_DURACAO_CONSULTA", 30))
    hora_abertura: int = field(default_factory=lambda: _int("VETCARE_HORA_ABERTURA", 8))
    hora_fechamento: int = field(default_factory=lambda: _int("VETCARE_HORA_FECHAMENTO", 18))
    admin_email: str = field(
        default_factory=lambda: os.environ.get("VETCARE_ADMIN_EMAIL", "admin@vetcare.local")
    )
    admin_senha: str = field(
        default_factory=lambda: os.environ.get("VETCARE_ADMIN_SENHA", "Admin@123")
    )
