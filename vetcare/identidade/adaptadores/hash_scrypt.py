"""Adaptador de hash de senha com scrypt (biblioteca padrão). Ver ADR-012.

Padrão: N=2^17, r=8, p=1 - mínimo recomendado pela OWASP (Password Storage
Cheat Sheet) quando Argon2id não está disponível. Usa 128 MiB por verificação.
Os parâmetros ficam gravados junto do hash, permitindo aumentá-los no futuro.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_MAX_LOG2_N = 20  # não confia em parâmetros absurdos vindos do banco


class HashScrypt:
    def __init__(self, log2_n: int = 17, r: int = 8, p: int = 1) -> None:
        self.n, self.r, self.p = 2**log2_n, r, p

    @staticmethod
    def _derivar(senha: str, sal: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(
            senha.encode(), salt=sal, n=n, r=r, p=p, dklen=32, maxmem=128 * n * r * p + 2**24
        )

    def gerar(self, senha: str) -> str:
        sal = secrets.token_bytes(16)
        chave = self._derivar(senha, sal, self.n, self.r, self.p)
        return "$".join(
            ["scrypt", str(self.n), str(self.r), str(self.p),
             base64.b64encode(sal).decode(), base64.b64encode(chave).decode()]
        )

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        try:
            _, n, r, p, sal_b64, chave_b64 = hash_armazenado.split("$")
            n, r, p = int(n), int(r), int(p)
            if n > 2**_MAX_LOG2_N or r > 16 or p > 4:
                return False
            esperado = base64.b64decode(chave_b64)
            obtido = self._derivar(senha, base64.b64decode(sal_b64), n, r, p)
        except (ValueError, TypeError):
            return False
        return len(esperado) == 32 and hmac.compare_digest(obtido, esperado)
