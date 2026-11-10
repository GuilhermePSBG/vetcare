"""AgendamentoService (REQ 07) e consulta de horários livres."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime, time, timedelta
from typing import Callable

from vetcare.compartilhado.eventos import EventoDeDominio, PublicadorDeEventos
from vetcare.compartilhado.excecoes import DadosInvalidos, NaoEncontrado
from vetcare.compartilhado.tipos import (
    UsuarioAutenticado,
    inteiro_positivo,
    texto_opcional,
    validar_data_hora,
)

from ..dominio.consulta import Consulta, DisponibilidadeService
from ..dominio.portas import CadastroLeitura, RepositorioDeConsultas, UnidadeDeTrabalho


def _dia(d: date) -> tuple[datetime, datetime]:
    inicio = datetime.combine(d, time(0))
    return inicio, inicio + timedelta(days=1)


class AgendamentoService:
    def __init__(
        self,
        consultas: RepositorioDeConsultas,
        cadastro: CadastroLeitura,
        disponibilidade: DisponibilidadeService,
        eventos: PublicadorDeEventos,
        unidade_de_trabalho: UnidadeDeTrabalho = nullcontext,
        relogio: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._repo = consultas
        self._cadastro = cadastro
        self._disp = disponibilidade
        self._eventos = eventos
        self._uow = unidade_de_trabalho
        self._agora = relogio

    def agendar(self, dados: dict, autor: UsuarioAutenticado | None) -> Consulta:
        animal_id = inteiro_positivo(dados.get("animal_id"), "animal_id")
        veterinario_id = inteiro_positivo(dados.get("veterinario_id"), "veterinario_id")
        inicio = validar_data_hora(dados.get("inicio"), "inicio")
        motivo = texto_opcional(dados.get("motivo"), "motivo", 250)

        animal = self._cadastro.animal(animal_id)
        if animal is None:
            raise DadosInvalidos("Animal não encontrado.", {"campo": "animal_id"})
        tutor_id = dados.get("tutor_id")
        if tutor_id not in (None, "") and int(tutor_id) != animal.tutor_id:
            raise DadosInvalidos("O animal não pertence ao tutor informado.", {"campo": "tutor_id"})
        vet = self._cadastro.veterinario(veterinario_id)
        if vet is None:
            raise DadosInvalidos("Veterinário não encontrado.", {"campo": "veterinario_id"})
        if not vet.ativo:
            raise DadosInvalidos("Veterinário inativo não pode receber consultas.", {"campo": "veterinario_id"})

        consulta = Consulta(
            animal_id=animal.id,
            tutor_id=animal.tutor_id,
            veterinario_id=vet.id,
            inicio=inicio,
            duracao_min=self._disp.duracao_min,
            motivo=motivo,
            criado_por=autor.id if autor else None,
        )
        # Verificação + gravação na mesma transação; a restrição única no banco
        # é a última barreira contra dupla marcação simultânea (ADR-004).
        with self._uow():
            ini_dia, fim_dia = _dia(inicio.date())
            self._disp.validar(
                inicio,
                self._agora(),
                self._repo.do_veterinario(vet.id, ini_dia, fim_dia),
                self._repo.do_animal(animal.id, ini_dia, fim_dia),
            )
            consulta = self._repo.salvar(consulta)
            self._eventos.publicar(
                EventoDeDominio(
                    "ConsultaAgendada",
                    {
                        "consulta_id": consulta.id,
                        "animal_id": consulta.animal_id,
                        "tutor_id": consulta.tutor_id,
                        "veterinario_id": consulta.veterinario_id,
                        "inicio": consulta.inicio.isoformat(timespec="minutes"),
                    },
                    autor.id if autor else None,
                )
            )
        return consulta

    def obter(self, id: int) -> Consulta:
        consulta = self._repo.obter(id)
        if consulta is None:
            raise NaoEncontrado("Consulta não encontrada.")
        return consulta

    def do_dia(self, dia: date, veterinario_id: int | None = None) -> list[Consulta]:
        """Listagem simples do dia, usada para conferir o agendamento.
        As visões por semana/profissional (REQ 09) ficam para a etapa final."""
        return self._repo.no_periodo(*_dia(dia), veterinario_id)

    def horarios_livres(self, veterinario_id: int, dia: date) -> list[datetime]:
        if self._cadastro.veterinario(veterinario_id) is None:
            raise NaoEncontrado("Veterinário não encontrado.")
        return self._disp.horarios_livres(
            dia, self._agora(), self._repo.do_veterinario(veterinario_id, *_dia(dia))
        )
