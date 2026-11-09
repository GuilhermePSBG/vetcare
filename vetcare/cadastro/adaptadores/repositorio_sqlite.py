"""Adaptadores de saída do módulo Cadastro em SQLite.

O módulo é dono das tabelas `tutores`, `animais` e `veterinarios`.
Chaves estrangeiras de outros módulos (ex.: consultas -> animais) impedem
excluir registros com dependentes; o erro é traduzido para `Conflito`.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from vetcare.compartilhado.excecoes import Conflito
from vetcare.compartilhado.tipos import Pagina, Paginacao
from vetcare.infraestrutura.banco import BancoDeDados

from ..dominio.entidades import Animal, Especie, Sexo, Tutor, Veterinario

ESQUEMA = """
CREATE TABLE IF NOT EXISTS tutores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    cpf        TEXT NOT NULL UNIQUE,
    telefone   TEXT NOT NULL,
    email      TEXT,
    endereco   TEXT,
    criado_em  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tutores_nome ON tutores(nome);

CREATE TABLE IF NOT EXISTS animais (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id         INTEGER NOT NULL REFERENCES tutores(id) ON DELETE RESTRICT,
    nome             TEXT NOT NULL,
    especie          TEXT NOT NULL,
    raca             TEXT,
    sexo             TEXT NOT NULL CHECK (sexo IN ('M','F')),
    data_nascimento  TEXT NOT NULL,
    criado_em        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_animais_tutor ON animais(tutor_id);
CREATE INDEX IF NOT EXISTS ix_animais_nome ON animais(nome);

CREATE TABLE IF NOT EXISTS veterinarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nome           TEXT NOT NULL,
    crmv           TEXT NOT NULL UNIQUE,
    telefone       TEXT NOT NULL,
    email          TEXT NOT NULL,
    especialidade  TEXT,
    ativo          INTEGER NOT NULL DEFAULT 1,
    criado_em      TEXT NOT NULL
);
"""


def _excluir(banco: BancoDeDados, tabela: str, id: int, mensagem: str) -> None:
    try:
        with banco.transacao() as c:
            c.execute(f"DELETE FROM {tabela} WHERE id=?", (id,))
    except sqlite3.IntegrityError:
        raise Conflito(mensagem)


def _paginar(banco, sql_base: str, filtro: str, args: list, ordem: str, pag: Paginacao, conv):
    with banco.transacao() as c:
        total = c.execute(f"SELECT COUNT(*) FROM ({sql_base} {filtro})", args).fetchone()[0]
        linhas = c.execute(
            f"{sql_base} {filtro} ORDER BY {ordem} LIMIT ? OFFSET ?", [*args, pag.tamanho, pag.offset]
        ).fetchall()
    return Pagina([conv(l) for l in linhas], total, pag.pagina, pag.tamanho)


# ---------------------------------------------------------------- tutores
def _tutor(l: sqlite3.Row) -> Tutor:
    return Tutor(
        id=l["id"], nome=l["nome"], cpf=l["cpf"], telefone=l["telefone"], email=l["email"],
        endereco=l["endereco"], criado_em=datetime.fromisoformat(l["criado_em"]),
    )


class RepositorioDeTutoresSQLite:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def salvar(self, t: Tutor) -> Tutor:
        valores = (t.nome, t.cpf, t.telefone, t.email, t.endereco)
        with self._banco.transacao() as c:
            if t.id is None:
                t.id = c.execute(
                    "INSERT INTO tutores (nome, cpf, telefone, email, endereco, criado_em)"
                    " VALUES (?,?,?,?,?,?)", (*valores, t.criado_em.isoformat()),
                ).lastrowid
            else:
                c.execute(
                    "UPDATE tutores SET nome=?, cpf=?, telefone=?, email=?, endereco=? WHERE id=?",
                    (*valores, t.id),
                )
        return t

    def obter(self, id: int) -> Tutor | None:
        with self._banco.transacao() as c:
            l = c.execute("SELECT * FROM tutores WHERE id=?", (id,)).fetchone()
        return _tutor(l) if l else None

    def obter_por_cpf(self, cpf: str) -> Tutor | None:
        with self._banco.transacao() as c:
            l = c.execute("SELECT * FROM tutores WHERE cpf=?", (cpf,)).fetchone()
        return _tutor(l) if l else None

    def listar(self, paginacao: Paginacao, busca: str | None) -> Pagina[Tutor]:
        filtro, args = "", []
        if busca:
            filtro, args = "WHERE nome LIKE ? OR cpf LIKE ?", [f"%{busca}%", f"%{busca}%"]
        return _paginar(self._banco, "SELECT * FROM tutores", filtro, args, "nome", paginacao, _tutor)

    def excluir(self, id: int) -> None:
        _excluir(self._banco, "tutores", id,
                 "Não é possível excluir: o tutor possui animais cadastrados.")


# ---------------------------------------------------------------- animais
def _animal(l: sqlite3.Row) -> Animal:
    return Animal(
        id=l["id"], tutor_id=l["tutor_id"], nome=l["nome"], especie=Especie(l["especie"]),
        raca=l["raca"], sexo=Sexo(l["sexo"]), data_nascimento=date.fromisoformat(l["data_nascimento"]),
        criado_em=datetime.fromisoformat(l["criado_em"]),
    )


class RepositorioDeAnimaisSQLite:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def salvar(self, a: Animal) -> Animal:
        valores = (a.tutor_id, a.nome, a.especie.value, a.raca, a.sexo.value, a.data_nascimento.isoformat())
        with self._banco.transacao() as c:
            if a.id is None:
                a.id = c.execute(
                    "INSERT INTO animais (tutor_id, nome, especie, raca, sexo, data_nascimento, criado_em)"
                    " VALUES (?,?,?,?,?,?,?)", (*valores, a.criado_em.isoformat()),
                ).lastrowid
            else:
                c.execute(
                    "UPDATE animais SET tutor_id=?, nome=?, especie=?, raca=?, sexo=?, data_nascimento=?"
                    " WHERE id=?", (*valores, a.id),
                )
        return a

    def obter(self, id: int) -> Animal | None:
        with self._banco.transacao() as c:
            l = c.execute("SELECT * FROM animais WHERE id=?", (id,)).fetchone()
        return _animal(l) if l else None

    def listar(self, paginacao: Paginacao, busca: str | None, tutor_id: int | None) -> Pagina[Animal]:
        condicoes, args = [], []
        if busca:
            condicoes.append("nome LIKE ?")
            args.append(f"%{busca}%")
        if tutor_id:
            condicoes.append("tutor_id = ?")
            args.append(tutor_id)
        filtro = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""
        return _paginar(self._banco, "SELECT * FROM animais", filtro, args, "nome", paginacao, _animal)

    def excluir(self, id: int) -> None:
        _excluir(self._banco, "animais", id,
                 "Não é possível excluir: o animal possui consultas registradas.")


# ---------------------------------------------------------------- veterinários
def _vet(l: sqlite3.Row) -> Veterinario:
    return Veterinario(
        id=l["id"], nome=l["nome"], crmv=l["crmv"], telefone=l["telefone"], email=l["email"],
        especialidade=l["especialidade"], ativo=bool(l["ativo"]),
        criado_em=datetime.fromisoformat(l["criado_em"]),
    )


class RepositorioDeVeterinariosSQLite:
    def __init__(self, banco: BancoDeDados) -> None:
        self._banco = banco

    def salvar(self, v: Veterinario) -> Veterinario:
        valores = (v.nome, v.crmv, v.telefone, v.email, v.especialidade, int(v.ativo))
        with self._banco.transacao() as c:
            if v.id is None:
                v.id = c.execute(
                    "INSERT INTO veterinarios (nome, crmv, telefone, email, especialidade, ativo, criado_em)"
                    " VALUES (?,?,?,?,?,?,?)", (*valores, v.criado_em.isoformat()),
                ).lastrowid
            else:
                c.execute(
                    "UPDATE veterinarios SET nome=?, crmv=?, telefone=?, email=?, especialidade=?, ativo=?"
                    " WHERE id=?", (*valores, v.id),
                )
        return v

    def obter(self, id: int) -> Veterinario | None:
        with self._banco.transacao() as c:
            l = c.execute("SELECT * FROM veterinarios WHERE id=?", (id,)).fetchone()
        return _vet(l) if l else None

    def obter_por_crmv(self, crmv: str) -> Veterinario | None:
        with self._banco.transacao() as c:
            l = c.execute("SELECT * FROM veterinarios WHERE crmv=?", (crmv,)).fetchone()
        return _vet(l) if l else None

    def listar(self, paginacao: Paginacao, busca: str | None, somente_ativos: bool) -> Pagina[Veterinario]:
        condicoes, args = [], []
        if busca:
            condicoes.append("(nome LIKE ? OR crmv LIKE ? OR especialidade LIKE ?)")
            args += [f"%{busca}%"] * 3
        if somente_ativos:
            condicoes.append("ativo = 1")
        filtro = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""
        return _paginar(self._banco, "SELECT * FROM veterinarios", filtro, args, "nome", paginacao, _vet)

    def excluir(self, id: int) -> None:
        _excluir(self._banco, "veterinarios", id,
                 "Não é possível excluir: o veterinário possui consultas. Desative-o em vez de excluir.")
