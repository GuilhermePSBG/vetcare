"""REQ 07 - Agendar Consulta: regras de domínio (sem banco) e serviço com SQLite."""
from __future__ import annotations

import threading
from datetime import date, datetime, time, timedelta

import pytest

from conftest import CPF_A, CPF_B, em, proximo_dia_util
from vetcare.agenda.dominio.consulta import (
    Consulta, DisponibilidadeService, HorarioDeFuncionamento, StatusConsulta,
)
from vetcare.compartilhado.excecoes import Conflito, DadosInvalidos

SEGUNDA = date(2026, 11, 16)
AGORA = datetime(2026, 11, 13, 12, 0)
disp = DisponibilidadeService(HorarioDeFuncionamento(8, 18), 30)


def c(h, m=0, vet=1, animal=1, status=StatusConsulta.AGENDADA):
    return Consulta(animal, 1, vet, datetime.combine(SEGUNDA, time(h, m)), 30, status=status)


def quando(h, m=0, dia=SEGUNDA):
    return datetime.combine(dia, time(h, m))


# ----------------------------------------------------------------- domínio puro
def test_horario_valido_passa():
    disp.validar(quando(9), AGORA, [c(10)], [])


@pytest.mark.parametrize("inicio, motivo", [
    (datetime(2026, 11, 12, 9, 0), "passado"),
    (quando(7, 30), "antes de abrir"),
    (quando(17, 45), "fora da grade"),
    (quando(18), "depois de fechar"),
    (quando(9, 10), "fora da grade"),
    (quando(9, dia=date(2026, 11, 15)), "domingo"),
])
def test_horarios_invalidos(inicio, motivo):
    with pytest.raises(DadosInvalidos):
        disp.validar(inicio, AGORA, [], [])


def test_conflito_do_veterinario_e_do_animal():
    with pytest.raises(Conflito, match="veterinário"):
        disp.validar(quando(9), AGORA, [c(9)], [])
    with pytest.raises(Conflito, match="animal"):
        disp.validar(quando(9), AGORA, [], [c(9, vet=2)])


def test_consulta_cancelada_libera_horario():
    disp.validar(quando(9), AGORA, [c(9, status=StatusConsulta.CANCELADA)], [])


def test_ultima_vaga_do_dia_e_horarios_livres():
    disp.validar(quando(17, 30), AGORA, [], [])
    livres = disp.horarios_livres(SEGUNDA, AGORA, [c(8), c(9, 30)])
    assert len(livres) == 18  # 20 vagas de 30 min das 8h às 18h, menos 2 ocupadas
    assert quando(8) not in livres and quando(8, 30) in livres and quando(17, 30) in livres
    assert disp.horarios_livres(date(2026, 11, 15), AGORA, []) == []  # domingo


# ----------------------------------------------------------------- serviço + SQLite
@pytest.fixture
def base(ctx):
    t1 = ctx.tutores.cadastrar({"nome": "Ana", "cpf": CPF_A, "telefone": "71991112222"}, None)
    t2 = ctx.tutores.cadastrar({"nome": "Bruno", "cpf": CPF_B, "telefone": "71991113333"}, None)
    animal = {"especie": "CANINA", "sexo": "M", "data_nascimento": "2020-01-01"}
    a1 = ctx.animais.cadastrar({**animal, "tutor_id": t1.id, "nome": "Thor"}, None)
    a2 = ctx.animais.cadastrar({**animal, "tutor_id": t2.id, "nome": "Rex"}, None)
    vet = {"telefone": "71988887777", "email": "v@x.com"}
    v1 = ctx.veterinarios.cadastrar({**vet, "nome": "Dr. A", "crmv": "CRMV-BA 1111"}, None)
    v2 = ctx.veterinarios.cadastrar({**vet, "nome": "Dr. B", "crmv": "CRMV-BA 2222"}, None)
    return ctx, t1, a1, a2, v1, v2


def test_agenda_relacionando_animal_tutor_veterinario(base):
    ctx, t1, a1, _, v1, _ = base
    consulta = ctx.agenda.agendar(
        {"animal_id": a1.id, "tutor_id": t1.id, "veterinario_id": v1.id, "inicio": em(9), "motivo": "Vacina"}, None
    )
    assert consulta.id and consulta.tutor_id == t1.id and consulta.status == StatusConsulta.AGENDADA
    assert [x.id for x in ctx.agenda.do_dia(proximo_dia_util())] == [consulta.id]
    eventos = [e["evento"] for e in ctx.auditoria.listar()]
    assert "ConsultaAgendada" in eventos


def test_valida_referencias(base):
    ctx, t1, a1, a2, v1, _ = base
    with pytest.raises(DadosInvalidos, match="Animal"):
        ctx.agenda.agendar({"animal_id": 999, "veterinario_id": v1.id, "inicio": em(9)}, None)
    with pytest.raises(DadosInvalidos, match="tutor"):
        ctx.agenda.agendar({"animal_id": a2.id, "tutor_id": t1.id, "veterinario_id": v1.id, "inicio": em(9)}, None)
    ctx.veterinarios.alterar(v1.id, {"ativo": False}, None)
    with pytest.raises(DadosInvalidos, match="inativo"):
        ctx.agenda.agendar({"animal_id": a1.id, "veterinario_id": v1.id, "inicio": em(9)}, None)


def test_conflitos(base):
    ctx, _, a1, a2, v1, v2 = base
    ctx.agenda.agendar({"animal_id": a1.id, "veterinario_id": v1.id, "inicio": em(9)}, None)
    with pytest.raises(Conflito):  # mesmo veterinário, mesmo horário
        ctx.agenda.agendar({"animal_id": a2.id, "veterinario_id": v1.id, "inicio": em(9)}, None)
    with pytest.raises(Conflito):  # mesmo animal com outro veterinário
        ctx.agenda.agendar({"animal_id": a1.id, "veterinario_id": v2.id, "inicio": em(9)}, None)
    ctx.agenda.agendar({"animal_id": a2.id, "veterinario_id": v1.id, "inicio": em(9, 30)}, None)
    assert len(ctx.agenda.horarios_livres(v1.id, proximo_dia_util())) == 18


def test_restricao_unica_do_banco_impede_dupla_marcacao(base):
    """Mesmo que a verificação em código falhe, o índice único barra a gravação."""
    ctx, _, a1, a2, v1, _ = base
    ctx.agenda._disp.validar = lambda *a, **k: None  # simula falha/condição de corrida
    ctx.agenda.agendar({"animal_id": a1.id, "veterinario_id": v1.id, "inicio": em(10)}, None)
    with pytest.raises(Conflito):
        ctx.agenda.agendar({"animal_id": a2.id, "veterinario_id": v1.id, "inicio": em(10)}, None)


def test_agendamentos_simultaneos_geram_uma_unica_consulta(base):
    ctx, _, a1, a2, v1, _ = base
    resultados = []

    def tentar(animal_id):
        try:
            ctx.agenda.agendar({"animal_id": animal_id, "veterinario_id": v1.id, "inicio": em(11)}, None)
            resultados.append("ok")
        except Conflito:
            resultados.append("conflito")

    threads = [threading.Thread(target=tentar, args=(a,)) for a in (a1.id, a2.id, a1.id, a2.id)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert resultados.count("ok") == 1 and resultados.count("conflito") == 3
