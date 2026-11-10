"""PoliticaDeAcesso (RBAC) centralizada - ADR-003.

Alterar uma permissão é mexer só nesta tabela; nenhum outro módulo muda.
Ações seguem o padrão "recurso:operacao".
"""
from __future__ import annotations

from vetcare.compartilhado.tipos import Perfil

A, R, V = Perfil.ADMINISTRADOR, Perfil.RECEPCIONISTA, Perfil.VETERINARIO

PERMISSOES: dict[str, frozenset[Perfil]] = {
    # Identidade e Acesso (REQ 01)
    "usuarios:gerenciar": frozenset({A}),
    # Tutores e Animais (REQ 04, 05) - dados pessoais: veterinário só consulta
    "tutores:ler": frozenset({A, R, V}),
    "tutores:escrever": frozenset({A, R}),
    "animais:ler": frozenset({A, R, V}),
    "animais:escrever": frozenset({A, R}),
    # Equipe Clínica (REQ 06)
    "veterinarios:ler": frozenset({A, R, V}),
    "veterinarios:escrever": frozenset({A}),
    # Agenda (REQ 07)
    "consultas:ler": frozenset({A, R, V}),
    "consultas:agendar": frozenset({A, R}),
    # Auditoria (ADR-008) - acesso restrito ao administrador
    "auditoria:ler": frozenset({A}),
}


def pode(perfil: Perfil, acao: str) -> bool:
    """Nega por padrão: ação desconhecida não é permitida a ninguém."""
    return perfil in PERMISSOES.get(acao, frozenset())


def acoes_do_perfil(perfil: Perfil) -> list[str]:
    return sorted(acao for acao, perfis in PERMISSOES.items() if perfil in perfis)
