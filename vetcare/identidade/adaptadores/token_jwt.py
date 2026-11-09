"""Adaptador TokenProvider: JWT assinado (HS256) com expiração."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from vetcare.compartilhado.excecoes import NaoAutenticado


class TokenJWT:
    def __init__(self, segredo: str, horas_validade: int = 8) -> None:
        self._segredo = segredo
        self._validade = timedelta(hours=horas_validade)

    def emitir(self, usuario_id: int, perfil: str) -> str:
        agora = datetime.now(timezone.utc)
        return jwt.encode(
            {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": agora + self._validade},
            self._segredo,
            algorithm="HS256",
        )

    def validar(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._segredo, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        except jwt.ExpiredSignatureError:
            raise NaoAutenticado("Sessão expirada. Faça login novamente.")
        except jwt.PyJWTError:
            raise NaoAutenticado("Token inválido.")
