/* VetCare - Portal Web (SPA). Consome a API REST; telas exibidas conforme o perfil. */
"use strict";

// ------------------------------------------------------------------ utilidades
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hojeISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const dataBR = (iso) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "");
const hora = (iso) => iso.slice(11, 16);
const fmtCPF = (c) => (c && c.length === 11 ? `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}` : c || "");
const fmtTel = (t) => (!t ? "" : t.length === 11 ? `(${t.slice(0, 2)}) ${t.slice(2, 7)}-${t.slice(7)}` : `(${t.slice(0, 2)}) ${t.slice(2, 6)}-${t.slice(6)}`);
const PERFIS = { ADMINISTRADOR: "Administrador", RECEPCIONISTA: "Recepcionista", VETERINARIO: "Veterinário" };
const ESPECIES = { CANINA: "Canina", FELINA: "Felina", AVE: "Ave", ROEDOR: "Roedor", REPTIL: "Réptil", OUTRA: "Outra" };

const armazem = {
  ler(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
  gravar(k, v) { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch { /* sem storage */ } },
};

let sessao = { token: armazem.ler("vetcare.token"), usuario: null, permissoes: [] };
const pode = (acao) => sessao.permissoes.includes(acao);

function aviso(msg) {
  const el = $("#aviso");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => (el.hidden = true), 3200);
}

async function api(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: {} };
  if (sessao.token) opcoes.headers.Authorization = `Bearer ${sessao.token}`;
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  const r = await fetch(caminho, opcoes);
  if (r.status === 204) return null;
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401 && caminho !== "/api/auth/login") sair(false);
    const erro = new Error(dados?.erro?.mensagem || `Erro ${r.status}`);
    erro.detalhes = dados?.erro?.detalhes || {};
    throw erro;
  }
  return dados;
}

// ------------------------------------------------------------------ autenticação (REQ 02)
$("#form-login").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const erro = $("#erro-login");
  erro.hidden = true;
  try {
    const r = await api("POST", "/api/auth/login", { email: f.email.value, senha: f.senha.value });
    sessao = { token: r.token, usuario: r.usuario, permissoes: r.permissoes };
    armazem.gravar("vetcare.token", r.token);
    f.reset();
    iniciarApp();
  } catch (e) {
    erro.textContent = e.message;
    erro.hidden = false;
  }
});

function sair(avisar = true) {
  sessao = { token: null, usuario: null, permissoes: [] };
  armazem.gravar("vetcare.token", null);
  $("#tela-app").hidden = true;
  $("#tela-login").hidden = false;
  if (avisar) aviso("Sessão encerrada.");
}
$("#btn-sair").addEventListener("click", () => sair());

// ------------------------------------------------------------------ navegação
const PAGINAS = [
  { rota: "agenda", titulo: "Agenda", permissao: "consultas:ler", render: paginaAgenda, grupo: "Atendimento" },
  { rota: "tutores", titulo: "Tutores", permissao: "tutores:ler", render: () => paginaCRUD(CRUD.tutores), grupo: "Cadastros" },
  { rota: "animais", titulo: "Animais", permissao: "animais:ler", render: () => paginaCRUD(CRUD.animais) },
  { rota: "veterinarios", titulo: "Veterinários", permissao: "veterinarios:ler", render: () => paginaCRUD(CRUD.veterinarios) },
  { rota: "usuarios", titulo: "Usuários", permissao: "usuarios:gerenciar", render: () => paginaCRUD(CRUD.usuarios), grupo: "Administração" },
  { rota: "auditoria", titulo: "Auditoria", permissao: "auditoria:ler", render: paginaAuditoria },
];

function montarMenu() {
  const nav = $("#menu");
  nav.innerHTML = "";
  for (const p of PAGINAS.filter((p) => pode(p.permissao))) {
    if (p.grupo) nav.insertAdjacentHTML("beforeend", `<div class="grupo">${esc(p.grupo)}</div>`);
    nav.insertAdjacentHTML("beforeend", `<a href="#/${p.rota}" data-rota="${p.rota}">${esc(p.titulo)}</a>`);
  }
}

function navegar() {
  const visiveis = PAGINAS.filter((p) => pode(p.permissao));
  const rota = location.hash.replace("#/", "") || visiveis[0]?.rota;
  const pagina = visiveis.find((p) => p.rota === rota) || visiveis[0];
  if (!pagina) return;
  document.querySelectorAll("#menu a").forEach((a) => a.classList.toggle("ativo", a.dataset.rota === pagina.rota));
  $("#titulo-pagina").textContent = `Início / ${pagina.titulo}`;
  $("#conteudo").innerHTML = '<div class="vazio">Carregando…</div>';
  pagina.render().catch((e) => ($("#conteudo").innerHTML = `<div class="alerta erro">${esc(e.message)}</div>`));
}
window.addEventListener("hashchange", () => sessao.usuario && navegar());

async function iniciarApp() {
  if (!sessao.usuario) {
    const r = await api("GET", "/api/auth/eu");
    sessao.usuario = r.usuario;
    sessao.permissoes = r.permissoes;
  }
  const u = sessao.usuario;
  $("#usuario-nome").textContent = u.nome;
  $("#usuario-perfil").textContent = PERFIS[u.perfil];
  $("#avatar").textContent = u.nome.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  $("#tela-login").hidden = true;
  $("#tela-app").hidden = false;
  montarMenu();
  navegar();
}

// ------------------------------------------------------------------ formulário em modal
function abrirModal({ titulo, campos, valores = {}, aoSalvar, extra }) {
  const dlg = $("#modal");
  const form = $("#modal-form");
  const linhas = campos.map((c) => {
    const v = valores[c.nome] ?? c.padrao ?? "";
    const cls = c.inteiro ? "inteiro" : "";
    const req = c.obrigatorio ? "required" : "";
    if (c.tipo === "select") {
      const ops = c.opcoes.map(([val, txt]) => `<option value="${esc(val)}" ${String(val) === String(v) ? "selected" : ""}>${esc(txt)}</option>`).join("");
      return `<label class="${cls}">${esc(c.rotulo)}<select name="${c.nome}" ${req}><option value="">Selecione…</option>${ops}</select></label>`;
    }
    if (c.tipo === "checkbox") {
      return `<label class="${cls}" style="flex-direction:row;align-items:center"><input type="checkbox" name="${c.nome}" ${v ? "checked" : ""}> ${esc(c.rotulo)}</label>`;
    }
    if (c.tipo === "textarea") return `<label class="${cls}">${esc(c.rotulo)}<textarea name="${c.nome}" rows="2">${esc(v)}</textarea></label>`;
    return `<label class="${cls}">${esc(c.rotulo)}<input name="${c.nome}" type="${c.tipo || "text"}" value="${esc(v)}" ${req} placeholder="${esc(c.dica || "")}"></label>`;
  });
  form.innerHTML = `<h2>${esc(titulo)}</h2><div class="campos">${linhas.join("")}</div>${extra || ""}
    <div id="erro-modal" class="alerta erro" hidden></div>
    <div class="rodape-modal"><button class="btn" value="cancelar" formnovalidate>Cancelar</button><button class="btn primario" id="btn-salvar" type="button">Salvar</button></div>`;
  form.onsubmit = (ev) => {
    if (ev.submitter?.value === "cancelar") return; // fecha o diálogo
    ev.preventDefault(); // Enter num campo = salvar
    $("#btn-salvar").click();
  };
  $("#btn-salvar").onclick = async () => {
    const dados = {};
    for (const c of campos) {
      const el = form.elements[c.nome];
      if (!el) continue;
      if (c.tipo === "checkbox") dados[c.nome] = el.checked;
      else if (c.tipo === "password" && !el.value) continue;
      else dados[c.nome] = el.value;
    }
    try {
      await aoSalvar(dados, form);
      dlg.close();
    } catch (e) {
      const caixa = $("#erro-modal");
      caixa.textContent = e.message;
      caixa.hidden = false;
      const campo = e.detalhes?.campo && form.elements[e.detalhes.campo];
      if (campo && campo.focus) campo.focus();
    }
  };
  dlg.showModal();
  return form;
}

// ------------------------------------------------------------------ CRUD genérico (REQ 01, 04, 05, 06)
const CRUD = {
  tutores: {
    titulo: "Tutores", singular: "tutor", recurso: "/api/tutores", escrever: "tutores:escrever",
    subtitulo: "Responsáveis pelos animais atendidos na clínica.",
    colunas: [["Nome", (t) => `<strong>${esc(t.nome)}</strong>`], ["CPF", (t) => fmtCPF(t.cpf)], ["Telefone", (t) => fmtTel(t.telefone)], ["E-mail", (t) => esc(t.email)]],
    campos: () => [
      { nome: "nome", rotulo: "Nome completo", obrigatorio: true, inteiro: true },
      { nome: "cpf", rotulo: "CPF", obrigatorio: true, dica: "000.000.000-00" },
      { nome: "telefone", rotulo: "Telefone", obrigatorio: true, dica: "(71) 99999-9999" },
      { nome: "email", rotulo: "E-mail", tipo: "email", inteiro: true },
      { nome: "endereco", rotulo: "Endereço", inteiro: true },
    ],
  },
  animais: {
    titulo: "Animais", singular: "animal", recurso: "/api/animais", escrever: "animais:escrever",
    subtitulo: "Pacientes da clínica, sempre vinculados a um tutor.",
    colunas: [["Nome", (a) => `<strong>${esc(a.nome)}</strong>`], ["Espécie / raça", (a) => `${esc(ESPECIES[a.especie])}${a.raca ? " · " + esc(a.raca) : ""}`],
      ["Sexo", (a) => (a.sexo === "M" ? "Macho" : "Fêmea")], ["Nascimento", (a) => dataBR(a.data_nascimento)], ["Tutor", (a) => esc(a.tutor_nome)]],
    campos: async () => {
      const tutores = (await api("GET", "/api/tutores?tamanho=100")).itens;
      return [
        { nome: "tutor_id", rotulo: "Tutor", tipo: "select", obrigatorio: true, inteiro: true, opcoes: tutores.map((t) => [t.id, `${t.nome} — ${fmtCPF(t.cpf)}`]) },
        { nome: "nome", rotulo: "Nome do animal", obrigatorio: true },
        { nome: "especie", rotulo: "Espécie", tipo: "select", obrigatorio: true, opcoes: Object.entries(ESPECIES) },
        { nome: "raca", rotulo: "Raça" },
        { nome: "sexo", rotulo: "Sexo", tipo: "select", obrigatorio: true, opcoes: [["M", "Macho"], ["F", "Fêmea"]] },
        { nome: "data_nascimento", rotulo: "Data de nascimento", tipo: "date", obrigatorio: true },
      ];
    },
  },
  veterinarios: {
    titulo: "Veterinários", singular: "veterinário", recurso: "/api/veterinarios", escrever: "veterinarios:escrever",
    subtitulo: "Equipe clínica que atende na agenda.",
    colunas: [["Nome", (v) => `<strong>${esc(v.nome)}</strong>`], ["CRMV", (v) => esc(v.crmv)], ["Especialidade", (v) => esc(v.especialidade)],
      ["Telefone", (v) => fmtTel(v.telefone)], ["Situação", (v) => (v.ativo ? '<span class="etiqueta">Ativo</span>' : '<span class="etiqueta cinza">Inativo</span>')]],
    campos: () => [
      { nome: "nome", rotulo: "Nome", obrigatorio: true, inteiro: true },
      { nome: "crmv", rotulo: "CRMV", obrigatorio: true, dica: "CRMV-BA 12345" },
      { nome: "especialidade", rotulo: "Especialidade" },
      { nome: "telefone", rotulo: "Telefone", obrigatorio: true },
      { nome: "email", rotulo: "E-mail", tipo: "email", obrigatorio: true },
      { nome: "ativo", rotulo: "Ativo (recebe agendamentos)", tipo: "checkbox", padrao: true, inteiro: true },
    ],
  },
  usuarios: {
    titulo: "Usuários", singular: "usuário", recurso: "/api/usuarios", escrever: "usuarios:gerenciar",
    subtitulo: "Contas de acesso e perfis (Administrador, Recepcionista, Veterinário).",
    colunas: [["Nome", (u) => `<strong>${esc(u.nome)}</strong>`], ["E-mail", (u) => esc(u.email)], ["Perfil", (u) => `<span class="etiqueta">${PERFIS[u.perfil]}</span>`],
      ["Situação", (u) => (u.ativo ? "Ativo" : '<span class="etiqueta cinza">Inativo</span>')]],
    campos: (edicao) => [
      { nome: "nome", rotulo: "Nome", obrigatorio: true, inteiro: true },
      { nome: "email", rotulo: "E-mail", tipo: "email", obrigatorio: true },
      { nome: "perfil", rotulo: "Perfil", tipo: "select", obrigatorio: true, opcoes: Object.entries(PERFIS) },
      { nome: "senha", rotulo: edicao ? "Nova senha (deixe em branco para manter)" : "Senha", tipo: "password", obrigatorio: !edicao, inteiro: true, dica: "mín. 8 caracteres, letras e números" },
      ...(edicao ? [{ nome: "ativo", rotulo: "Ativo", tipo: "checkbox", inteiro: true }] : []),
    ],
  },
};

async function paginaCRUD(cfg, estado = { pagina: 1, busca: "" }) {
  const qs = new URLSearchParams({ pagina: estado.pagina, tamanho: 10, busca: estado.busca });
  const dados = await api("GET", `${cfg.recurso}?${qs}`);
  const escrever = pode(cfg.escrever);
  const totalPag = Math.max(1, Math.ceil(dados.total / dados.tamanho));
  const linhas = dados.itens.map((item) => `<tr>${cfg.colunas.map(([, f]) => `<td>${f(item)}</td>`).join("")}
      ${escrever ? `<td class="acoes"><button class="btn mini" data-editar="${item.id}">Editar</button> <button class="btn mini perigo" data-excluir="${item.id}">Excluir</button></td>` : ""}</tr>`).join("");
  $("#conteudo").innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>${esc(cfg.titulo)}</h1><div class="sutil">${esc(cfg.subtitulo)}</div></div>
      <div class="barra">
        <input id="busca" type="search" placeholder="Buscar…" value="${esc(estado.busca)}">
        ${escrever ? `<button class="btn primario" id="btn-novo">+ Novo ${esc(cfg.singular)}</button>` : ""}
      </div>
    </div>
    <div class="cartao">
      ${dados.itens.length ? `<table><thead><tr>${cfg.colunas.map(([t]) => `<th>${esc(t)}</th>`).join("")}${escrever ? "<th></th>" : ""}</tr></thead><tbody>${linhas}</tbody></table>`
        : `<div class="vazio">Nenhum registro encontrado.</div>`}
      <div class="paginacao"><span class="sutil">${dados.total} registro(s)</span>
        <div class="barra"><button class="btn mini" id="ant" ${estado.pagina <= 1 ? "disabled" : ""}>‹ Anterior</button>
        <span>${estado.pagina} / ${totalPag}</span>
        <button class="btn mini" id="prox" ${estado.pagina >= totalPag ? "disabled" : ""}>Próxima ›</button></div></div>
    </div>`;

  const recarregar = (mud = {}) => paginaCRUD(cfg, { ...estado, ...mud });
  let espera;
  $("#busca").addEventListener("input", (e) => { clearTimeout(espera); espera = setTimeout(() => recarregar({ busca: e.target.value, pagina: 1 }).then(() => { const b = $("#busca"); b.focus(); b.setSelectionRange(b.value.length, b.value.length); }), 300); });
  $("#ant").onclick = () => recarregar({ pagina: estado.pagina - 1 });
  $("#prox").onclick = () => recarregar({ pagina: estado.pagina + 1 });
  if (!escrever) return;

  $("#btn-novo").onclick = async () => abrirModal({
    titulo: `Novo ${cfg.singular}`, campos: await cfg.campos(false),
    aoSalvar: async (d) => { await api("POST", cfg.recurso, d); aviso("Cadastro realizado."); recarregar(); },
  });
  document.querySelectorAll("[data-editar]").forEach((b) => (b.onclick = async () => {
    const item = await api("GET", `${cfg.recurso}/${b.dataset.editar}`);
    abrirModal({
      titulo: `Editar ${cfg.singular}`, campos: await cfg.campos(true), valores: item,
      aoSalvar: async (d) => { await api("PUT", `${cfg.recurso}/${item.id}`, d); aviso("Alterações salvas."); recarregar(); },
    });
  }));
  document.querySelectorAll("[data-excluir]").forEach((b) => (b.onclick = async () => {
    if (!confirm(`Excluir este ${cfg.singular}?`)) return;
    try { await api("DELETE", `${cfg.recurso}/${b.dataset.excluir}`); aviso("Registro excluído."); recarregar(); }
    catch (e) { aviso(e.message); }
  }));
}

// ------------------------------------------------------------------ Agenda (REQ 07)
async function paginaAgenda(estado = { data: hojeISO(), vet: "" }) {
  const qs = new URLSearchParams({ data: estado.data, ...(estado.vet ? { veterinario_id: estado.vet } : {}) });
  const [consultas, vets] = await Promise.all([api("GET", `/api/consultas?${qs}`), api("GET", "/api/veterinarios?tamanho=100")]);
  const itens = consultas.itens;
  const agendar = pode("consultas:agendar");
  const porVet = {};
  itens.forEach((c) => (porVet[c.veterinario_nome] = (porVet[c.veterinario_nome] || 0) + 1));
  $("#conteudo").innerHTML = `
    <div class="cabecalho-pagina">
      <div><h1>Agenda</h1><div class="sutil">Consultas agendadas para ${dataBR(estado.data)}.</div></div>
      <div class="barra">
        <input type="date" id="data" value="${estado.data}">
        <select id="vet"><option value="">Todos os veterinários</option>${vets.itens.map((v) => `<option value="${v.id}" ${String(v.id) === estado.vet ? "selected" : ""}>${esc(v.nome)}</option>`).join("")}</select>
        ${agendar ? '<button class="btn primario" id="btn-nova">+ Nova consulta</button>' : ""}
      </div>
    </div>
    <div class="agenda-grade">
      <div class="cartao">
        ${itens.length ? itens.map((c) => `<div class="horario">
            <span class="hora">${hora(c.inicio)}</span>
            <div><strong>${esc(c.animal_nome)}</strong><br><span class="sutil pequeno">Tutor: ${esc(c.tutor_nome)}</span></div>
            <div>${esc(c.veterinario_nome)}<br><span class="sutil pequeno">${esc(c.motivo || "—")}</span></div>
            <span class="etiqueta ${c.status === "AGENDADA" ? "laranja" : "cinza"}">${c.status === "AGENDADA" ? "Agendada" : esc(c.status)}</span>
          </div>`).join("") : '<div class="vazio">Nenhuma consulta neste dia.</div>'}
      </div>
      <div class="cartao pad resumo-dia">
        <h2 style="margin-bottom:10px">Resumo do dia</h2>
        <div><span>Total de consultas</span><strong>${itens.length}</strong></div>
        ${Object.entries(porVet).map(([n, q]) => `<div><span class="sutil">${esc(n)}</span><span>${q}</span></div>`).join("")}
        <p class="sutil pequeno" style="margin-top:14px">Visões por semana e por profissional (REQ 09) e cancelamento (REQ 08) entram na próxima sprint.</p>
      </div>
    </div>`;
  const recarregar = (mud) => paginaAgenda({ ...estado, ...mud });
  $("#data").onchange = (e) => recarregar({ data: e.target.value || hojeISO() });
  $("#vet").onchange = (e) => recarregar({ vet: e.target.value });
  if (agendar) $("#btn-nova").onclick = () => novaConsulta(estado.data, vets.itens.filter((v) => v.ativo), (data) => recarregar({ data }));
}

async function novaConsulta(dataInicial, vets, aoConcluir) {
  const animais = (await api("GET", "/api/animais?tamanho=100")).itens;
  let horarioEscolhido = null;
  const form = abrirModal({
    titulo: "Agendar consulta",
    campos: [
      { nome: "animal_id", rotulo: "Animal (tutor)", tipo: "select", obrigatorio: true, inteiro: true,
        opcoes: animais.map((a) => [a.id, `${a.nome} (${ESPECIES[a.especie]}) — tutor: ${a.tutor_nome}`]) },
      { nome: "veterinario_id", rotulo: "Veterinário", tipo: "select", obrigatorio: true, opcoes: vets.map((v) => [v.id, v.nome]) },
      { nome: "data", rotulo: "Data", tipo: "date", obrigatorio: true, padrao: dataInicial },
      { nome: "motivo", rotulo: "Motivo", tipo: "textarea", inteiro: true },
    ],
    extra: '<div><div style="font-weight:600;font-size:13px;margin-bottom:6px">Horários livres</div><div id="slots" class="slots sutil">Escolha o veterinário e a data.</div></div>',
    aoSalvar: async (d) => {
      if (!horarioEscolhido) throw new Error("Escolha um horário livre.");
      await api("POST", "/api/consultas", { animal_id: d.animal_id, veterinario_id: d.veterinario_id, inicio: horarioEscolhido, motivo: d.motivo });
      aviso("Consulta agendada.");
      aoConcluir(d.data);
    },
  });
  const carregarSlots = async () => {
    horarioEscolhido = null;
    const vet = form.elements.veterinario_id.value;
    const data = form.elements.data.value;
    const caixa = $("#slots");
    if (!vet || !data) { caixa.textContent = "Escolha o veterinário e a data."; return; }
    try {
      const r = await api("GET", `/api/agenda/horarios-livres?veterinario_id=${vet}&data=${data}`);
      caixa.innerHTML = r.horarios.length ? r.horarios.map((h) => `<button type="button" class="slot" data-h="${h}">${hora(h)}</button>`).join("") : "Sem horários livres neste dia.";
      caixa.querySelectorAll(".slot").forEach((b) => (b.onclick = () => {
        caixa.querySelectorAll(".slot").forEach((x) => x.classList.remove("sel"));
        b.classList.add("sel");
        horarioEscolhido = b.dataset.h;
      }));
    } catch (e) { caixa.textContent = e.message; }
  };
  form.elements.veterinario_id.onchange = carregarSlots;
  form.elements.data.onchange = carregarSlots;
}

// ------------------------------------------------------------------ Auditoria (somente administrador)
async function paginaAuditoria() {
  const r = await api("GET", "/api/auditoria?limite=100");
  $("#conteudo").innerHTML = `
    <div class="cabecalho-pagina"><div><h1>Auditoria</h1><div class="sutil">Últimos 100 eventos (trilha somente de inserção).</div></div></div>
    <div class="cartao"><table><thead><tr><th>Quando</th><th>Evento</th><th>Usuário</th><th>Dados</th></tr></thead><tbody>
      ${r.itens.map((e) => `<tr><td>${esc(new Date(e.ocorrido_em).toLocaleString("pt-BR"))}</td><td><span class="etiqueta">${esc(e.evento)}</span></td>
        <td>${esc(e.usuario_id ?? "—")}</td><td class="sutil pequeno">${esc(JSON.stringify(e.dados))}</td></tr>`).join("")}
    </tbody></table></div>`;
}

// ------------------------------------------------------------------ início
if (sessao.token) iniciarApp().catch(() => sair(false));
else $("#tela-login").hidden = false;
