# ADRs da Etapa 2 — desvios e complementos à arquitetura da Etapa 1

As ADR-001 a ADR-009 estão no documento de arquitetura da Etapa 1 e continuam válidas,
exceto nos pontos alterados abaixo. A numeração continua a partir da ADR-010.

| ADR | Título | Relação com a Etapa 1 | Status |
|---|---|---|---|
| ADR-010 | Linguagem e framework: Python 3 + Starlette + Uvicorn | Complementa ADR-002 (a Etapa 1 não fixou linguagem) | Aceita |
| ADR-011 | SQLite nesta sprint, PostgreSQL mantido como alvo de produção | **Desvio** parcial da ADR-004 | Aceita |
| ADR-012 | Hash de senha com scrypt | **Desvio** da tática "Argon2 ou bcrypt" (ADR-003) | Aceita |
| ADR-013 | Barramento de eventos síncrono; tabela Outbox adiada para o REQ 16 | **Desvio** de cronograma da ADR-007 | Aceita |
| ADR-014 | Cache da agenda do dia adiado | **Desvio** parcial da ADR-009 | Aceita |
| ADR-015 | Agenda declara a própria porta de leitura do Cadastro | Refinamento da regra de dependência (ADR-005) | Aceita |

---

## ADR-010 — Linguagem e framework: Python 3 + Starlette + Uvicorn

**Status:** Aceita

**Contexto.** A Etapa 1 definiu o estilo (monolito modular com hexagonal por módulo, ADR-002),
mas não a linguagem nem o framework. A equipe é pequena (premissa P5) e precisa de algo simples
de instalar e rodar na máquina do avaliador.

**Decisão.** Python 3.10+ com **Starlette** (servidor ASGI enxuto) e **Uvicorn**. O Portal Web é
uma SPA em HTML/CSS/JavaScript sem framework, servida pela própria aplicação. A fachada REST
(`vetcare/app.py`) traduz um contrato neutro (`Rota`, `Requisicao`, `Resposta`) para o Starlette,
de modo que os módulos não importam o framework.

**Alternativas.**
- *Django*: produtivo, mas impõe ORM e organização em camadas globais (models/views), o que
  conflita com a hexagonal por módulo e com o "domínio isolado de frameworks".
- *FastAPI*: boa opção; foi descartada nesta sprint para reduzir dependências (traz Pydantic como
  modelo central, que acabaria vazando para o domínio).
- *SPA com React/Vue*: exigiria build com Node; para 6 telas o ganho não compensa.

**Consequências.** Positivas: 3 dependências de execução, domínio 100% em Python puro,
instalação com um `pip install`. Negativas: sem documentação OpenAPI automática (a tabela de
endpoints fica no README; gerar OpenAPI fica para a próxima sprint); a SPA sem framework pede
disciplina para não crescer desorganizada.

## ADR-011 — SQLite nesta sprint, PostgreSQL mantido como alvo de produção

**Status:** Aceita — altera parcialmente a ADR-004

**Contexto.** A ADR-004 escolheu PostgreSQL. Para a avaliação, o sistema precisa rodar sem que o
avaliador instale e configure um servidor de banco.

**Decisão.** Usar **SQLite** (biblioteca padrão do Python) nesta sprint, mantendo todas as
garantias de integridade que motivaram a ADR-004:
transações ACID (`BEGIN IMMEDIATE`), chaves estrangeiras com `ON DELETE RESTRICT`, restrição
única parcial `(veterinario_id, inicio) WHERE status='AGENDADA'` e trilha de auditoria protegida
por gatilhos contra UPDATE/DELETE. O acesso ao banco fica só nos adaptadores de repositório,
atrás de portas; trocar para PostgreSQL é escrever novos adaptadores, sem mudar domínio nem
serviços.

**Alternativas.** PostgreSQL via Docker desde já (mais fiel à ADR-004, porém mais um pré-requisito
para rodar o projeto).

**Consequências.** Positivas: o sistema roda com um comando. Negativas: SQLite serializa escritas
(suficiente para "dezenas de usuários", premissa P1, mas não para várias unidades); backup contínuo
com restauração a um instante (ADR-006) só será possível após a migração para PostgreSQL, prevista
antes da implantação.

## ADR-012 — Hash de senha com scrypt

**Status:** Aceita — altera a tática "Senha com hash e salt (Argon2 ou bcrypt)"

**Contexto.** Argon2 e bcrypt exigem bibliotecas com código nativo. Queremos manter o objetivo da
tática (um vazamento do banco não expõe senhas) sem dependências nativas.

**Decisão.** Usar **scrypt** (`hashlib.scrypt`, biblioteca padrão), com sal aleatório de 16 bytes
por senha e parâmetros N=2^17, r=8, p=1 (mínimo recomendado pela OWASP quando Argon2id não está disponível), gravados junto do hash. O custo é configurável por `VETCARE_CUSTO_HASH`; com o padrão, cada login leva cerca de 0,3 s e usa 128 MiB de memória durante a verificação. A comparação usa tempo constante.
O adaptador implementa a porta `GeradorDeHash`, então trocar para Argon2 é trocar um adaptador.

**Alternativas.** Argon2id (preferível, mas com dependência nativa); PBKDF2 (padrão, porém não é
resistente a ataques com hardware dedicado como o scrypt).

**Consequências.** Positivas: função de derivação "memory-hard" recomendada pela OWASP, sem
dependência extra. Negativas: parâmetros precisam ser revistos com o tempo; o formato armazenado
já guarda os parâmetros para permitir isso.

## ADR-013 — Barramento de eventos síncrono; tabela Outbox adiada para o REQ 16

**Status:** Aceita — adia parte da ADR-007

**Contexto.** A ADR-007 prevê Outbox para enviar notificações ao tutor com retentativa. Nesta
sprint ainda não há notificações (REQ 16), e o único consumidor de eventos é a Auditoria (ADR-008).

**Decisão.** Implementar o barramento interno (`compartilhado/eventos.py`) com entrega síncrona
dentro da mesma transação do fato de origem. Consumidores não derrubam quem publicou (falhas são
registradas). A Agenda já publica `ConsultaAgendada`; quando o módulo Comunicação for criado, ele
gravará esses eventos na tabela Outbox e um processo separado fará o envio, como na ADR-007.

**Alternativas.** Criar a Outbox já agora, sem consumidor (código sem uso nesta sprint).

**Consequências.** Positivas: auditoria gravada atomicamente com a operação; nenhum código morto.
Negativas: um consumidor lento atrasaria a operação — aceitável enquanto o único consumidor é
uma inserção local.

## ADR-014 — Cache da agenda do dia adiado

**Status:** Aceita — adia parte da ADR-009

**Contexto.** A ADR-009 previa cache de curta duração para a agenda do dia. Com índices em
`(veterinario_id, inicio)`, `(animal_id, inicio)` e `(inicio)`, a listagem do dia já é rápida.
Medição feita pela equipe com cerca de 12.850 consultas (cerca de 10 meses de agenda cheia para 5
veterinários) e 300 tutores: listagem de um dia com 50 consultas em 1,4 ms (p95) e cálculo de
horários livres em 0,1 ms (p95), medidos na camada de aplicação, sem a rede. A meta da Etapa 1 é
2 s para 95% das consultas.

**Decisão.** Não implementar cache nesta sprint. Manter índices e paginação nas listagens.
Reavaliar quando as visões por semana e por profissional (REQ 09) forem implementadas, medindo o
tempo de resposta.

**Consequências.** Positivas: sem risco de exibir agenda desatualizada e sem lógica de invalidação.
Negativas: se a carga crescer, o cache volta a ser necessário (a porta de leitura já permite
incluí-lo como adaptador).

## ADR-015 — Agenda declara a própria porta de leitura do Cadastro

**Status:** Aceita — refina a ADR-005

**Contexto.** Na Etapa 1, a Agenda "consome CadastroPort". Se o núcleo da Agenda importasse a
classe do Cadastro, o domínio da Agenda passaria a depender de outro módulo.

**Decisão.** O núcleo da Agenda declara a porta `CadastroLeitura` (um `Protocol` com
`animal(id)` e `veterinario(id)`). O módulo Cadastro publica `CadastroPort` em `cadastro/api.py`,
e o ponto de composição (`app.py`) liga uma à outra. Testes de arquitetura em
`tests/test_arquitetura.py` verificam, a cada execução e na integração contínua, que:
o domínio não importa infraestrutura, módulos só usam a interface pública (`api`) uns dos
outros, as dependências seguem a tabela da Etapa 1 e não há ciclos.

**Consequências.** Positivas: a Agenda pode ser testada com um Cadastro falso; a dependência
Agenda→Cadastro continua existindo em tempo de execução, como no diagrama, mas sem acoplamento
de código. Negativas: uma interface a mais para manter.
