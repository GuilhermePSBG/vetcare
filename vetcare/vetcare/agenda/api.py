"""Interface pública do módulo Agenda.

Nesta etapa nenhum outro módulo consome a Agenda diretamente: a integração
acontece pelo evento `ConsultaAgendada`. Na etapa final, o módulo clínico
(Registrar Atendimento) usará esta porta para localizar a consulta.
"""
from __future__ import annotations

from .aplicacao.servicos import AgendamentoService
from .dominio.consulta import Consulta, StatusConsulta

__all__ = ["AgendaPort", "StatusConsulta"]


class AgendaPort:
    def __init__(self, servico: AgendamentoService) -> None:
        self._servico = servico

    def consulta(self, id: int) -> Consulta:
        return self._servico.obter(id)
