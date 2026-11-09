"""Interface pública do módulo Cadastro: CadastroPort.

A Agenda consulta animal, tutor e veterinário por aqui, sem acessar as
tabelas do Cadastro diretamente (regra 1 do diagrama de pacotes).
"""
from __future__ import annotations

from dataclasses import dataclass

from .aplicacao.servicos import AnimalService, TutorService, VeterinarioService
from vetcare.compartilhado.excecoes import NaoEncontrado


@dataclass(frozen=True)
class AnimalResumo:
    id: int
    nome: str
    especie: str
    tutor_id: int
    tutor_nome: str
    tutor_telefone: str


@dataclass(frozen=True)
class VeterinarioResumo:
    id: int
    nome: str
    ativo: bool


class CadastroPort:
    def __init__(
        self, tutores: TutorService, animais: AnimalService, veterinarios: VeterinarioService
    ) -> None:
        self._tutores = tutores
        self._animais = animais
        self._vets = veterinarios

    def animal(self, id: int) -> AnimalResumo | None:
        try:
            a = self._animais.obter(id)
            t = self._tutores.obter(a.tutor_id)
        except NaoEncontrado:
            return None
        return AnimalResumo(a.id, a.nome, a.especie.value, t.id, t.nome, t.telefone)

    def veterinario(self, id: int) -> VeterinarioResumo | None:
        try:
            v = self._vets.obter(id)
        except NaoEncontrado:
            return None
        return VeterinarioResumo(v.id, v.nome, v.ativo)
