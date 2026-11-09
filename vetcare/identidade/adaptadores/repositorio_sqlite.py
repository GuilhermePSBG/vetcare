"""Adaptador de saída: UsuarioRepository em SQLite. O módulo é dono da tabela `usuarios`."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from vetcare.compartilhado.tipos import Pagina, Paginacao, Perfil
from vetcare.infraestrutura.banco import BancoDeDados

from ..dominio.usuario import Usuario

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    perfil            TEXT NOT NULL CHECK (perfil IN ('ADMINISTRADOR','RECEPCIONISTA','VETERINARIO')),
    hash_senha        TEXT NOT NULL,
    ativo             INTEGER NOT NULL DEFAULT 1,
    tentativas_falhas INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate     TEXT,
    criado_em         TEXT NOT NULL
);
"""


def _para_entidade(linha: sqlite3.Row) -> Usuario:
    return Usuario(
        id=linha["id"],
        nome=linha["nome"],
        email=linha["email"],
        perfil=Perfil(linha["perfil"]),
        hash_senha=linha["hash_senha"],
        ativo=bool(linha["ativo"]),
        tentativas_falhas=linha["tentativas_falhas"],
        bloqueado_ate=datetime.fromisoformat(linha["bloqueado_ate"]) if linha["bloqueado_ate"] else None,
        criado_em=datetime.fromisoformat(linha["criado_em"]),
    )


class RepositorioDeUsuariosSQLite:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def salvar(self, u: Usuario) -> Usuario:
        valores = (
            u.nome,
            u.email,
            u.perfil.value,
            u.hash_senha,
            int(u.ativo),
            u.tentativas_falhas,
            u.bloqueado_ate.isoformat() if u.bloqueado_ate else None,
        )
        with self._banco.transacao() as c:
            if u.id is None:
                cur = c.execute(
                    "INSERT INTO usuarios (nome, email, perfil, hash_senha, ativo, tentativas_falhas,"
                    " bloqueado_ate, criado_em) VALUES (?,?,?,?,?,?,?,?)",
                    (*valores, u.criado_em.isoformat()),
                )
                u.id = cur.lastrowid
            else:
                c.execute(
                    "UPDATE usuarios SET nome=?, email=?, perfil=?, hash_senha=?, ativo=?,"
                    " tentativas_falhas=?, bloqueado_ate=? WHERE id=?",
                    (*valores, u.id),
                )
        return u

    def obter(self, id: int) -> Usuario | None:
        with self._banco.transacao() as c:
            linha = c.execute("SELECT * FROM usuarios WHERE id=?", (id,)).fetchone()
        return _para_entidade(linha) if linha else None

    def obter_por_email(self, email: str) -> Usuario | None:
        with self._banco.transacao() as c:
            linha = c.execute("SELECT * FROM usuarios WHERE email=?", (email.lower(),)).fetchone()
        return _para_entidade(linha) if linha else None

    def listar(self, paginacao: Paginacao, busca: str | None) -> Pagina[Usuario]:
        filtro, args = "", []
        if busca:
            filtro = "WHERE nome LIKE ? OR email LIKE ?"
            args = [f"%{busca}%", f"%{busca}%"]
        with self._banco.transacao() as c:
            total = c.execute(f"SELECT COUNT(*) FROM usuarios {filtro}", args).fetchone()[0]
            linhas = c.execute(
                f"SELECT * FROM usuarios {filtro} ORDER BY nome LIMIT ? OFFSET ?",
                [*args, paginacao.tamanho, paginacao.offset],
            ).fetchall()
        return Pagina([_para_entidade(l) for l in linhas], total, paginacao.pagina, paginacao.tamanho)

    def excluir(self, id: int) -> None:
        with self._banco.transacao() as c:
            c.execute("DELETE FROM usuarios WHERE id=?", (id,))

    def contar_admins_ativos(self) -> int:
        with self._banco.transacao() as c:
            return c.execute(
                "SELECT COUNT(*) FROM usuarios WHERE perfil='ADMINISTRADOR' AND ativo=1"
            ).fetchone()[0]
