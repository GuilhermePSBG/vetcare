"""Testes ponta a ponta pela fachada REST: autenticação, RBAC e fluxo completo."""
from __future__ import annotations

from conftest import CPF_A, ClienteASGI, em


def _criar_usuario(cliente, perfil, email):
    r = cliente.post("/api/usuarios", {"nome": perfil.title(), "email": email, "perfil": perfil, "senha": "Senha123"})
    assert r.status == 201, r.json


def test_saude_e_portal_web(app):
    c = ClienteASGI(app)
    assert c.get("/api/saude", token=None).json == {"status": "ok"}
    pagina = c.get("/", token=None)
    assert pagina.status == 200 and b"VetCare" in pagina.corpo
    assert pagina.headers["x-frame-options"] == "DENY"


def test_rotas_exigem_token(app):
    c = ClienteASGI(app)
    r = c.get("/api/tutores", token=None)
    assert r.status == 401 and r.json["erro"]["codigo"] == "NAO_AUTENTICADO"
    assert c.get("/api/tutores", token="invalido").status == 401
    assert c.get("/api/inexistente", token=None).status == 404


def test_login_errado_retorna_401_padronizado(app):
    r = ClienteASGI(app).post("/api/auth/login", {"email": "admin@teste.com", "senha": "x"}, token=None)
    assert r.status == 401
    assert set(r.json["erro"]) == {"codigo", "mensagem", "detalhes"}


def test_rbac_por_perfil(app, cliente):
    _criar_usuario(cliente, "VETERINARIO", "vet@teste.com")
    _criar_usuario(cliente, "RECEPCIONISTA", "rec@teste.com")
    vet, rec = ClienteASGI(app), ClienteASGI(app)
    vet.login("vet@teste.com", "Senha123")
    rec.login("rec@teste.com", "Senha123")

    tutor = {"nome": "Ana", "cpf": CPF_A, "telefone": "71991112222"}
    assert vet.post("/api/tutores", tutor).status == 403          # veterinário só lê
    assert vet.get("/api/tutores").status == 200
    assert rec.post("/api/tutores", tutor).status == 201          # recepção cadastra
    assert rec.get("/api/usuarios").status == 403                 # só admin gerencia usuários
    assert rec.post("/api/veterinarios", {}).status == 403
    assert rec.get("/api/auditoria").status == 403
    eu = vet.get("/api/auth/eu").json
    assert eu["usuario"]["perfil"] == "VETERINARIO" and "consultas:agendar" not in eu["permissoes"]


def test_fluxo_completo_ate_agendamento(cliente):
    t = cliente.post("/api/tutores", {"nome": "Ana Souza", "cpf": CPF_A, "telefone": "71991112222"})
    assert t.status == 201
    a = cliente.post("/api/animais", {"tutor_id": t.json["id"], "nome": "Thor", "especie": "CANINA",
                                      "sexo": "M", "data_nascimento": "2020-01-01"})
    assert a.status == 201 and a.json["tutor_nome"] == "Ana Souza"
    v = cliente.post("/api/veterinarios", {"nome": "Dr. Paulo", "crmv": "CRMV-BA 1234",
                                           "telefone": "71988887777", "email": "p@x.com"})
    assert v.status == 201

    dia = em(9)[:10]
    livres = cliente.get(f"/api/agenda/horarios-livres?veterinario_id={v.json['id']}&data={dia}").json["horarios"]
    assert em(9) in livres

    corpo = {"animal_id": a.json["id"], "veterinario_id": v.json["id"], "inicio": em(9), "motivo": "Rotina"}
    r = cliente.post("/api/consultas", corpo)
    assert r.status == 201
    assert r.json["animal_nome"] == "Thor" and r.json["veterinario_nome"] == "Dr. Paulo"
    assert r.json["fim"] == em(9, 30)

    duplicada = cliente.post("/api/consultas", corpo)
    assert duplicada.status == 409 and duplicada.json["erro"]["codigo"] == "CONFLITO"

    lista = cliente.get(f"/api/consultas?data={dia}").json["itens"]
    assert [x["id"] for x in lista] == [r.json["id"]]

    eventos = {e["evento"] for e in cliente.get("/api/auditoria").json["itens"]}
    assert {"LoginRealizado", "TutorCadastrado", "AnimalCadastrado", "ConsultaAgendada"} <= eventos


def test_validacao_paginacao_e_json_invalido(cliente):
    r = cliente.post("/api/tutores", {"nome": "", "cpf": "1", "telefone": "1"})
    assert r.status == 422 and r.json["erro"]["detalhes"]["campo"] == "nome"
    assert cliente.get("/api/tutores?tamanho=1000").status == 422
    bruto = cliente.requisicao("POST", "/api/tutores", None)
    assert bruto.status == 422  # corpo vazio -> campos obrigatórios
    for i in range(3):
        cpf = ["52998224725", "11144477735", "39053344705"][i]
        cliente.post("/api/tutores", {"nome": f"Tutor {i}", "cpf": cpf, "telefone": "71991112222"})
    pag = cliente.get("/api/tutores?pagina=2&tamanho=2").json
    assert pag["total"] == 3 and len(pag["itens"]) == 1
