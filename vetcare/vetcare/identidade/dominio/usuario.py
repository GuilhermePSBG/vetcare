"""Entidade Usuário e regras de bloqueio por tentativas falhas."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from vetcare.compartilhado.excecoes import DadosInvalidos
from vetcare.compartilhado.tipos import Perfil, texto_obrigatorio, validar_email


def validar_perfil(valor: object) -> Perfil:
    try:
        return Perfil(str(valor).upper())
    except ValueError:
        opcoes = ", ".join(p.value for p in Perfil)
        raise DadosInvalidos(f"Perfil inválido. Use um de: {opcoes}.", {"campo": "perfil"})


def validar_senha(senha: object) -> str:
    """Política mínima: 8+ caracteres, com letra e número."""
    if not isinstance(senha, str) or len(senha) < 8:
        raise DadosInvalidos("A senha deve ter pelo menos 8 caracteres.", {"campo": "senha"})
    if not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
        raise DadosInvalidos("A senha deve conter letras e números.", {"campo": "senha"})
    return senha


@dataclass
class Usuario:
    nome: str
    email: str
    perfil: Perfil
    hash_senha: str
    ativo: bool = True
    tentativas_falhas: int = 0
    bloqueado_ate: datetime | None = None
    id: int | None = None
    criado_em: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))

    @classmethod
    def novo(cls, nome: object, email: object, perfil: object, hash_senha: str) -> "Usuario":
        return cls(
            nome=texto_obrigatorio(nome, "nome"),
            email=validar_email(email),
            perfil=validar_perfil(perfil),
            hash_senha=hash_senha,
        )

    def esta_bloqueado(self, agora: datetime) -> bool:
        return self.bloqueado_ate is not None and agora < self.bloqueado_ate

    def registrar_falha(self, agora: datetime, max_tentativas: int, minutos_bloqueio: int) -> None:
        self.tentativas_falhas += 1
        if self.tentativas_falhas >= max_tentativas:
            self.bloqueado_ate = agora + timedelta(minutes=minutos_bloqueio)
            self.tentativas_falhas = 0

    def registrar_sucesso(self) -> None:
        self.tentativas_falhas = 0
        self.bloqueado_ate = None
