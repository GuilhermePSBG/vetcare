"""REQ 04 (Tutor), REQ 05 (Animal) e REQ 06 (Veterinário)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from conftest import CPF_A, CPF_B, em
from vetcare.cadastro.dominio.entidades import Animal, Tutor, validar_crmv
from vetcare.compartilhado.excecoes import Conflito, DadosInvalidos, NaoEncontrado
from vetcare.compartilhado.tipos import Paginacao, validar_cpf

TUTOR = {"nome": "Ana Souza", "cpf": "529.982.247-25", "telefone": "(71) 99111-2222", "email": "ana@x.com"}


def animal(tutor_id, **extra):
    return {"tutor_id": tutor_id, "nome": "Thor", "especie": "canina", "raca": "Labrador",
            "sexo": "M", "data_nascimento": "2020-03-01", **extra}


# ----------------------------------------------------------------- regras puras
@pytest.mark.parametrize("cpf", ["52998224725", "529.982.247-25"])
def test_cpf_valido(cpf):
    assert validar_cpf(cpf) == "52998224725"


@pytest.mark.parametrize("cpf", ["52998224724", "11111111111", "123", ""])
def test_cpf_invalido(cpf):
    with pytest.raises(DadosInvalidos):
        validar_cpf(cpf)


def test_tutor_normaliza_campos():
    t = Tutor.de_dados(TUTOR)
    assert t.cpf == "52998224725" and t.telefone == "71991112222"


def test_animal_exige_campos_e_data_valida():
    with pytest.raises(DadosInvalidos):
        Animal.de_dados(animal(1, especie="dragao"))
    with pytest.raises(DadosInvalidos):
        Animal.de_dados(animal(1, data_nascimento=(date.today() + timedelta(days=1)).isoformat()))
    with pytest.raises(DadosInvalidos):
        Animal.de_dados(animal(None))


@pytest.mark.parametrize("entrada", ["CRMV-BA 12345", "crmv ba 12345", "CRMV-BA12345"])
def test_crmv_normalizado(entrada):
    assert validar_crmv(entrada) == "CRMV-BA 12345"


# ----------------------------------------------------------------- serviços + SQLite
def test_crud_tutor(ctx):
    t = ctx.tutores.cadastrar(TUTOR, None)
    assert ctx.tutores.obter(t.id).nome == "Ana Souza"
    ctx.tutores.alterar(t.id, {"telefone": "7133334444"}, None)
    assert ctx.tutores.obter(t.id).telefone == "7133334444"
    assert ctx.tutores.listar(Paginacao(), "ana").total == 1
    ctx.tutores.excluir(t.id, None)
    with pytest.raises(NaoEncontrado):
        ctx.tutores.obter(t.id)


def test_cpf_duplicado(ctx):
    ctx.tutores.cadastrar(TUTOR, None)
    with pytest.raises(Conflito):
        ctx.tutores.cadastrar({**TUTOR, "nome": "Outra"}, None)
    outro = ctx.tutores.cadastrar({**TUTOR, "cpf": CPF_B}, None)
    with pytest.raises(Conflito):
        ctx.tutores.alterar(outro.id, {"cpf": CPF_A}, None)


def test_animal_associado_a_tutor_existente(ctx):
    with pytest.raises(DadosInvalidos):
        ctx.animais.cadastrar(animal(999), None)
    t = ctx.tutores.cadastrar(TUTOR, None)
    a = ctx.animais.cadastrar(animal(t.id), None)
    assert ctx.animais.listar(Paginacao(), None, t.id).total == 1
    ctx.animais.alterar(a.id, {"nome": "Thor II"}, None)
    assert ctx.animais.obter(a.id).nome == "Thor II"


def test_nao_exclui_tutor_com_animais(ctx):
    t = ctx.tutores.cadastrar(TUTOR, None)
    a = ctx.animais.cadastrar(animal(t.id), None)
    with pytest.raises(Conflito):
        ctx.tutores.excluir(t.id, None)
    ctx.animais.excluir(a.id, None)
    ctx.tutores.excluir(t.id, None)


def test_veterinario_crmv_unico_e_exclusao_com_consulta(ctx):
    dados = {"nome": "Dr. Paulo", "crmv": "CRMV-BA 1234", "telefone": "71988887777", "email": "p@x.com"}
    v = ctx.veterinarios.cadastrar(dados, None)
    with pytest.raises(Conflito):
        ctx.veterinarios.cadastrar({**dados, "crmv": "crmv-ba 1234"}, None)
    t = ctx.tutores.cadastrar(TUTOR, None)
    a = ctx.animais.cadastrar(animal(t.id), None)
    ctx.agenda.agendar({"animal_id": a.id, "veterinario_id": v.id, "inicio": em(9)}, None)
    with pytest.raises(Conflito):  # chave estrangeira protege o histórico
        ctx.veterinarios.excluir(v.id, None)
    with pytest.raises(Conflito):
        ctx.animais.excluir(a.id, None)
    ctx.veterinarios.alterar(v.id, {"ativo": False}, None)
    assert ctx.veterinarios.listar(Paginacao(), None, somente_ativos=True).total == 0
