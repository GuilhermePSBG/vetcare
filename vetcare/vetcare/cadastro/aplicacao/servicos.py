"""Serviços de aplicação do módulo Cadastro (REQ 04, 05 e 06)."""
from __future__ import annotations

from vetcare.compartilhado.eventos import EventoDeDominio, PublicadorDeEventos
from vetcare.compartilhado.excecoes import Conflito, DadosInvalidos, NaoEncontrado
from vetcare.compartilhado.tipos import Pagina, Paginacao, UsuarioAutenticado

from ..dominio.entidades import Animal, Tutor, Veterinario
from ..dominio.portas import RepositorioDeAnimais, RepositorioDeTutores, RepositorioDeVeterinarios


class _Base:
    def __init__(self, eventos: PublicadorDeEventos) -> None:
        self._eventos = eventos

    def _publicar(self, nome: str, dados: dict, autor: UsuarioAutenticado | None) -> None:
        self._eventos.publicar(EventoDeDominio(nome, dados, autor.id if autor else None))


class TutorService(_Base):
    """REQ 04 - Manter Tutor."""

    def __init__(self, tutores: RepositorioDeTutores, eventos: PublicadorDeEventos) -> None:
        super().__init__(eventos)
        self._repo = tutores

    def cadastrar(self, dados: dict, autor: UsuarioAutenticado | None) -> Tutor:
        tutor = Tutor.de_dados(dados)
        if self._repo.obter_por_cpf(tutor.cpf):
            raise Conflito("Já existe um tutor com este CPF.", {"campo": "cpf"})
        tutor = self._repo.salvar(tutor)
        self._publicar("TutorCadastrado", {"tutor_id": tutor.id}, autor)
        return tutor

    def alterar(self, id: int, dados: dict, autor: UsuarioAutenticado | None) -> Tutor:
        tutor = self.obter(id)
        tutor.atualizar(dados)
        existente = self._repo.obter_por_cpf(tutor.cpf)
        if existente and existente.id != tutor.id:
            raise Conflito("Já existe um tutor com este CPF.", {"campo": "cpf"})
        tutor = self._repo.salvar(tutor)
        self._publicar("TutorAlterado", {"tutor_id": tutor.id, "campos": sorted(dados)}, autor)
        return tutor

    def excluir(self, id: int, autor: UsuarioAutenticado | None) -> None:
        self.obter(id)
        self._repo.excluir(id)
        self._publicar("TutorExcluido", {"tutor_id": id}, autor)

    def obter(self, id: int) -> Tutor:
        tutor = self._repo.obter(id)
        if tutor is None:
            raise NaoEncontrado("Tutor não encontrado.")
        return tutor

    def listar(self, paginacao: Paginacao, busca: str | None = None) -> Pagina[Tutor]:
        return self._repo.listar(paginacao, busca)


class AnimalService(_Base):
    """REQ 05 - Manter Animal (sempre associado a um tutor)."""

    def __init__(
        self,
        animais: RepositorioDeAnimais,
        tutores: RepositorioDeTutores,
        eventos: PublicadorDeEventos,
    ) -> None:
        super().__init__(eventos)
        self._repo = animais
        self._tutores = tutores

    def cadastrar(self, dados: dict, autor: UsuarioAutenticado | None) -> Animal:
        animal = Animal.de_dados(dados)
        self._garantir_tutor(animal.tutor_id)
        animal = self._repo.salvar(animal)
        self._publicar("AnimalCadastrado", {"animal_id": animal.id, "tutor_id": animal.tutor_id}, autor)
        return animal

    def alterar(self, id: int, dados: dict, autor: UsuarioAutenticado | None) -> Animal:
        animal = self.obter(id)
        animal.atualizar(dados)
        self._garantir_tutor(animal.tutor_id)
        animal = self._repo.salvar(animal)
        self._publicar("AnimalAlterado", {"animal_id": animal.id, "campos": sorted(dados)}, autor)
        return animal

    def excluir(self, id: int, autor: UsuarioAutenticado | None) -> None:
        self.obter(id)
        self._repo.excluir(id)
        self._publicar("AnimalExcluido", {"animal_id": id}, autor)

    def obter(self, id: int) -> Animal:
        animal = self._repo.obter(id)
        if animal is None:
            raise NaoEncontrado("Animal não encontrado.")
        return animal

    def listar(
        self, paginacao: Paginacao, busca: str | None = None, tutor_id: int | None = None
    ) -> Pagina[Animal]:
        return self._repo.listar(paginacao, busca, tutor_id)

    def _garantir_tutor(self, tutor_id: int) -> None:
        if self._tutores.obter(tutor_id) is None:
            raise DadosInvalidos("Tutor informado não existe.", {"campo": "tutor_id"})


class VeterinarioService(_Base):
    """REQ 06 - Manter Veterinário."""

    def __init__(self, veterinarios: RepositorioDeVeterinarios, eventos: PublicadorDeEventos) -> None:
        super().__init__(eventos)
        self._repo = veterinarios

    def cadastrar(self, dados: dict, autor: UsuarioAutenticado | None) -> Veterinario:
        vet = Veterinario.de_dados(dados)
        if self._repo.obter_por_crmv(vet.crmv):
            raise Conflito("Já existe um veterinário com este CRMV.", {"campo": "crmv"})
        vet = self._repo.salvar(vet)
        self._publicar("VeterinarioCadastrado", {"veterinario_id": vet.id}, autor)
        return vet

    def alterar(self, id: int, dados: dict, autor: UsuarioAutenticado | None) -> Veterinario:
        vet = self.obter(id)
        vet.atualizar(dados)
        existente = self._repo.obter_por_crmv(vet.crmv)
        if existente and existente.id != vet.id:
            raise Conflito("Já existe um veterinário com este CRMV.", {"campo": "crmv"})
        vet = self._repo.salvar(vet)
        self._publicar("VeterinarioAlterado", {"veterinario_id": vet.id, "campos": sorted(dados)}, autor)
        return vet

    def excluir(self, id: int, autor: UsuarioAutenticado | None) -> None:
        self.obter(id)
        self._repo.excluir(id)
        self._publicar("VeterinarioExcluido", {"veterinario_id": id}, autor)

    def obter(self, id: int) -> Veterinario:
        vet = self._repo.obter(id)
        if vet is None:
            raise NaoEncontrado("Veterinário não encontrado.")
        return vet

    def listar(
        self, paginacao: Paginacao, busca: str | None = None, somente_ativos: bool = False
    ) -> Pagina[Veterinario]:
        return self._repo.listar(paginacao, busca, somente_ativos)
