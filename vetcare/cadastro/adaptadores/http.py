"""Adaptadores de entrada HTTP do módulo Cadastro."""
from __future__ import annotations

from vetcare.infraestrutura.http import Requisicao, Resposta, Rota, pagina_para_json

from ..aplicacao.servicos import AnimalService, TutorService, VeterinarioService
from ..dominio.entidades import Animal, Tutor, Veterinario


def tutor_para_json(t: Tutor) -> dict:
    return {
        "id": t.id, "nome": t.nome, "cpf": t.cpf, "telefone": t.telefone,
        "email": t.email, "endereco": t.endereco, "criado_em": t.criado_em.isoformat(),
    }


def animal_para_json(a: Animal, tutor: Tutor | None = None) -> dict:
    return {
        "id": a.id, "tutor_id": a.tutor_id, "tutor_nome": tutor.nome if tutor else None,
        "nome": a.nome, "especie": a.especie.value, "raca": a.raca, "sexo": a.sexo.value,
        "data_nascimento": a.data_nascimento.isoformat(), "criado_em": a.criado_em.isoformat(),
    }


def vet_para_json(v: Veterinario) -> dict:
    return {
        "id": v.id, "nome": v.nome, "crmv": v.crmv, "telefone": v.telefone, "email": v.email,
        "especialidade": v.especialidade, "ativo": v.ativo, "criado_em": v.criado_em.isoformat(),
    }


def criar_rotas(
    tutores: TutorService, animais: AnimalService, veterinarios: VeterinarioService
) -> list[Rota]:
    # ------------------------------------------------------------ tutores
    def listar_tutores(req: Requisicao) -> Resposta:
        pag = tutores.listar(req.paginacao(), req.consulta.get("busca"))
        return Resposta(200, pagina_para_json(pag, tutor_para_json))

    def obter_tutor(req: Requisicao) -> Resposta:
        return Resposta(200, tutor_para_json(tutores.obter(req.id())))

    def criar_tutor(req: Requisicao) -> Resposta:
        return Resposta(201, tutor_para_json(tutores.cadastrar(req.corpo, req.usuario)))

    def alterar_tutor(req: Requisicao) -> Resposta:
        return Resposta(200, tutor_para_json(tutores.alterar(req.id(), req.corpo, req.usuario)))

    def excluir_tutor(req: Requisicao) -> Resposta:
        tutores.excluir(req.id(), req.usuario)
        return Resposta(204)

    # ------------------------------------------------------------ animais
    def _com_tutor(a: Animal, cache: dict[int, Tutor]) -> dict:
        if a.tutor_id not in cache:
            cache[a.tutor_id] = tutores.obter(a.tutor_id)
        return animal_para_json(a, cache[a.tutor_id])

    def listar_animais(req: Requisicao) -> Resposta:
        tutor_id = req.consulta.get("tutor_id")
        pag = animais.listar(
            req.paginacao(), req.consulta.get("busca"), int(tutor_id) if tutor_id else None
        )
        cache: dict[int, Tutor] = {}
        return Resposta(200, pagina_para_json(pag, lambda a: _com_tutor(a, cache)))

    def obter_animal(req: Requisicao) -> Resposta:
        return Resposta(200, _com_tutor(animais.obter(req.id()), {}))

    def criar_animal(req: Requisicao) -> Resposta:
        return Resposta(201, _com_tutor(animais.cadastrar(req.corpo, req.usuario), {}))

    def alterar_animal(req: Requisicao) -> Resposta:
        return Resposta(200, _com_tutor(animais.alterar(req.id(), req.corpo, req.usuario), {}))

    def excluir_animal(req: Requisicao) -> Resposta:
        animais.excluir(req.id(), req.usuario)
        return Resposta(204)

    # ------------------------------------------------------------ veterinários
    def listar_vets(req: Requisicao) -> Resposta:
        pag = veterinarios.listar(
            req.paginacao(), req.consulta.get("busca"), req.consulta.get("ativos") == "1"
        )
        return Resposta(200, pagina_para_json(pag, vet_para_json))

    def obter_vet(req: Requisicao) -> Resposta:
        return Resposta(200, vet_para_json(veterinarios.obter(req.id())))

    def criar_vet(req: Requisicao) -> Resposta:
        return Resposta(201, vet_para_json(veterinarios.cadastrar(req.corpo, req.usuario)))

    def alterar_vet(req: Requisicao) -> Resposta:
        return Resposta(200, vet_para_json(veterinarios.alterar(req.id(), req.corpo, req.usuario)))

    def excluir_vet(req: Requisicao) -> Resposta:
        veterinarios.excluir(req.id(), req.usuario)
        return Resposta(204)

    return [
        Rota("GET", "/api/tutores", listar_tutores, "tutores:ler"),
        Rota("POST", "/api/tutores", criar_tutor, "tutores:escrever"),
        Rota("GET", "/api/tutores/{id:int}", obter_tutor, "tutores:ler"),
        Rota("PUT", "/api/tutores/{id:int}", alterar_tutor, "tutores:escrever"),
        Rota("DELETE", "/api/tutores/{id:int}", excluir_tutor, "tutores:escrever"),
        Rota("GET", "/api/animais", listar_animais, "animais:ler"),
        Rota("POST", "/api/animais", criar_animal, "animais:escrever"),
        Rota("GET", "/api/animais/{id:int}", obter_animal, "animais:ler"),
        Rota("PUT", "/api/animais/{id:int}", alterar_animal, "animais:escrever"),
        Rota("DELETE", "/api/animais/{id:int}", excluir_animal, "animais:escrever"),
        Rota("GET", "/api/veterinarios", listar_vets, "veterinarios:ler"),
        Rota("POST", "/api/veterinarios", criar_vet, "veterinarios:escrever"),
        Rota("GET", "/api/veterinarios/{id:int}", obter_vet, "veterinarios:ler"),
        Rota("PUT", "/api/veterinarios/{id:int}", alterar_vet, "veterinarios:escrever"),
        Rota("DELETE", "/api/veterinarios/{id:int}", excluir_vet, "veterinarios:escrever"),
    ]
