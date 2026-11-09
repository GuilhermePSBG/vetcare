"""Exceções de domínio comuns a todos os módulos.

A camada HTTP converte cada exceção em uma resposta de erro padronizada
(tática de usabilidade: "mensagens de erro padronizadas pela API").
"""


class ErroDeDominio(Exception):
    """Base de todas as exceções de negócio do VetCare."""

    codigo = "ERRO_DE_DOMINIO"
    status_http = 400

    def __init__(self, mensagem: str, detalhes: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes or {}


class DadosInvalidos(ErroDeDominio):
    codigo = "DADOS_INVALIDOS"
    status_http = 422


class NaoEncontrado(ErroDeDominio):
    codigo = "NAO_ENCONTRADO"
    status_http = 404


class Conflito(ErroDeDominio):
    codigo = "CONFLITO"
    status_http = 409


class NaoAutenticado(ErroDeDominio):
    codigo = "NAO_AUTENTICADO"
    status_http = 401


class AcessoNegado(ErroDeDominio):
    codigo = "ACESSO_NEGADO"
    status_http = 403


class ContaBloqueada(ErroDeDominio):
    codigo = "CONTA_BLOQUEADA"
    status_http = 423
