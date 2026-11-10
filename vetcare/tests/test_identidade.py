"""REQ 01 (Manter Usuário) e REQ 02 (Autenticar Usuário) - testes do núcleo com dublês."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from vetcare.compartilhado.excecoes import (
    Conflito, ContaBloqueada, DadosInvalidos, NaoAutenticado, NaoEncontrado,
)
from vetcare.compartilhado.tipos import Pagina, Perfil, UsuarioAutenticado
from vetcare.identidade.adaptadores.hash_scrypt import HashScrypt
from vetcare.identidade.adaptadores.token_jwt import TokenJWT
from vetcare.identidade.aplicacao.servicos import AutenticacaoService, UsuarioService
from vetcare.identidade.dominio.politica_acesso import pode

S1 = "segredo-um-para-testes-com-32-bytes!!"
S2 = "segredo-dois-para-testes-com-32-bytes!"


class RepoFalso:
    def __init__(self):
        self.dados, self.seq = {}, 0

    def salvar(self, u):
        if u.id is None:
            self.seq += 1
            u.id = self.seq
        self.dados[u.id] = u
        return u

    def obter(self, id):
        return self.dados.get(id)

    def obter_por_email(self, email):
        return next((u for u in self.dados.values() if u.email == email), None)

    def listar(self, pag, busca):
        itens = list(self.dados.values())
        return Pagina(itens, len(itens), pag.pagina, pag.tamanho)

    def excluir(self, id):
        self.dados.pop(id)

    def contar_admins_ativos(self):
        return sum(1 for u in self.dados.values() if u.perfil == Perfil.ADMINISTRADOR and u.ativo)


class HashFalso:
    def gerar(self, s):
        return "h:" + s

    def verificar(self, s, h):
        return h == "h:" + s


class Eventos:
    def __init__(self):
        self.lista = []

    def publicar(self, e):
        self.lista.append(e)


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 11, 10, 9, 0)

    def __call__(self):
        return self.agora


@pytest.fixture
def cenario():
    repo, eventos, relogio = RepoFalso(), Eventos(), Relogio()
    usuarios = UsuarioService(repo, HashFalso(), eventos)
    auth = AutenticacaoService(repo, HashFalso(), TokenJWT(S1), eventos, 3, 15, relogio)
    admin = usuarios.criar({"nome": "Admin", "email": "a@x.com", "perfil": "ADMINISTRADOR", "senha": "Senha123"}, None)
    autor = UsuarioAutenticado(admin.id, admin.nome, admin.email, admin.perfil)
    return usuarios, auth, eventos, relogio, autor


# ----------------------------------------------------------------- REQ 01
def test_cria_usuario_com_senha_em_hash(cenario):
    usuarios, *_ , autor = cenario
    u = usuarios.criar({"nome": "Rita", "email": "RITA@x.com", "perfil": "recepcionista", "senha": "abc12345"}, autor)
    assert u.email == "rita@x.com" and u.perfil == Perfil.RECEPCIONISTA
    assert u.hash_senha != "abc12345"


@pytest.mark.parametrize("senha", ["curta1", "somenteletras", "12345678"])
def test_politica_de_senha(cenario, senha):
    usuarios, *_, autor = cenario
    with pytest.raises(DadosInvalidos):
        usuarios.criar({"nome": "X", "email": "x@x.com", "perfil": "VETERINARIO", "senha": senha}, autor)


def test_email_duplicado_e_perfil_invalido(cenario):
    usuarios, *_, autor = cenario
    with pytest.raises(Conflito):
        usuarios.criar({"nome": "Y", "email": "a@x.com", "perfil": "VETERINARIO", "senha": "Senha123"}, autor)
    with pytest.raises(DadosInvalidos):
        usuarios.criar({"nome": "Y", "email": "y@x.com", "perfil": "GERENTE", "senha": "Senha123"}, autor)


def test_altera_consulta_e_exclui(cenario):
    usuarios, *_, autor = cenario
    u = usuarios.criar({"nome": "Vet", "email": "v@x.com", "perfil": "VETERINARIO", "senha": "Senha123"}, autor)
    usuarios.alterar(u.id, {"nome": "Dra. Vet", "perfil": "RECEPCIONISTA"}, autor)
    assert usuarios.obter(u.id).nome == "Dra. Vet"
    usuarios.excluir(u.id, autor)
    with pytest.raises(NaoEncontrado):
        usuarios.obter(u.id)


def test_nao_exclui_a_si_mesmo_nem_o_ultimo_admin(cenario):
    usuarios, *_, autor = cenario
    with pytest.raises(DadosInvalidos):
        usuarios.excluir(autor.id, autor)
    outro = usuarios.criar({"nome": "R", "email": "r@x.com", "perfil": "RECEPCIONISTA", "senha": "Senha123"}, autor)
    autor_r = UsuarioAutenticado(outro.id, "R", "r@x.com", Perfil.RECEPCIONISTA)
    with pytest.raises(Conflito):
        usuarios.alterar(autor.id, {"perfil": "VETERINARIO"}, autor_r)


# ----------------------------------------------------------------- REQ 02
def test_login_valido_gera_token_que_autentica(cenario):
    _, auth, eventos, *_ = cenario
    token, u = auth.login("A@X.com", "Senha123")
    identidade = auth.autenticar_token(token)
    assert identidade.id == u.id and identidade.perfil == Perfil.ADMINISTRADOR
    assert eventos.lista[-1].nome == "LoginRealizado"


def test_login_invalido_usa_mensagem_generica(cenario):
    _, auth, *_ = cenario
    with pytest.raises(NaoAutenticado) as e1:
        auth.login("a@x.com", "errada")
    with pytest.raises(NaoAutenticado) as e2:
        auth.login("naoexiste@x.com", "qualquer")
    assert e1.value.mensagem == e2.value.mensagem


def test_bloqueio_apos_tentativas_falhas_e_liberacao(cenario):
    _, auth, _, relogio, _ = cenario
    for _ in range(2):
        with pytest.raises(NaoAutenticado):
            auth.login("a@x.com", "errada")
    with pytest.raises(ContaBloqueada):
        auth.login("a@x.com", "errada")
    with pytest.raises(ContaBloqueada):  # mesmo com a senha certa
        auth.login("a@x.com", "Senha123")
    relogio.agora += timedelta(minutes=16)
    assert auth.login("a@x.com", "Senha123")[0]


def test_usuario_desativado_perde_acesso(cenario):
    usuarios, auth, *_, autor = cenario
    u = usuarios.criar({"nome": "R", "email": "r@x.com", "perfil": "RECEPCIONISTA", "senha": "Senha123"}, autor)
    token, _ = auth.login("r@x.com", "Senha123")
    usuarios.alterar(u.id, {"ativo": False}, autor)
    with pytest.raises(NaoAutenticado):
        auth.autenticar_token(token)
    with pytest.raises(NaoAutenticado):
        auth.login("r@x.com", "Senha123")


def test_token_adulterado_ou_expirado():
    tokens = TokenJWT(S1, horas_validade=0)
    with pytest.raises(NaoAutenticado):
        tokens.validar(tokens.emitir(1, "ADMINISTRADOR"))  # expira imediatamente
    with pytest.raises(NaoAutenticado):
        TokenJWT(S2).validar(TokenJWT(S1).emitir(1, "ADMINISTRADOR"))


def test_hash_scrypt():
    h = HashScrypt(log2_n=12)
    assert HashScrypt().n == 2**17  # padrão = mínimo OWASP
    hash1, hash2 = h.gerar("Senha123"), h.gerar("Senha123")
    assert hash1 != hash2  # sal aleatório
    assert h.verificar("Senha123", hash1) and not h.verificar("senha123", hash1)
    assert not h.verificar("x", "lixo")
    assert not h.verificar("x", "scrypt$1073741824$8$1$AAAA$AAAA")  # parâmetro abusivo


def test_rbac():
    assert pode(Perfil.ADMINISTRADOR, "usuarios:gerenciar")
    assert not pode(Perfil.RECEPCIONISTA, "usuarios:gerenciar")
    assert pode(Perfil.RECEPCIONISTA, "consultas:agendar")
    assert not pode(Perfil.VETERINARIO, "tutores:escrever")
    assert pode(Perfil.VETERINARIO, "tutores:ler")
    assert not pode(Perfil.ADMINISTRADOR, "acao:inexistente")  # nega por padrão
