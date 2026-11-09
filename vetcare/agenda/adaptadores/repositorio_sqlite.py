"""ConsultaRepository em SQLite. O módulo Agenda é dono da tabela `consultas`."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from vetcare.compartilhado.excecoes import Conflito
from vetcare.infraestrutura.banco import BancoDeDados

from ..dominio.consulta import Consulta, StatusConsulta

ESQUEMA = """
CREATE TABLE IF NOT EXISTS consultas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    animal_id       INTEGER NOT NULL REFERENCES animais(id) ON DELETE RESTRICT,
    tutor_id        INTEGER NOT NULL REFERENCES tutores(id) ON DELETE RESTRICT,
    veterinario_id  INTEGER NOT NULL REFERENCES veterinarios(id) ON DELETE RESTRICT,
    inicio          TEXT NOT NULL,
    duracao_min     INTEGER NOT NULL CHECK (duracao_min > 0),
    motivo          TEXT,
    status          TEXT NOT NULL CHECK (status IN ('AGENDADA','CANCELADA','REALIZADA')),
    criado_por      INTEGER,
    criado_em       TEXT NOT NULL
);
-- Restrição única (veterinário + data/hora ativa): impede dupla marcação
-- mesmo com requisições simultâneas (Etapa 1, seção 5.2.2 / ADR-004).
CREATE UNIQUE INDEX IF NOT EXISTS ux_consulta_vet_horario_ativo
    ON consultas(veterinario_id, inicio) WHERE status = 'AGENDADA';
-- Índices das consultas mais frequentes (ADR-009).
CREATE INDEX IF NOT EXISTS ix_consultas_inicio ON consultas(inicio);
CREATE INDEX IF NOT EXISTS ix_consultas_vet_inicio ON consultas(veterinario_id, inicio);
CREATE INDEX IF NOT EXISTS ix_consultas_animal_inicio ON consultas(animal_id, inicio);
"""


def _consulta(l: sqlite3.Row) -> Consulta:
    return Consulta(
        id=l["id"], animal_id=l["animal_id"], tutor_id=l["tutor_id"],
        veterinario_id=l["veterinario_id"], inicio=datetime.fromisoformat(l["inicio"]),
        duracao_min=l["duracao_min"], motivo=l["motivo"], status=StatusConsulta(l["status"]),
        criado_por=l["criado_por"], criado_em=datetime.fromisoformat(l["criado_em"]),
    )


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


class RepositorioDeConsultasSQLite:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def salvar(self, c: Consulta) -> Consulta:
        valores = (
            c.animal_id, c.tutor_id, c.veterinario_id, _iso(c.inicio), c.duracao_min,
            c.motivo, c.status.value, c.criado_por,
        )
        try:
            with self._banco.transacao() as cx:
                if c.id is None:
                    c.id = cx.execute(
                        "INSERT INTO consultas (animal_id, tutor_id, veterinario_id, inicio, duracao_min,"
                        " motivo, status, criado_por, criado_em) VALUES (?,?,?,?,?,?,?,?,?)",
                        (*valores, c.criado_em.isoformat()),
                    ).lastrowid
                else:
                    cx.execute(
                        "UPDATE consultas SET animal_id=?, tutor_id=?, veterinario_id=?, inicio=?,"
                        " duracao_min=?, motivo=?, status=?, criado_por=? WHERE id=?",
                        (*valores, c.id),
                    )
        except sqlite3.IntegrityError as erro:
            if "UNIQUE" in str(erro):
                raise Conflito("O veterinário já possui consulta neste horário.", {"campo": "inicio"})
            raise
        return c

    def obter(self, id: int) -> Consulta | None:
        with self._banco.transacao() as cx:
            l = cx.execute("SELECT * FROM consultas WHERE id=?", (id,)).fetchone()
        return _consulta(l) if l else None

    def _buscar(self, filtro: str, args: list) -> list[Consulta]:
        with self._banco.transacao() as cx:
            linhas = cx.execute(f"SELECT * FROM consultas WHERE {filtro} ORDER BY inicio", args).fetchall()
        return [_consulta(l) for l in linhas]

    def do_veterinario(self, veterinario_id: int, inicio: datetime, fim: datetime) -> list[Consulta]:
        return self._buscar("veterinario_id=? AND inicio>=? AND inicio<?", [veterinario_id, _iso(inicio), _iso(fim)])

    def do_animal(self, animal_id: int, inicio: datetime, fim: datetime) -> list[Consulta]:
        return self._buscar("animal_id=? AND inicio>=? AND inicio<?", [animal_id, _iso(inicio), _iso(fim)])

    def no_periodo(self, inicio: datetime, fim: datetime, veterinario_id: int | None) -> list[Consulta]:
        filtro, args = "inicio>=? AND inicio<?", [_iso(inicio), _iso(fim)]
        if veterinario_id:
            filtro += " AND veterinario_id=?"
            args.append(veterinario_id)
        return self._buscar(filtro, args)
