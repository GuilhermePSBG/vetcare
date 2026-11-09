"""Barramento de eventos interno (in-process).

Implementa a comunicação por eventos prevista na ADR-002: módulos publicam
fatos de domínio (ex.: ConsultaAgendada) sem conhecer quem os consome.
Os consumidores (Auditoria hoje; Comunicação e Gerencial nas próximas sprints)
se inscrevem no ponto de composição da aplicação (vetcare/app.py).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class EventoDeDominio:
    nome: str
    dados: dict[str, Any]
    usuario_id: int | None = None
    ocorrido_em: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


Manipulador = Callable[[EventoDeDominio], None]


class BarramentoDeEventos:
    """Publica eventos de forma síncrona para os inscritos.

    Inscrever-se em "*" recebe todos os eventos (usado pela Auditoria).
    Uma falha em um consumidor não interrompe a operação de quem publicou
    (degradação graciosa); o erro é registrado em `falhas`.
    """

    def __init__(self) -> None:
        self._inscritos: dict[str, list[Manipulador]] = defaultdict(list)
        self.falhas: list[tuple[str, str]] = []

    def inscrever(self, nome_evento: str, manipulador: Manipulador) -> None:
        self._inscritos[nome_evento].append(manipulador)

    def publicar(self, evento: EventoDeDominio) -> None:
        for manipulador in [*self._inscritos.get(evento.nome, []), *self._inscritos.get("*", [])]:
            try:
                manipulador(evento)
            except Exception as exc:  # noqa: BLE001 - consumidor nunca derruba o publicador
                self.falhas.append((evento.nome, repr(exc)))


class PublicadorDeEventos:
    """Porta usada pelos módulos para publicar eventos (facilita dublês em testes)."""

    def publicar(self, evento: EventoDeDominio) -> None:  # pragma: no cover - interface
        raise NotImplementedError
