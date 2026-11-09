"""Adaptadores de entrada HTTP: AuthController e UsuarioController."""
from __future__ import annotations

from vetcare.compartilhado.excecoes import NaoAutenticado
from vetcare.infraestrutura.http import Requisicao, Resposta, Rota, pagina_para_json

from ..aplicacao.servicos import AutenticacaoService, UsuarioService
from ..dominio.politica_acesso import acoes_do_perfil
from ..dominio.usuario import Usuario


def usuario_para_json(u: Usuario) -> dict:
    return {
        "id": u.id,
        "nome": u.nome,
        "email": u.email,
        "perfil": u.perfil.value,
        "ativo": u.ativo,
        "criado_em": u.criado_em.isoformat(),
    }


def criar_rotas(usuarios: UsuarioService, autenticacao: AutenticacaoService) -> list[Rota]:
    def login(req: Requisicao) -> Resposta:
        token, usuario = autenticacao.login(req.corpo.get("email"), req.corpo.get("senha"), req.ip)
        return Resposta(
            200,
            {
                "token": token,
                "usuario": usuario_para_json(usuario),
                "permissoes": acoes_do_perfil(usuario.perfil),
            },
        )

    def eu(req: Requisicao) -> Resposta:
        if req.usuario is None:
            raise NaoAutenticado("Não autenticado.")
        u = usuarios.obter(req.usuario.id)
        return Resposta(200, {"usuario": usuario_para_json(u), "permissoes": acoes_do_perfil(u.perfil)})

    def listar(req: Requisicao) -> Resposta:
        pagina = usuarios.listar(req.paginacao(), req.consulta.get("busca"))
        return Resposta(200, pagina_para_json(pagina, usuario_para_json))

    def obter(req: Requisicao) -> Resposta:
        return Resposta(200, usuario_para_json(usuarios.obter(req.id())))

    def criar(req: Requisicao) -> Resposta:
        return Resposta(201, usuario_para_json(usuarios.criar(req.corpo, req.usuario)))

    def alterar(req: Requisicao) -> Resposta:
        return Resposta(200, usuario_para_json(usuarios.alterar(req.id(), req.corpo, req.usuario)))

    def excluir(req: Requisicao) -> Resposta:
        usuarios.excluir(req.id(), req.usuario)
        return Resposta(204)

    return [
        Rota("POST", "/api/auth/login", login, None),
        Rota("GET", "/api/auth/eu", eu, "autenticado"),
        Rota("GET", "/api/usuarios", listar, "usuarios:gerenciar"),
        Rota("POST", "/api/usuarios", criar, "usuarios:gerenciar"),
        Rota("GET", "/api/usuarios/{id:int}", obter, "usuarios:gerenciar"),
        Rota("PUT", "/api/usuarios/{id:int}", alterar, "usuarios:gerenciar"),
        Rota("DELETE", "/api/usuarios/{id:int}", excluir, "usuarios:gerenciar"),
    ]
