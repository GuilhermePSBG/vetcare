# VetCare — Sistema de Gestão para Clínica Veterinária

Trabalho II (Etapa 2) de Engenharia de Software 1 — UFBA.
Etapa 2: primeira etapa de implementação do VetCare, seguindo a arquitetura definida na Etapa 1:
**monolito modular com arquitetura hexagonal (portas e adaptadores) em cada módulo**.

## Requisitos implementados nesta etapa (6 de 17 ≈ 35%)

| REQ | Nome | Prioridade | Módulo |
|---|---|---|---|
| REQ 01 | Manter Usuário | Alta | Identidade e Acesso |
| REQ 02 | Autenticar Usuário | Alta | Identidade e Acesso |
| REQ 04 | Manter Tutor | Alta | Cadastro (Tutores e Animais) |
| REQ 05 | Manter Animal | Alta | Cadastro (Tutores e Animais) |
| REQ 06 | Manter Veterinário | Alta | Cadastro (Equipe Clínica) |
| REQ 07 | Agendar Consulta | Alta | Agenda |

Também foram implementados os atributos de qualidade que sustentam esses requisitos: perfis de
acesso (RBAC) aplicados em todas as rotas, auditoria em trilha somente de inserção, restrição única
no banco contra dupla marcação e testes automáticos da regra de dependência entre módulos.

## Como rodar

Pré-requisito: **Python 3.10 ou superior**.

```bash
git clone https://github.com/GuilhermePSBG/vetcare.git
cd vetcare

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# (opcional) dados de demonstração: usuários, veterinários, tutores, animais e consultas
python -m vetcare.dados_exemplo

# sobe o servidor
python -m vetcare
```

Acesse **http://127.0.0.1:8000**.

**Atalho no Windows:** dê dois cliques em `iniciar.bat`. Na primeira vez ele procura o Python (e tenta instalá-lo pelo winget se não houver), cria o ambiente, instala as dependências e carrega os dados de demonstração; depois disso só sobe o servidor e abre o navegador. A primeira execução precisa de internet. Para voltar aos dados iniciais, feche o sistema e rode `resetar_dados.bat`. Para mudar porta/host: `python -m vetcare --host 0.0.0.0 --port 8080`.

### Usuários

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador (criado automaticamente na 1ª execução) | `admin@vetcare.local` | `Admin@123` |
| Recepcionista (dados de demonstração) | `recepcao@vetcare.local` | `Senha@123` |
| Veterinário (dados de demonstração) | `vet@vetcare.local` | `Senha@123` |

O que cada perfil vê: o **Administrador** acessa tudo, inclusive Usuários e Auditoria; a
**Recepcionista** cadastra tutores e animais e agenda consultas; o **Veterinário** consulta a agenda
e os cadastros, sem alterar dados pessoais.

### Testes

```bash
pytest
```

São 54 testes: regras de domínio com dublês (sem banco), serviços com SQLite, testes ponta a ponta
pela API REST e **testes de arquitetura** que falham se um módulo acessar o interior de outro, se o
domínio importar infraestrutura ou se surgir dependência cíclica. Eles rodam também no GitHub
Actions (`.github/workflows/testes.yml`).

### Configuração (variáveis de ambiente)

| Variável | Padrão | Descrição |
|---|---|---|
| `VETCARE_DB` | `vetcare.db` | Arquivo do banco SQLite |
| `VETCARE_SEGREDO` | aleatório a cada execução | Segredo de assinatura dos tokens. **Defina em produção**, senão todos são deslogados ao reiniciar |
| `VETCARE_TOKEN_HORAS` | `8` | Validade da sessão |
| `VETCARE_MAX_TENTATIVAS` / `VETCARE_MINUTOS_BLOQUEIO` | `5` / `15` | Bloqueio temporário após senhas erradas |
| `VETCARE_CUSTO_HASH` | `17` | log2 do parâmetro N do scrypt (mínimo OWASP) |
| `VETCARE_DURACAO_CONSULTA` | `30` | Duração da consulta em minutos |
| `VETCARE_HORA_ABERTURA` / `VETCARE_HORA_FECHAMENTO` | `8` / `18` | Horário de funcionamento (seg a sáb) |
| `VETCARE_ADMIN_EMAIL` / `VETCARE_ADMIN_SENHA` | `admin@vetcare.local` / `Admin@123` | Administrador inicial |

## Arquitetura no código

```
vetcare/
├── app.py                 # ponto de composição + fachada REST (autenticação e RBAC em todas as rotas)
├── compartilhado/         # eventos de domínio, exceções, tipos comuns (não depende de nada)
├── infraestrutura/        # banco (SQLite), configuração, contrato HTTP neutro
├── identidade/            # REQ 01, 02 — usuários, login, perfis (RBAC)
│   ├── dominio/           #   entidades, política de acesso, portas (sem banco/web)
│   ├── aplicacao/         #   UsuarioService, AutenticacaoService
│   ├── adaptadores/       #   repositório SQLite, hash scrypt, token JWT, controller HTTP
│   └── api.py             #   interface pública: AutorizacaoPort
├── cadastro/              # REQ 04, 05, 06 — tutores, animais, veterinários
│   └── api.py             #   interface pública: CadastroPort (usada pela Agenda)
├── agenda/                # REQ 07 — agendamento, conflito de horário, horários livres
├── auditoria/             # trilha somente de inserção, alimentada por eventos
└── web/static/            # Portal Web (SPA em HTML/CSS/JS)
tests/                     # unitários, integração, API e arquitetura
docs/ADRs-Etapa2.md        # decisões e desvios em relação à Etapa 1
```

Regras do diagrama de pacotes da Etapa 1 verificadas por `tests/test_arquitetura.py`:
(1) módulos só se comunicam por `api.py` e eventos; (2) sem ciclos; (3) domínio não depende de
infraestrutura; (4) dependências seguem a tabela "Pode depender de".

## API REST

Todas as rotas, exceto login e saúde, exigem `Authorization: Bearer <token>`.
Erros seguem o formato `{"erro": {"codigo", "mensagem", "detalhes"}}`.
Listagens aceitam `?pagina=1&tamanho=20&busca=texto` (máx. 100 por página).

| Método | Rota | Permissão | REQ |
|---|---|---|---|
| POST | `/api/auth/login` | pública | 02 |
| GET | `/api/auth/eu` | autenticado | 02 |
| GET, POST | `/api/usuarios` | Administrador | 01 |
| GET, PUT, DELETE | `/api/usuarios/{id}` | Administrador | 01 |
| GET, POST | `/api/tutores` | ler: todos · escrever: Adm., Recepção | 04 |
| GET, PUT, DELETE | `/api/tutores/{id}` | idem | 04 |
| GET, POST | `/api/animais` (`?tutor_id=`) | ler: todos · escrever: Adm., Recepção | 05 |
| GET, PUT, DELETE | `/api/animais/{id}` | idem | 05 |
| GET, POST | `/api/veterinarios` (`?ativos=1`) | ler: todos · escrever: Adm. | 06 |
| GET, PUT, DELETE | `/api/veterinarios/{id}` | idem | 06 |
| POST | `/api/consultas` | Adm., Recepção | 07 |
| GET | `/api/consultas?data=AAAA-MM-DD&veterinario_id=` | todos | 07 |
| GET | `/api/consultas/{id}` | todos | 07 |
| GET | `/api/agenda/horarios-livres?veterinario_id=&data=` | todos | 07 |
| GET | `/api/auditoria` | Administrador | — |
| GET | `/api/saude` | pública | — |

Exemplo:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"recepcao@vetcare.local","senha":"Senha@123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")

curl -s -X POST localhost:8000/api/consultas -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"animal_id":1,"veterinario_id":1,"inicio":"2026-11-16T10:00","motivo":"Vacina"}'
```

## Regras de negócio principais

- **Tutor:** CPF validado pelos dígitos verificadores e único; não pode ser excluído se tiver animais.
- **Animal:** sempre ligado a um tutor existente; espécie, sexo e data de nascimento (não futura) obrigatórios; não pode ser excluído se tiver consultas.
- **Veterinário:** CRMV único (normalizado para `CRMV-UF 12345`); veterinário inativo não recebe consultas; com consultas, deve ser desativado em vez de excluído.
- **Usuário:** senha com 8+ caracteres, letras e números; o sistema sempre mantém um administrador ativo; ninguém exclui ou desativa a si mesmo.
- **Login:** mensagem genérica para e-mail ou senha errados; 5 erros bloqueiam a conta por 15 minutos; usuário desativado perde o acesso imediatamente, mesmo com token válido.
- **Consulta:** só no futuro, seg a sáb das 8h às 18h, na grade de 30 min; sem sobreposição para o mesmo veterinário nem para o mesmo animal; o índice único no banco barra dupla marcação mesmo com requisições simultâneas.

## Etapa final

REQ 03 (recuperar senha), 08 (cancelar consulta), 09 (agenda por semana/profissional), 10–13
(atendimento, prontuário, vacinação, prescrição), 14–15 (pagamento, dashboard), 16 (notificações
com Outbox) e 17 (relatórios). Antes da implantação: migração para PostgreSQL (ver ADR-011) e HTTPS
via proxy reverso.
