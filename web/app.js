const ROTULO_TIPO = {
  artigo_periodico: "Artigo de periódico", preprint: "Preprint", revisao: "Revisão",
  capitulo_livro: "Capítulo de livro", anais_congresso: "Anais de congresso",
  livro: "Livro", tese_dissertacao: "Tese/Dissertação", relatorio: "Relatório",
};
const ROTULO_PDF = {
  nao_baixado: "Sem download", nao_disponivel: "Sem versão aberta", baixando: "Baixando…",
  baixado: "PDF baixado", falha: "Falha no download",
};
const ROTULO_RESUMO = {
  nao_iniciado: "Sem resumo", processando: "Resumindo…", pronto: "Resumo pronto", falha: "Falha no resumo",
};

const $ = (id) => document.getElementById(id);
let categorias = [];

async function api(url, opcoes = {}) {
  const r = await fetch(url, opcoes);
  if (!r.ok) {
    const texto = await r.text();
    throw new Error(texto.slice(0, 200));
  }
  return r.json();
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.hidden = true; }, 3500);
}

function selo(classe, texto) {
  return `<span class="selo ${classe}">${texto}</span>`;
}

function classeStatus(status, okV, erroV, andandoV, vazioV) {
  if (status === okV) return "ok";
  if (status === erroV) return "erro";
  if (status === andandoV) return "andando";
  return "vazio";
}

async function carregarCategorias() {
  try {
    categorias = await api("/api/categorias");
  } catch { categorias = []; }
  const sel = $("filtro-categoria");
  sel.innerHTML = '<option value="">Qualquer categoria</option>' +
    categorias.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s ?? "");
  return div.innerHTML;
}

function autoresHtml(autores, limite = 4) {
  let lista = autores;
  try { lista = typeof autores === "string" ? JSON.parse(autores) : autores; } catch { lista = []; }
  if (!Array.isArray(lista) || !lista.length) return "Autores não informados";
  const visiveis = lista.slice(0, limite);
  const resto = lista.length > limite ? ` et al.` : "";
  return visiveis.join(", ") + resto;
}

function cartaoArtigo(a, emBusca = false) {
  const cat = a.categoria_nome
    ? `<span class="etiqueta-categoria" style="background:${a.categoria_cor || "#4f8cff"}">${esc(a.categoria_nome)}</span>`
    : "";
  const acoesBusca = emBusca ? `
    <button class="botao-mini" onclick="salvarDaBusca(${JSON.stringify(a).replace(/"/g, "&quot;")})">＋ Adicionar à biblioteca</button>
    <button class="botao-mini" data-href="${esc(a.url_pagina || "")}" onclick="abrirLink(this)">🔗 Página</button>` : `
    <button class="botao-mini" onclick="baixarPdf(${a.id})">⭳ ${a.pdf_status === "baixado" ? "Re-baixar" : "Baixar PDF"}</button>
    <button class="botao-mini" onclick="resumir(${a.id})">✨ Resumir</button>
    ${a.pdf_status === "baixado" ? `<button class="botao-mini" onclick="abrirPdf(${a.id})">📄 Abrir PDF</button>` : ""}
    <button class="botao-mini" onclick="abrirDetalhe(${a.id})">Detalhes</button>
    <button class="botao-mini perigo" onclick="excluir(${a.id})">🗑</button>`;
  const statusPdf = a.pdf_status === "baixando" ? selo("andando", ROTULO_PDF[a.pdf_status]) :
    (a.pdf_status === "baixado" ? selo("ok", ROTULO_PDF[a.pdf_status]) :
     (a.pdf_status === "falha" || a.pdf_status === "nao_disponivel" ? selo("erro", ROTULO_PDF[a.pdf_status]) : selo("vazio", ROTULO_PDF[a.pdf_status])));
  const resumoStatus = a.resumo_status === "pronto" ? selo("ok", "Resumo pronto") :
    (a.resumo_status === "processando" ? selo("andando", "Resumindo…") :
     (a.resumo_status === "falha" ? selo("erro", "Falha no resumo") : selo("vazio", "Sem resumo")));
  return `<article class="cartao">
    <div class="meta">${cat}${selo("fonte", a.fonte)}${selo("ano", a.ano || "—")}${selo("tipo", ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "—")}</div>
    <div class="titulo">${esc(a.titulo)}</div>
    <div class="autores">${autoresHtml(a.autores)}</div>
    ${a.classificacao ? `<div class="autores">🧭 ${esc(a.classificacao)}</div>` : ""}
    ${a.resumo ? `<div class="resumo">${esc(a.resumo)}</div>` : ""}
    <div class="meta">${statusPdf}${resumoStatus}</div>
    <div class="acoes">${acoesBusca}</div>
  </article>`;
}

document.querySelectorAll(".aba").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach(x => x.classList.remove("ativa"));
    document.querySelectorAll(".painel").forEach(p => p.classList.remove("ativo"));
    b.classList.add("ativa");
    $("aba-" + b.dataset.aba).classList.add("ativo");
    if (b.dataset.aba === "biblioteca") listarBiblioteca();
    if (b.dataset.aba === "config") carregarConfig();
  });
});

$("botao-buscar").addEventListener("click", buscar);
$("campo-busca").addEventListener("keydown", e => { if (e.key === "Enter") buscar(); });
$("filtro-busca-biblioteca").addEventListener("input", listarBiblioteca);
$("filtro-categoria").addEventListener("change", listarBiblioteca);
$("filtro-tipo").addEventListener("change", listarBiblioteca);
$("filtro-status").addEventListener("change", listarBiblioteca);
$("filtro-resumo").addEventListener("change", listarBiblioteca);
$("limpar-filtros").addEventListener("click", () => {
  ["filtro-categoria", "filtro-tipo", "filtro-status", "filtro-resumo", "filtro-busca-biblioteca"]
    .forEach(id => { $(id).value = ""; });
  listarBiblioteca();
});
$("fechar-modal").addEventListener("click", () => $("modal-detalhe").hidden = true);
$("modal-detalhe").addEventListener("click", e => { if (e.target === $("modal-detalhe")) $("modal-detalhe").hidden = true; });

async function buscar() {
  const q = $("campo-busca").value.trim();
  if (!q) { toast("Digite palavras-chave para buscar"); return; }
  const tipo = $("filtro-tipo-busca").value;
  const params = new URLSearchParams({ q });
  if (tipo) params.set("tipo_origem", tipo);
  if ($("ano-min").value) params.set("ano_min", $("ano-min").value);
  if ($("ano-max").value) params.set("ano_max", $("ano-max").value);
  $("status-busca").textContent = "Buscando...";
  try {
    const resultados = await api("/api/busca?" + params.toString());
    $("status-busca").textContent = `${resultados.length} resultado(s)`;
    const div = $("resultados-busca");
    div.innerHTML = resultados.length
      ? resultados.map(r => cartaoArtigo(r, true)).join("")
      : '<p class="vazio">Nenhum artigo encontrado. Tente outras palavras-chave.</p>';
  } catch (e) {
    $("status-busca").textContent = "Erro na busca: " + e.message;
  }
}

async function salvarDaBusca(r) {
  try {
    await api("/api/artigos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(r),
    });
    toast("Artigo adicionado à biblioteca");
    $("status-busca").textContent = "Adicionado ✓";
  } catch (e) { toast("Erro: " + e.message); }
}

async function listarBiblioteca() {
  const params = new URLSearchParams();
  if ($("filtro-categoria").value) params.set("categoria_id", $("filtro-categoria").value);
  if ($("filtro-tipo").value) params.set("tipo_origem", $("filtro-tipo").value);
  if ($("filtro-status").value) params.set("pdf_status", $("filtro-status").value);
  if ($("filtro-resumo").value) params.set("tem_resumo", $("filtro-resumo").value);
  if ($("filtro-busca-biblioteca").value.trim()) params.set("busca", $("filtro-busca-biblioteca").value.trim());
  try {
    const artigos = await api("/api/artigos?" + params.toString());
    const div = $("lista-biblioteca");
    div.innerHTML = artigos.length
      ? artigos.map(a => cartaoArtigo(a)).join("")
      : '<p class="vazio">Biblioteca vazia. Busque artigos ou importe PDFs.</p>';
  } catch (e) { toast("Erro: " + e.message); }
}

async function baixarPdf(id) {
  try { await api(`/api/artigos/${id}/download`, { method: "POST" }); toast("Download iniciado"); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}

async function resumir(id) {
  try { await api(`/api/artigos/${id}/resumir`, { method: "POST" }); toast("Resumo iniciado"); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}

function abrirPdf(id) { window.open(`/api/artigos/${id}/pdf`, "_blank"); }

async function excluir(id) {
  if (!confirm("Excluir este artigo e o PDF do seu computador?")) return;
  try { await api(`/api/artigos/${id}`, { method: "DELETE" }); listarBiblioteca(); toast("Artigo excluído"); }
  catch (e) { toast("Erro: " + e.message); }
}

async function abrirDetalhe(id) {
  try {
    const a = await api(`/api/artigos/${id}`);
    let resumoHtml = `<p class="nao-id">Nenhum resumo ainda. Clique em "Resumir" no cartão.</p>`;
    if (a.resumo_status === "processando") resumoHtml = `<p class="nao-id">Resumo em andamento...</p>`;
    else if (a.resumo_status === "falha") resumoHtml = `<p class="nao-id">Falha: ${esc(a.resumo_mensagem || "erro desconhecido")}</p>`;
    else if (a.resumo_llm) {
      const campos = JSON.parse(a.resumo_llm);
      const rotulos = { objetivos: "Objetivos", metodologia: "Metodologia", resultados: "Resultados", contribuicoes: "Contribuições", limitacoes: "Limitações" };
      resumoHtml = Object.keys(rotulos).map(k =>
        `<div class="secao-resumo"><h4>${rotulos[k]}</h4><p class="${campos[k] === "Não identificado no texto" ? "nao-id" : ""}">${esc(campos[k])}</p></div>`
      ).join("");
    }
    $("conteudo-detalhe").innerHTML = `
      <h3>${esc(a.titulo)}</h3>
      <div class="meta-linha">${autoresHtml(a.autores)} · ${a.ano || "—"} · ${esc(ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "")} · fonte: ${esc(a.fonte)}</div>
      ${a.classificacao ? `<div class="meta-linha">🧭 ${esc(a.classificacao)}</div>` : ""}
      ${a.doi ? `<div class="meta-linha">DOI: ${esc(a.doi)}</div>` : ""}
      ${a.caminho_pdf ? `<a href="/api/artigos/${a.id}/pdf" target="_blank" class="botao-mini">📄 Abrir PDF</a>` : ""}
      <a href="${esc(a.url_pagina || "#")}" target="_blank" class="botao-mini">🔗 Página do artigo</a>
      <div class="secao-resumo"><h4>Resumo (abstract)</h4><p>${esc(a.resumo || "Não disponível")}</p></div>
      <div class="secao-resumo"><h4>Resumo estruturado</h4>${resumoHtml}</div>
      <div class="secao-resumo"><h4>Organização</h4>
        <p>Classificação: <input id="det-classif" value="${esc(a.classificacao || "")}" style="width:220px"></p>
        <p>${gerenciarCategoria(a)}</p>
        <button class="botao-mini" onclick="salvarDetalhe(${a.id})">Salvar organização</button>
      </div>`;
    $("modal-detalhe").hidden = false;
  } catch (e) { toast("Erro: " + e.message); }
}

function gerenciarCategoria(a) {
  return `Categoria: <select id="det-categoria">
      <option value="">(sem categoria)</option>
      ${categorias.map(c => `<option value="${c.id}" ${c.id === a.categoria_id ? "selected" : ""}>${esc(c.nome)}</option>`).join("")}
    </select>
    <input id="det-nova-categoria" placeholder="ou criar nova..." style="width:180px">`;
}

async function salvarDetalhe(id) {
  const body = { classificacao: $("det-classif").value, categoria_id: $("det-categoria").value || null };
  if ($("det-nova-categoria").value.trim()) body.nova_categoria = $("det-nova-categoria").value.trim();
  try {
    await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await carregarCategorias();
    $("modal-detalhe").hidden = true;
    listarBiblioteca();
    toast("Organização salva");
  } catch (e) { toast("Erro: " + e.message); }
}

const zona = $("zona-drop");
["dragenter", "dragover"].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.add("solto"); }));
["dragleave", "drop"].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.remove("solto"); }));
zona.addEventListener("drop", e => {
  const f = e.dataTransfer.files[0];
  if (f) escolherArquivo(f);
});
zona.addEventListener("click", () => $("arquivo-import").click());
$("arquivo-import").addEventListener("change", e => {
  if (e.target.files[0]) escolherArquivo(e.target.files[0]);
});
function escolherArquivo(f) {
  $("nome-arquivo").textContent = f.name;
  $("imp-titulo").value = f.name.replace(/\.pdf$/i, "").replace(/[_]+/g, " ");
}

$("botao-importar").addEventListener("click", async () => {
  const f = $("arquivo-import").files[0];
  if (!f) { toast("Escolha um PDF primeiro"); return; }
  const form = new FormData();
  form.append("arquivo", f);
  form.append("titulo", $("imp-titulo").value.trim());
  form.append("autores", $("imp-autores").value.trim());
  form.append("ano", $("imp-ano").value);
  form.append("classificacao", $("imp-classificacao").value.trim());
  form.append("categoria", $("imp-categoria").value.trim());
  $("status-importar").textContent = "Importando...";
  try {
    await fetch("/api/importar", { method: "POST", body: form });
    $("status-importar").textContent = "Importado ✓";
    ["imp-titulo", "imp-autores", "imp-ano", "imp-classificacao", "imp-categoria"].forEach(id => $(id).value = "");
    $("nome-arquivo").textContent = "";
    $("arquivo-import").value = "";
  } catch (e) { $("status-importar").textContent = "Erro: " + e.message; }
});

async function carregarConfig() {
  try {
    const c = await api("/api/configuracoes");
    $("cfg-provider").value = c.summary_provider;
    $("cfg-ollama-url").value = c.ollama_base_url;
    $("cfg-ollama-model").value = c.ollama_model;
    $("cfg-abacus-key").value = c.abacus_api_key;
    $("cfg-abacus-url").value = c.abacus_base_url;
    $("cfg-abacus-model").value = c.abacus_model;
    const st = await api("/api/status-ferramentas");
    const ollama = st.ollama_ok
      ? `<span class="ok">✓ Ollama ativo (${st.modelos_ollama.length} modelo(s) local(is))${st.modelo_padrao_baixado ? "" : " — modelo padrão ainda não baixado (será baixado no primeiro resumo)"}</span>`
      : `<span class="erro">✗ Ollama não está rodando. Inicie com "ollama serve" ou abra o aplicativo Ollama.</span>`;
    $("status-ferramentas").innerHTML = ollama +
      `<span>Provedor atual: <b>${c.summary_provider === "abacus" ? "Abacus AI" : "Ollama local"}</b></span>` +
      (c.api_key_definida ? `<span class="ok">✓ Chave Abacus configurada</span>` : `<span>Chave Abacus: não configurada (necessária para usar o provedor Abacus)</span>`);
  } catch (e) { $("status-ferramentas").innerHTML = `<span class="erro">Erro ao carregar: ${esc(e.message)}</span>`; }
}

$("salvar-config").addEventListener("click", async () => {
  const body = {
    summary_provider: $("cfg-provider").value,
    ollama_base_url: $("cfg-ollama-url").value.trim(),
    ollama_model: $("cfg-ollama-model").value,
    abacus_base_url: $("cfg-abacus-url").value.trim(),
    abacus_model: $("cfg-abacus-model").value.trim(),
  };
  if ($("cfg-abacus-key").value) body.abacus_api_key = $("cfg-abacus-key").value.trim();
  try {
    await api("/api/configuracoes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    $("status-config").textContent = "Salvo ✓";
    setTimeout(carregarConfig, 800);
  } catch (e) { $("status-config").textContent = "Erro: " + e.message; }
});

setInterval(async () => {
  const ativo = document.querySelector(".aba.ativa");
  if (ativo && ativo.dataset.aba === "biblioteca") {
    const artigos = await api("/api/artigos").catch(() => null);
    if (artigos && artigos.some(a => a.pdf_status === "baixando" || a.resumo_status === "processando")) {
      listarBiblioteca();
    }
  }
}, 5000);

carregarCategorias();
listarBiblioteca();
