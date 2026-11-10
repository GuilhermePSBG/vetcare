"""Popula o banco com dados de demonstração:  python -m vetcare.dados_exemplo

Cria usuários dos três perfis, veterinários, tutores, animais e algumas
consultas no próximo dia útil. Pode ser executado mais de uma vez (ignora
o que já existe).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from vetcare.app import montar
from vetcare.compartilhado.excecoes import ErroDeDominio
from vetcare.compartilhado.tipos import Paginacao


def cpf_valido(base9: str) -> str:
    digitos = [int(d) for d in base9]
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(digitos))
        digitos.append((soma * 10) % 11 % 10)
    return "".join(map(str, digitos))


def proximo_dia_util(hoje: date) -> date:
    dia = hoje + timedelta(days=1)
    while dia.weekday() == 6:  # domingo
        dia += timedelta(days=1)
    return dia


def _tentar(funcao, *args):
    try:
        return funcao(*args)
    except ErroDeDominio as e:
        print(f"  - ignorado: {e.mensagem}")
        return None


def main() -> None:
    ctx = montar()
    print("Criando usuários...")
    for nome, email, perfil in [
        ("Rita Recepção", "recepcao@vetcare.local", "RECEPCIONISTA"),
        ("Dr. Paulo Vet", "vet@vetcare.local", "VETERINARIO"),
    ]:
        _tentar(ctx.usuarios.criar, {"nome": nome, "email": email, "perfil": perfil, "senha": "Senha@123"}, None)

    print("Criando veterinários...")
    vets_dados = [
        {"nome": "Dr. Paulo Andrade", "crmv": "CRMV-BA 10234", "telefone": "71988887777",
         "email": "paulo@vetcare.local", "especialidade": "Clínica geral"},
        {"nome": "Dra. Marina Lopes", "crmv": "CRMV-BA 11876", "telefone": "71977776666",
         "email": "marina@vetcare.local", "especialidade": "Dermatologia"},
        {"nome": "Dr. Caio Ribeiro", "crmv": "CRMV-BA 09345", "telefone": "71966665555",
         "email": "caio@vetcare.local", "especialidade": "Ortopedia"},
    ]
    for dados in vets_dados:
        _tentar(ctx.veterinarios.cadastrar, dados, None)

    print("Criando tutores e animais...")
    tutores = [
        ("Ana Souza", "123456789", "71991112222", [("Thor", "CANINA", "Labrador", "M", "2019-04-12"),
                                                    ("Mia", "FELINA", "SRD", "F", "2021-08-03")]),
        ("Bruno Lima", "987654321", "71992223333", [("Pipoca", "CANINA", "Shih-tzu", "F", "2020-01-20")]),
        ("Carla Menezes", "456789123", "71993334444", [("Frajola", "FELINA", "Siamês", "M", "2018-11-30"),
                                                        ("Kiwi", "AVE", "Calopsita", "M", "2022-06-15")]),
        ("Diego Santos", "321654987", "71994445555", [("Rex", "CANINA", "Pastor Alemão", "M", "2017-09-09")]),
    ]
    for nome, base, tel, animais in tutores:
        cpf = cpf_valido(base)
        tutor = ctx.tutores._repo.obter_por_cpf(cpf) or _tentar(
            ctx.tutores.cadastrar,
            {"nome": nome, "cpf": cpf, "telefone": tel, "email": f"{nome.split()[0].lower()}@exemplo.com"},
            None,
        )
        existentes = {a.nome for a in ctx.animais.listar(Paginacao(1, 100), None, tutor.id).itens}
        for a_nome, especie, raca, sexo, nasc in animais:
            if a_nome not in existentes:
                _tentar(ctx.animais.cadastrar, {"tutor_id": tutor.id, "nome": a_nome, "especie": especie,
                                                "raca": raca, "sexo": sexo, "data_nascimento": nasc}, None)

    print("Agendando consultas no próximo dia útil...")
    dia = proximo_dia_util(date.today())
    vets = ctx.veterinarios.listar(Paginacao(1, 10)).itens
    animais = ctx.animais.listar(Paginacao(1, 10)).itens
    horarios = [time(9, 0), time(9, 30), time(10, 30), time(14, 0), time(15, 30)]
    for i, (animal, hora) in enumerate(zip(animais, horarios)):
        _tentar(ctx.agenda.agendar, {
            "animal_id": animal.id, "veterinario_id": vets[i % len(vets)].id,
            "inicio": datetime.combine(dia, hora).isoformat(), "motivo": "Consulta de rotina",
        }, None)
    print("\nPronto! Usuários de demonstração (senha Senha@123): recepcao@vetcare.local, vet@vetcare.local")
    print(f"Administrador: {ctx.config.admin_email} / {ctx.config.admin_senha}")


if __name__ == "__main__":
    main()
