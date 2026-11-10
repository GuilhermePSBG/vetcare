"""Entidade Consulta e DisponibilidadeService (regras puras, sem banco nem web)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum

from vetcare.compartilhado.excecoes import Conflito, DadosInvalidos


class StatusConsulta(str, Enum):
    AGENDADA = "AGENDADA"
    CANCELADA = "CANCELADA"
    REALIZADA = "REALIZADA"


@dataclass
class Consulta:
    animal_id: int
    tutor_id: int
    veterinario_id: int
    inicio: datetime
    duracao_min: int
    motivo: str | None = None
    status: StatusConsulta = StatusConsulta.AGENDADA
    criado_por: int | None = None
    id: int | None = None
    criado_em: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))

    @property
    def fim(self) -> datetime:
        return self.inicio + timedelta(minutes=self.duracao_min)

    @property
    def ativa(self) -> bool:
        return self.status == StatusConsulta.AGENDADA

    def sobrepoe(self, inicio: datetime, fim: datetime) -> bool:
        return self.inicio < fim and inicio < self.fim


@dataclass(frozen=True)
class HorarioDeFuncionamento:
    abertura: int = 8          # hora
    fechamento: int = 18       # hora
    dias_uteis: frozenset[int] = frozenset({0, 1, 2, 3, 4, 5})  # seg..sáb (weekday())

    def contem(self, inicio: datetime, fim: datetime) -> bool:
        if inicio.weekday() not in self.dias_uteis:
            return False
        meia_noite = datetime.combine(inicio.date(), time(0))
        abertura = meia_noite + timedelta(hours=self.abertura)
        fechamento = meia_noite + timedelta(hours=self.fechamento)
        return abertura <= inicio and fim <= fechamento


class DisponibilidadeService:
    """Regras de agendamento (REQ 07):
    - não agendar no passado nem fora do horário de funcionamento;
    - horário alinhado à grade de consultas;
    - veterinário não pode ter duas consultas sobrepostas;
    - o mesmo animal não pode estar em duas consultas sobrepostas.
    """

    def __init__(self, horario: HorarioDeFuncionamento, duracao_min: int) -> None:
        self.horario = horario
        self.duracao_min = duracao_min

    def validar(
        self,
        inicio: datetime,
        agora: datetime,
        consultas_do_veterinario: list[Consulta],
        consultas_do_animal: list[Consulta],
    ) -> None:
        fim = inicio + timedelta(minutes=self.duracao_min)
        if inicio <= agora:
            raise DadosInvalidos("Não é possível agendar consultas no passado.", {"campo": "inicio"})
        if (inicio.hour * 60 + inicio.minute - self.horario.abertura * 60) % self.duracao_min != 0:
            raise DadosInvalidos(
                f"O horário deve seguir a grade de {self.duracao_min} minutos "
                f"a partir das {self.horario.abertura:02d}:00.",
                {"campo": "inicio"},
            )
        if not self.horario.contem(inicio, fim):
            raise DadosInvalidos(
                f"Fora do horário de funcionamento (seg a sáb, {self.horario.abertura:02d}:00 às "
                f"{self.horario.fechamento:02d}:00).",
                {"campo": "inicio"},
            )
        if any(c.ativa and c.sobrepoe(inicio, fim) for c in consultas_do_veterinario):
            raise Conflito("O veterinário já possui consulta neste horário.", {"campo": "inicio"})
        if any(c.ativa and c.sobrepoe(inicio, fim) for c in consultas_do_animal):
            raise Conflito("Este animal já possui consulta neste horário.", {"campo": "inicio"})

    def horarios_livres(
        self, dia: date, agora: datetime, consultas_do_veterinario: list[Consulta]
    ) -> list[datetime]:
        livres: list[datetime] = []
        if dia.weekday() not in self.horario.dias_uteis:
            return livres
        atual = datetime.combine(dia, time(self.horario.abertura))
        limite = datetime.combine(dia, time(0)) + timedelta(hours=self.horario.fechamento)
        passo = timedelta(minutes=self.duracao_min)
        while atual + passo <= limite:
            ocupado = any(c.ativa and c.sobrepoe(atual, atual + passo) for c in consultas_do_veterinario)
            if atual > agora and not ocupado:
                livres.append(atual)
            atual += passo
        return livres
