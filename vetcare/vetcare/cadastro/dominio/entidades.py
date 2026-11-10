"""Entidades do módulo Cadastro: Tutor (REQ 04), Animal (REQ 05) e Veterinário (REQ 06)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from vetcare.compartilhado.excecoes import DadosInvalidos
from vetcare.compartilhado.tipos import (
    texto_obrigatorio,
    texto_opcional,
    validar_cpf,
    validar_data,
    validar_email,
    validar_telefone,
)


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


class Especie(str, Enum):
    CANINA = "CANINA"
    FELINA = "FELINA"
    AVE = "AVE"
    ROEDOR = "ROEDOR"
    REPTIL = "REPTIL"
    OUTRA = "OUTRA"


class Sexo(str, Enum):
    MACHO = "M"
    FEMEA = "F"


def _enum(tipo, valor: object, campo: str):
    try:
        return tipo(str(valor).upper())
    except ValueError:
        opcoes = ", ".join(e.value for e in tipo)
        raise DadosInvalidos(f"Valor inválido para '{campo}'. Use: {opcoes}.", {"campo": campo})


@dataclass
class Tutor:
    nome: str
    cpf: str
    telefone: str
    email: str | None = None
    endereco: str | None = None
    id: int | None = None
    criado_em: datetime = field(default_factory=_agora)

    @classmethod
    def de_dados(cls, dados: dict) -> "Tutor":
        tutor = cls(nome="", cpf="", telefone="")
        tutor.atualizar(dados, completo=True)
        return tutor

    def atualizar(self, dados: dict, completo: bool = False) -> None:
        if completo or "nome" in dados:
            self.nome = texto_obrigatorio(dados.get("nome"), "nome")
        if completo or "cpf" in dados:
            self.cpf = validar_cpf(dados.get("cpf"))
        if completo or "telefone" in dados:
            self.telefone = validar_telefone(dados.get("telefone"))
        if completo or "email" in dados:
            email = dados.get("email")
            self.email = validar_email(email) if email else None
        if completo or "endereco" in dados:
            self.endereco = texto_opcional(dados.get("endereco"), "endereco", 250)


@dataclass
class Animal:
    tutor_id: int
    nome: str
    especie: Especie
    sexo: Sexo
    data_nascimento: date
    raca: str | None = None
    id: int | None = None
    criado_em: datetime = field(default_factory=_agora)

    @classmethod
    def de_dados(cls, dados: dict) -> "Animal":
        animal = cls(0, "", Especie.OUTRA, Sexo.MACHO, date.today())
        animal.atualizar(dados, completo=True)
        return animal

    def atualizar(self, dados: dict, completo: bool = False) -> None:
        if completo or "tutor_id" in dados:
            try:
                self.tutor_id = int(dados.get("tutor_id"))
            except (TypeError, ValueError):
                raise DadosInvalidos("O animal deve estar associado a um tutor.", {"campo": "tutor_id"})
        if completo or "nome" in dados:
            self.nome = texto_obrigatorio(dados.get("nome"), "nome", 80)
        if completo or "especie" in dados:
            self.especie = _enum(Especie, dados.get("especie"), "especie")
        if completo or "raca" in dados:
            self.raca = texto_opcional(dados.get("raca"), "raca", 80)
        if completo or "sexo" in dados:
            self.sexo = _enum(Sexo, dados.get("sexo"), "sexo")
        if completo or "data_nascimento" in dados:
            nascimento = validar_data(dados.get("data_nascimento"), "data_nascimento")
            if nascimento > date.today():
                raise DadosInvalidos(
                    "A data de nascimento não pode estar no futuro.", {"campo": "data_nascimento"}
                )
            self.data_nascimento = nascimento


_CRMV_RE = re.compile(r"^CRMV[- ]?([A-Z]{2})[- ]?(\d{3,6})$")


def validar_crmv(valor: object) -> str:
    """Aceita 'CRMV-BA 12345', 'crmv ba 12345' etc. e normaliza para 'CRMV-BA 12345'."""
    m = _CRMV_RE.match(re.sub(r"\s+", " ", str(valor or "").strip().upper()))
    if not m:
        raise DadosInvalidos("CRMV inválido. Formato esperado: CRMV-UF 12345.", {"campo": "crmv"})
    return f"CRMV-{m.group(1)} {m.group(2)}"


@dataclass
class Veterinario:
    nome: str
    crmv: str
    telefone: str
    email: str
    especialidade: str | None = None
    ativo: bool = True
    id: int | None = None
    criado_em: datetime = field(default_factory=_agora)

    @classmethod
    def de_dados(cls, dados: dict) -> "Veterinario":
        vet = cls(nome="", crmv="", telefone="", email="")
        vet.atualizar(dados, completo=True)
        return vet

    def atualizar(self, dados: dict, completo: bool = False) -> None:
        if completo or "nome" in dados:
            self.nome = texto_obrigatorio(dados.get("nome"), "nome")
        if completo or "crmv" in dados:
            self.crmv = validar_crmv(dados.get("crmv"))
        if completo or "telefone" in dados:
            self.telefone = validar_telefone(dados.get("telefone"))
        if completo or "email" in dados:
            self.email = validar_email(dados.get("email"))
        if completo or "especialidade" in dados:
            self.especialidade = texto_opcional(dados.get("especialidade"), "especialidade", 80)
        if "ativo" in dados:
            self.ativo = bool(dados["ativo"])
