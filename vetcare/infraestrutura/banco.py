"""Adaptador de persistência compartilhado (SQLite).

Cada módulo é dono das próprias tabelas: o esquema de cada um fica no seu
adaptador de repositório e é aplicado aqui, no ponto de composição.
Ver ADR-010 (SQLite nesta sprint, PostgreSQL previsto para produção).
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator


class BancoDeDados:
    def __init__(self, caminho: str) -> None:
        self.caminho = caminho
        self._local = threading.local()

    def _nova_conexao(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho, timeout=10, isolation_level=None)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute("PRAGMA busy_timeout = 5000")
        if self.caminho != ":memory:":
            conexao.execute("PRAGMA journal_mode = WAL")
        return conexao

    def _conexao(self) -> sqlite3.Connection:
        conexao = getattr(self._local, "conexao", None)
        if conexao is None:
            conexao = self._nova_conexao()
            self._local.conexao = conexao
            self._local.profundidade = 0
        return conexao

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Transação ACID. Chamadas aninhadas participam da transação externa,
        o que permite a um serviço compor operações de mais de um repositório."""
        conexao = self._conexao()
        externa = self._local.profundidade == 0
        if externa:
            conexao.execute("BEGIN IMMEDIATE")
        self._local.profundidade += 1
        try:
            yield conexao
        except BaseException:
            self._local.profundidade -= 1
            if externa:
                conexao.execute("ROLLBACK")
            raise
        else:
            self._local.profundidade -= 1
            if externa:
                conexao.execute("COMMIT")

    def aplicar_esquema(self, *esquemas: str) -> None:
        conexao = self._conexao()
        for esquema in esquemas:
            conexao.executescript(esquema)

    def fechar(self) -> None:
        conexao = getattr(self._local, "conexao", None)
        if conexao is not None:
            conexao.close()
            self._local.conexao = None
