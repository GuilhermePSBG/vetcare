"""Testes de arquitetura (ADR-005): verificam automaticamente as regras do
diagrama de pacotes da Etapa 1, para que a arquitetura não se degrade.

Regras verificadas:
 1. Módulos só usam outros módulos pela interface pública (`<modulo>.api`).
 2. Sem dependências cíclicas entre módulos.
 3. O domínio não depende de infraestrutura, adaptadores, web ou banco.
 4. `compartilhado` não depende de nenhum outro pacote do sistema.
 5. As dependências entre módulos respeitam a tabela "Pode depender de".
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "vetcare"
MODULOS = {"identidade", "cadastro", "agenda", "auditoria"}
# Tabela "Pode depender de" da Etapa 1 (restrita aos módulos já implementados).
PERMITIDO = {
    "identidade": {"compartilhado", "infraestrutura"},
    "cadastro": {"compartilhado", "infraestrutura"},
    "agenda": {"cadastro", "compartilhado", "infraestrutura"},
    "auditoria": {"compartilhado", "infraestrutura"},
    "compartilhado": set(),
    "infraestrutura": {"compartilhado"},
}
PROIBIDOS_NO_DOMINIO = ("sqlite3", "starlette", "uvicorn", "jwt", "vetcare.infraestrutura")


def _importacoes(arquivo: Path) -> list[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    pacote = ".".join(arquivo.relative_to(RAIZ.parent).with_suffix("").parts[:-1])
    nomes = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes += [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            if no.level:  # import relativo -> resolve para absoluto
                base = pacote.split(".")[: len(pacote.split(".")) - (no.level - 1)]
                nomes.append(".".join(base + ([no.module] if no.module else [])))
            else:
                nomes.append(no.module or "")
    return nomes


def _arquivos(pacote: str):
    return [p for p in (RAIZ / pacote).rglob("*.py")]


def test_dominio_nao_depende_de_infraestrutura():
    violacoes = []
    for modulo in MODULOS - {"auditoria"}:
        for arq in (RAIZ / modulo / "dominio").rglob("*.py"):
            for imp in _importacoes(arq):
                if imp.startswith(PROIBIDOS_NO_DOMINIO) or ".adaptadores" in imp:
                    violacoes.append(f"{arq.relative_to(RAIZ)} importa {imp}")
    assert not violacoes, "\n".join(violacoes)


def test_modulos_so_usam_interface_publica_e_dependencias_permitidas():
    violacoes = []
    for origem in [*MODULOS, "compartilhado", "infraestrutura"]:
        for arq in _arquivos(origem):
            for imp in _importacoes(arq):
                partes = imp.split(".")
                if partes[0] != "vetcare" or len(partes) < 2 or partes[1] == origem:
                    continue
                destino = partes[1]
                if destino not in PERMITIDO[origem]:
                    violacoes.append(f"{origem} -> {destino} não permitido ({arq.relative_to(RAIZ)})")
                elif destino in MODULOS and (len(partes) < 3 or partes[2] != "api"):
                    violacoes.append(f"{origem} acessa interno de {destino}: {imp}")
    assert not violacoes, "\n".join(violacoes)


def test_sem_ciclos_entre_modulos():
    grafo: dict[str, set[str]] = {m: set() for m in PERMITIDO}
    for origem in grafo:
        for arq in _arquivos(origem):
            for imp in _importacoes(arq):
                partes = imp.split(".")
                if partes[0] == "vetcare" and len(partes) > 1 and partes[1] in grafo and partes[1] != origem:
                    grafo[origem].add(partes[1])

    def visitar(no, caminho):
        for vizinho in grafo[no]:
            assert vizinho not in caminho, f"Ciclo: {' -> '.join([*caminho, vizinho])}"
            visitar(vizinho, [*caminho, vizinho])

    for modulo in grafo:
        visitar(modulo, [modulo])
