"""AgendaController: agendar consulta, listar consultas do dia e horários livres."""
from __future__ import annotations

from datetime import date

from vetcare.compartilhado.tipos import validar_data
from vetcare.infraestrutura.http import Requisicao, Resposta, Rota

from ..aplicacao.servicos import AgendamentoService
from ..dominio.consulta import Consulta
from ..dominio.portas import CadastroLeitura


def criar_rotas(agenda: AgendamentoService, cadastro: CadastroLeitura) -> list[Rota]:
    def para_json(c: Consulta) -> dict:
        animal = cadastro.animal(c.animal_id)
        vet = cadastro.veterinario(c.veterinario_id)
        return {
            "id": c.id,
            "animal_id": c.animal_id,
            "animal_nome": animal.nome if animal else None,
            "tutor_id": c.tutor_id,
            "tutor_nome": animal.tutor_nome if animal else None,
            "veterinario_id": c.veterinario_id,
            "veterinario_nome": vet.nome if vet else None,
            "inicio": c.inicio.isoformat(timespec="minutes"),
            "fim": c.fim.isoformat(timespec="minutes"),
            "duracao_min": c.duracao_min,
            "motivo": c.motivo,
            "status": c.status.value,
        }

    def _data(req: Requisicao) -> date:
        valor = req.consulta.get("data")
        return validar_data(valor, "data") if valor else date.today()

    def agendar(req: Requisicao) -> Resposta:
        return Resposta(201, para_json(agenda.agendar(req.corpo, req.usuario)))

    def obter(req: Requisicao) -> Resposta:
        return Resposta(200, para_json(agenda.obter(req.id())))

    def do_dia(req: Requisicao) -> Resposta:
        vet = req.consulta.get("veterinario_id")
        consultas = agenda.do_dia(_data(req), int(vet) if vet else None)
        return Resposta(200, {"itens": [para_json(c) for c in consultas]})

    def livres(req: Requisicao) -> Resposta:
        vet_id = int(req.consulta.get("veterinario_id") or 0)
        horarios = agenda.horarios_livres(vet_id, _data(req))
        return Resposta(200, {"horarios": [h.isoformat(timespec="minutes") for h in horarios]})

    return [
        Rota("POST", "/api/consultas", agendar, "consultas:agendar"),
        Rota("GET", "/api/consultas", do_dia, "consultas:ler"),
        Rota("GET", "/api/consultas/{id:int}", obter, "consultas:ler"),
        Rota("GET", "/api/agenda/horarios-livres", livres, "consultas:ler"),
    ]
