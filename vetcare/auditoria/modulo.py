"""Módulo Auditoria (ADR-008): trilha somente de inserção alimentada por eventos.

Os outros módulos não conhecem a Auditoria: ela apenas se inscreve no
barramento e grava cada evento. Gatilhos no banco impedem UPDATE e DELETE.
"""
from __future__ import annotations

import json

from vetcare.compartilhado.eventos import EventoDeDominio
from vetcare.infraestrutura.banco import BancoDeDados
from vetcare.infraestrutura.http import Requisicao, Resposta, Rota

ESQUEMA = """
CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    evento      TEXT NOT NULL,
    usuario_id  INTEGER,
    dados       TEXT NOT NULL,
    ocorrido_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_auditoria_ocorrido ON auditoria(ocorrido_em);
CREATE TRIGGER IF NOT EXISTS tg_auditoria_sem_update BEFORE UPDATE ON auditoria
BEGIN SELECT RAISE(ABORT, 'auditoria e somente de insercao'); END;
CREATE TRIGGER IF NOT EXISTS tg_auditoria_sem_delete BEFORE DELETE ON auditoria
BEGIN SELECT RAISE(ABORT, 'auditoria e somente de insercao'); END;
"""


class TrilhaDeAuditoria:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def registrar(self, evento: EventoDeDominio) -> None:
        with self._banco.transacao() as c:
            c.execute(
                "INSERT INTO auditoria (evento, usuario_id, dados, ocorrido_em) VALUES (?,?,?,?)",
                (evento.nome, evento.usuario_id, json.dumps(evento.dados, ensure_ascii=False), evento.ocorrido_em),
            )

    def listar(self, limite: int = 100) -> list[dict]:
        with self._banco.transacao() as c:
            linhas = c.execute(
                "SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (max(1, min(limite, 500)),)
            ).fetchall()
        return [
            {
                "id": l["id"], "evento": l["evento"], "usuario_id": l["usuario_id"],
                "dados": json.loads(l["dados"]), "ocorrido_em": l["ocorrido_em"],
            }
            for l in linhas
        ]

    def rotas(self) -> list[Rota]:
        def listar(req: Requisicao) -> Resposta:
            return Resposta(200, {"itens": self.listar(int(req.consulta.get("limite", 100)))})

        return [Rota("GET", "/api/auditoria", listar, "auditoria:ler")]
