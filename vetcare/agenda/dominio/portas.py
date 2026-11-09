"""Portas do módulo Agenda.

`CadastroLeitura` é a porta consumida (Figura 3 da Etapa 1: CadastroPort);
no ponto de composição ela é ligada à interface pública do módulo Cadastro.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable, Protocol

from .consulta import Consulta


class AnimalInfo(Protocol):
    id: int
    nome: str
    tutor_id: int
    tutor_nome: str


class VeterinarioInfo(Protocol):
    id: int
    nome: str
    ativo: bool


class CadastroLeitura(Protocol):
    def animal(self, id: int) -> AnimalInfo | None: ...
    def veterinario(self, id: int) -> VeterinarioInfo | None: ...


class RepositorioDeConsultas(Protocol):
    def salvar(self, consulta: Consulta) -> Consulta:
        """Levanta Conflito se a restrição única (veterinário + início ativo) for violada."""
        ...

    def obter(self, id: int) -> Consulta | None: ...
    def do_veterinario(self, veterinario_id: int, inicio: datetime, fim: datetime) -> list[Consulta]: ...
    def do_animal(self, animal_id: int, inicio: datetime, fim: datetime) -> list[Consulta]: ...
    def no_periodo(
        self, inicio: datetime, fim: datetime, veterinario_id: int | None
    ) -> list[Consulta]: ...


# Abre uma transação que engloba "verificar conflito + gravar".
UnidadeDeTrabalho = Callable[[], AbstractContextManager]
