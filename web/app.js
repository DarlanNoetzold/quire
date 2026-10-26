/* ============================================================
   Quire — frontend (busca, biblioteca, leitor, resumos, ajustes)
   ============================================================ */
const ROTULO_TIPO = {
  artigo_periodico: "Journal", preprint: "Preprint", revisao: "Review",
  capitulo_livro: "Chapter", anais_congresso: "Proceedings",
  livro: "Book", tese_dissertacao: "Thesis", relatorio: "Report",
};
const ROTULO_FONTE = {
  openalex: "OpenAlex", arxiv: "arXiv", semanticscholar: "Semantic Scholar",
  pubmed: "PubMed", crossref: "Crossref", doaj: "DOAJ", europepmc: "Europe PMC",
  manual: "Manual", dblp: "dblp", hal: "HAL", zenodo: "Zenodo", openaire: "OpenAIRE",
  plos: "PLOS", openreview: "OpenReview", osf: "OSF", figshare: "Figshare", datacite: "DataCite", huggingface: "Hugging Face",
};
const ROTULO_PDF = {
  nao_baixado: "No PDF", nao_disponivel: "No open version", baixando: "Downloading...",
  baixado: "PDF downloaded", falha: "Download failed",
};
const ROTULO_LEITURA = { nao_lido: "Not read", lendo: "Reading", lido: "Read" };
const ROTULO_CAMPOS = {
  objectives: "Objectives", motivation: "Motivation", methodology: "Methodology",
  results: "Results", contributions: "Contributions", limitations: "Limitations",
  experimental_setup: "Experimental setup",
  novelty: "Novelty", related_work: "Related work", future_work: "Future work",
};
const SUGESTOES_BUSCA = [
  "machine learning", "artificial intelligence", "cybersecurity", "natural language processing",
  "computer vision", "distributed systems", "cryptography", "neural networks", "big data", "robotics",
];

const $ = (id) => document.getElementById(id);
let categorias = [];
let _pessoais = [];
let _idsBase = [];
let _filtrosAtivos = {};
let _leitorAtual = null;
let _totalBiblioteca = 0;
let _detalheAtualId = null;
let _ultimosResultados = [];

/* ---------------- Tema ---------------- */
function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema;
  const bt = $("botao-tema");
  if (bt) bt.textContent = tema === "escuro" ? "☀️" : "🌙";
  localStorage.setItem("tema", tema);
}
(function initTema() {
  const salvo = localStorage.getItem("tema");
  const pref = salvo || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "escuro" : "claro";
  aplicarTema(pref);
})();
$("botao-tema").addEventListener("click", () => {
  aplicarTema(document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro");
});

/* ---------------- Utilidades ---------------- */
function esc(s) {
  const div = document.createElement("div");
  div.textContent = String(s ?? "");
  return div.innerHTML;
}
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.hidden = true; }, 3200);
}
function selo(classe, texto) {
  return `<span class="selo ${classe}">${esc(texto)}</span>`;
}
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
async function api(url, opcoes = {}) {
  const r = await fetch(url, opcoes);
  if (!r.ok) {
    let msg = await r.text();
    try {
      const det = JSON.parse(msg).detail;
      if (typeof det === "string") msg = det;
      else if (det && det.mensagem) msg = det.mensagem;
    } catch { }
    const erro = new Error(msg.slice(0, 200));
    if (r.status === 409) erro.duplicado = true;
    throw erro;
  }
  return r.json();
}
function autoresHtml(autores, limite = 4) {
  let lista = autores;
  try { lista = typeof autores === "string" ? JSON.parse(autores) : autores; } catch { lista = []; }
  if (!Array.isArray(lista) || !lista.length) return "Authors not listed";
  const visiveis = lista.slice(0, limite);
  return visiveis.join(", ") + (lista.length > limite ? " et al." : "");
}
function limparDoi(d) { return String(d || "").replace(/^https?:\/\/doi\.org\//i, "").trim(); }
function copiarDoi(texto) {
  const ok = () => toast("DOI copiado: " + texto);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(texto).then(ok).catch(() => toast("Failed to copy"));
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = texto; document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); ok(); } catch { toast("Failed to copy"); }
  document.body.removeChild(ta);
}
function tagsDe(a) {
  try { return Array.isArray(a.tags) ? a.tags : JSON.parse(a.tags || "[]"); }
  catch { return []; }
}
function pctLeitura(a) {
  if (!a.paginas_total) return null;
  return Math.min(100, Math.round(((a.progresso_leitura || 0) / a.paginas_total) * 100));
}

/* ---------------- Categorias / chips ---------------- */
async function carregarCategorias() {
  try { categorias = await api("/api/categorias"); } catch { categorias = []; }
  $("filtro-categoria").innerHTML = '<option value="">Category (all)</option>' +
    categorias.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
  const selectBib = $("imp-bib-categoria-select");
  if (selectBib) {
    selectBib.innerHTML = '<option value="">Existing category (or choose none)</option>' +
      categorias.map(c => `<option value="${esc(c.nome)}">${esc(c.nome)}</option>`).join("");
  }
}
function chipsRapidos() {
  $("chips-rapidos").innerHTML = SUGESTOES_BUSCA.map(s =>
    `<button class="chip-rapido" onclick="buscarSugestao('${esc(s)}')">${esc(s)}</button>`).join("");
}
function buscarSugestao(s) {
  $("campo-busca").value = s;
  buscar();
}

/* ---------------- Navegação por abas ---------------- */
document.querySelectorAll(".aba").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".aba").forEach(x => x.classList.remove("ativa"));
    document.querySelectorAll(".painel").forEach(p => p.classList.remove("ativo"));
    b.classList.add("ativa");
    $("aba-" + b.dataset.aba).classList.add("ativo");
    if (b.dataset.aba === "biblioteca") listarBiblioteca();
    if (b.dataset.aba === "tendencias") carregarTendencias();
    if (b.dataset.aba === "config") { carregarConfig(); carregarCategoriasAdmin(); }
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});

/* ---------------- Atalhos de teclado ---------------- */
document.addEventListener("keydown", (e) => {
  const emCampo = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
  if (e.key === "/" && !emCampo) {
    e.preventDefault();
    $("campo-busca").focus();
  } else if ((e.key === "b" || e.key === "B") && !emCampo) {
    document.querySelector('.aba[data-aba="biblioteca"]').click();
  } else if (e.key === "s" && !emCampo) {
    document.querySelector('.aba[data-aba="buscar"]').click();
  } else if (e.key === "Escape" && !$("modal-leitor").hidden) {
    fecharLeitor();
  }
});

/* ---------------- Card de artigo ---------------- */
function secaoAcesso(a) {
  const doiLimpo = limparDoi(a.doi);
  if (!doiLimpo && !a.url_pagina) return "";
  const href = doiLimpo ? "https://doi.org/" + encodeURIComponent(doiLimpo) : esc(a.url_pagina);
  const rotulo = doiLimpo || "Open the article page";
  const copia = doiLimpo || a.url_pagina;
  return `<div class="acesso-doi" title="Use the DOI to get the PDF (institutional access, open repositories, etc.)">
    <span class="rotulo-doi">DOI</span>
    <a href="${href}" target="_blank" rel="noopener">${esc(rotulo)}</a>
    <button class="botao-doi" onclick="copiarDoi('${esc(copia)}')" title="Copiar DOI">⧉</button>
  </div>`;
}
function barrinhaProgresso(a) {
  const pct = pctLeitura(a);
  if (pct === null) return "";
  const est = pct >= 100 ? "ok" : pct > 0 ? "andando" : "vazio";
  return `<div class="faixa-progresso" title="Progresso da leitura: ${pct}%"><div class="preenchimento" style="width:${pct}%"></div></div>`;
}
function tagsCard(a) {
  const tags = tagsDe(a).slice(0, 4);
  if (!tags.length) return "";
  return `<div class="tags-cartao">${tags.map(t => `<span class="tag-min" onclick="filtrarPorTag('${esc(t)}')">#${esc(t)}</span>`).join("")}</div>`;
}
function cartaoArtigo(a, emBusca = false) {
  const cat = a.categoria_nome
    ? `<span class="etiqueta-categoria" style="background:${a.categoria_cor || "#4f8cff"}">${esc(a.categoria_nome)}</span>`
    : "";
  const fav = a.favorito ? `<span class="selo ok">★</span>` : "";
  const leitura = selo("vazio", ROTULO_LEITURA[a.read_status] || "Not read");
  const cit = (!emBusca && a.citacoes) ? selo("fonte", `📊 ${a.citacoes} cit.`) : "";
  const idioma = (!emBusca && a.idioma) ? selo("fonte", a.idioma) : "";
  const oa = a.acesso_aberto ? selo("ok", "Open access") : "";
  const statusPdf = a.pdf_status === "baixando" ? selo("andando", ROTULO_PDF[a.pdf_status]) :
    (a.pdf_status === "baixado" ? selo("ok", ROTULO_PDF[a.pdf_status]) :
     (a.pdf_status === "falha" || a.pdf_status === "nao_disponivel" ? selo("erro", ROTULO_PDF[a.pdf_status]) : selo("vazio", ROTULO_PDF[a.pdf_status])));
  const resumoStatus = a.resumo_status === "pronto" ? selo("ok", "Summary ready") :
    (a.resumo_status === "processando" ? selo("andando", "Summarizing...") :
     (a.resumo_status === "falha" ? `<span class="selo erro" title="Failed: ${esc(a.resumo_mensagem || "unknown error")}">Failed summary</span>` : selo("vazio", "No summary")));

  const acoesBusca = emBusca ? `
    <button class="botao-mini" onclick="salvarDaBusca(${JSON.stringify(a).replace(/"/g, "&quot;")})">＋ Add</button>
    <button class="botao-mini" data-href="${esc(a.url_pagina || "")}" onclick="abrirLink(this)">Page</button>` : `
    <button class="botao-mini" onclick="baixarPdf(${a.id})">⭳ ${a.pdf_status === "baixado" ? "Download again" : "Download PDF"}</button>
    ${["falha", "nao_disponivel", "nao_baixado"].includes(a.pdf_status) ? `<button class="botao-mini" onclick="anexarPdf(${a.id})">📎 Attach</button>` : ""}
    <button class="botao-mini" onclick="resumir(${a.id})">✨ Resumir</button>
    ${a.pdf_status === "baixado" ? `<button class="botao-mini" onclick="abrirLeitor(${a.id})">📖 Read</button>` : ""}
    <button class="botao-mini" onclick="toggleFavorito(${a.id})">${a.favorito ? "★" : "☆"}</button>
    <select class="botao-mini" onchange="mudarLeitura(${a.id}, this.value)">
      <option value="nao_lido" ${a.read_status === "nao_lido" ? "selected" : ""}>Not read</option>
      <option value="lendo" ${a.read_status === "lendo" ? "selected" : ""}>Reading</option>
      <option value="lido" ${a.read_status === "lido" ? "selected" : ""}>Read</option>
    </select>
    <button class="botao-mini" onclick="abrirDetalhe(${a.id})">Details</button>
    <button class="botao-mini perigo" onclick="excluir(${a.id})" title="Delete article and PDF">🗑</button>`;
  return `<article class="cartao">
    <div class="meta">${cat}${selo("fonte", ROTULO_FONTE[a.fonte] || a.fonte)}${selo("ano", a.ano || "—")}${selo("tipo", ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "—")}${oa}${fav}${leitura}${cit}${idioma}</div>
    <div class="titulo">${esc(a.titulo)}</div>
    <div class="autores">${autoresHtml(a.autores)}</div>
    ${a.classificacao ? `<div class="autores">${esc(a.classificacao)}</div>` : ""}
    ${a.resumo ? `<div class="resumo">${esc(a.resumo)}</div>` : ""}
    ${(!emBusca && a.pdf_status === "baixado") ? barrinhaProgresso(a) : ""}
    ${tagsCard(a)}
    <div class="meta">${statusPdf}${resumoStatus}</div>
    ${(!emBusca && !["baixado", "baixando"].includes(a.pdf_status)) ? secaoAcesso(a) : ""}
    <div class="acoes">${acoesBusca}</div>
  </article>`;
}

/* ---------------- Busca ---------------- */
$("botao-buscar").addEventListener("click", buscar);
$("campo-busca").addEventListener("keydown", e => { if (e.key === "Enter") buscar(); });
["filtro-tipo-busca", "filtro-idioma-busca", "filtro-ord-busca", "deduplicar-busca"].forEach(id => $(id).addEventListener("change", buscar));
$("filtro-oa-busca").addEventListener("change", buscar);
$("ano-min").addEventListener("change", buscar);
$("ano-max").addEventListener("change", buscar);
["autor-busca", "assunto-busca", "citacoes-min-busca"].forEach(id => $(id).addEventListener("keydown", e => { if (e.key === "Enter") buscar(); }));
["autor-busca", "assunto-busca", "citacoes-min-busca"].forEach(id => $(id).addEventListener("change", buscar));
$("regex-busca").addEventListener("keydown", e => {
  if (e.key === "Enter") {
    if (!_ultimosResultados.length) buscar();
    else aplicarRegexBusca();
  }
});
$("regex-busca").addEventListener("change", aplicarRegexBusca);
$("regex-busca").addEventListener("input", debounce(aplicarRegexBusca, 250));
$("regex-ci").addEventListener("change", aplicarRegexBusca);

function regexAtual() {
  const texto = $("regex-busca").value.trim();
  if (!texto) return null;
  try {
    return new RegExp(texto, $("regex-ci").checked ? "im" : "m");
  } catch (e) {
    return e;
  }
}
function camposBuscaRegex(r) {
  let autores = r.autores;
  try { autores = typeof autores === "string" ? JSON.parse(autores).join(" ") : (autores || []).join(" "); } catch { autores = ""; }
  return [r.titulo, r.resumo, autores, r.classificacao, r.doi].filter(Boolean).join("\n");
}
function aplicarRegexBusca(tempo = null) {
  const re = regexAtual();
  const bruto = _ultimosResultados || [];
  const linha = $("regex-linha");
  const statusRegex = $("regex-status");
  const reValido = re && !(re instanceof Error);
  if (re instanceof Error) {
    linha.classList.add("erro");
    statusRegex.textContent = "Invalid regex — filter ignored";
    statusRegex.className = "regex-status invalido";
  } else {
    linha.classList.remove("erro");
    statusRegex.textContent = "";
    statusRegex.className = "regex-status";
  }
  const filtrados = bruto.filter(r => reValido ? re.test(camposBuscaRegex(r)) : true);
  const tempoStr = tempo !== null ? ` in ${tempo.toFixed(1)}s` : "";
  $("status-busca").textContent = `${filtrados.length} result(s)${reValido && bruto.length ? ` (${filtrados.length} of ${bruto.length} match the regex)` : ""}${tempoStr}`;
  const vazio = reValido && bruto.length && !filtrados.length
    ? '<p class="vazio">No result matches the regex. Check the pattern or clear the filter.</p>'
    : '<p class="vazio">No articles found. Try different keywords or loosen the filters.</p>';
  const div = $("resultados-busca");
  div.innerHTML = filtrados.length
    ? filtrados.map(r => cartaoArtigo(r, true)).join("")
    : vazio;
}

async function buscar() {
  const q = $("campo-busca").value.trim();
  if (!q) { toast("Type keywords to search"); $("campo-busca").focus(); return; }
  const params = new URLSearchParams({ q });
  if ($("filtro-tipo-busca").value) params.set("tipo_origem", $("filtro-tipo-busca").value);
  if ($("ano-min").value) params.set("ano_min", $("ano-min").value);
  if ($("ano-max").value) params.set("ano_max", $("ano-max").value);
  if ($("autor-busca").value.trim()) params.set("autor", $("autor-busca").value.trim());
  if ($("assunto-busca").value.trim()) params.set("assunto", $("assunto-busca").value.trim());
  if ($("citacoes-min-busca").value) params.set("citacoes_min", $("citacoes-min-busca").value);
  params.set("deduplicar", $("deduplicar-busca").checked ? "1" : "0");
  const fontes = [...$("filtro-fonte-busca").selectedOptions].map(o => o.value);
  if (fontes.length) params.set("fontes", fontes.join(","));
  if ($("filtro-idioma-busca").value) params.set("idioma", $("filtro-idioma-busca").value);
  if ($("filtro-oa-busca").checked) params.set("acesso_aberto", "1");
  if ($("filtro-ord-busca").value) params.set("ordenacao", $("filtro-ord-busca").value);
  $("status-busca").textContent = "Searching...";
  const botao = $("botao-buscar");
  botao.disabled = true;
  try {
    const t0 = Date.now();
    const resultados = await api("/api/busca?" + params.toString());
    _ultimosResultados = resultados;
    aplicarRegexBusca((Date.now() - t0) / 1000);
  } catch (e) {
    $("status-busca").textContent = "Search error: " + e.message;
  } finally {
    botao.disabled = false;
  }
}

/* ---------------- Libreria: filtros ---------------- */
["filtro-categoria", "filtro-tipo", "filtro-status", "filtro-resumo", "filtro-fonte", "filtro-leitura", "filtro-favoritos", "filtro-idioma", "filtro-adicionado", "filtro-ordenacao", "filtro-tag"]
  .forEach(id => $(id).addEventListener("change", listarBiblioteca));
["filtro-busca-biblioteca", "filtro-ano-min", "filtro-ano-max", "filtro-citacoes", "filtro-autor"]
  .forEach(id => $(id).addEventListener("input", debounce(listarBiblioteca, 350)));

$("limpar-filtros").addEventListener("click", () => {
  ["filtro-categoria", "filtro-tipo", "filtro-status", "filtro-resumo", "filtro-fonte", "filtro-leitura", "filtro-favoritos", "filtro-idioma", "filtro-adicionado", "filtro-ordenacao", "filtro-tag"]
    .forEach(id => { $(id).value = ""; });
  ["filtro-busca-biblioteca", "filtro-ano-min", "filtro-ano-max", "filtro-citacoes", "filtro-autor"].forEach(id => { $(id).value = ""; });
  _filtrosAtivos = {};
  listarBiblioteca();
  atualizarFiltrosAtivos();
});
function filtrarPorTag(t) {
  $("filtro-tag").value = t;
  listarBiblioteca();
}
function atualizarFiltrosAtivos() {
  const mapa = { "filtro-tag": "tag", "filtro-leitura": "leitura", "filtro-favoritos": "favoritos", "filtro-status": "pdf" };
  const chips = Object.entries(mapa).map(([idE, rotulo]) => {
    const v = $(idE).value;
    if (!v) return "";
    const nome = $(idE).selectedOptions[0] ? $(idE).selectedOptions[0].text : v;
    return `<span class="filtro-ativo">${esc(rotulo)}: ${esc(nome)} <button onclick="document.getElementById('${idE}').value='';atualizarFiltrosAtivos();listarBiblioteca();">✕</button></span>`;
  }).join("");
  $("filtros-ativos").innerHTML = chips;
}

async function listarBiblioteca() {
  const params = new URLSearchParams();
  const mapear = (id, nome, limpo = "") => { if ($(id).value && $(id).value !== limpo) params.set(nome, $(id).value); };
  mapear("filtro-categoria", "categoria_id");
  mapear("filtro-tipo", "tipo_origem");
  mapear("filtro-status", "pdf_status");
  mapear("filtro-resumo", "tem_resumo");
  mapear("filtro-fonte", "fonte");
  mapear("filtro-leitura", "read_status");
  if ($("filtro-favoritos").value === "sim") params.set("favorito", "sim");
  mapear("filtro-idioma", "idioma");
  mapear("filtro-citacoes", "citacoes_min");
  mapear("filtro-adicionado", "adicionado");
  mapear("filtro-autor", "autor");
  mapear("filtro-ano-min", "ano_min");
  mapear("filtro-ano-max", "ano_max");
  mapear("filtro-ordenacao", "ordenacao");
  mapear("filtro-tag", "tag");
  if ($("filtro-busca-biblioteca").value.trim()) params.set("busca", $("filtro-busca-biblioteca").value.trim());
  atualizarFiltrosAtivos();
  try {
    const artigos = await api("/api/artigos?" + params.toString());
    _totalBiblioteca = artigos.length;
    const div = $("lista-biblioteca");
    div.innerHTML = artigos.length
      ? artigos.map(a => cartaoArtigo(a)).join("")
      : '<p class="vazio">The library is empty. Search for articles, import PDFs or change the filters.</p>';
    $("status-biblioteca").textContent = artigos.length + " article(s)";
    carregarStats();
  } catch (e) { toast("Erro: " + e.message); }
}

/* ---------------- Ações de artigo ---------------- */
async function baixarPdf(id) {
  try { await api(`/api/artigos/${id}/download`, { method: "POST" }); toast("Download started"); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}
async function resumir(id) {
  const a = await api(`/api/artigos/${id}`).catch(() => null);
  if (a && a.pdf_status !== "baixado") { toast("Download the PDF first."); return; }
  try { await api(`/api/artigos/${id}/resumir`, { method: "POST" }); toast("Summary started ✨"); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}
function anexarPdf(id) {
  const inp = $("input-anexar-pdf");
  inp.dataset.artigoId = id;
  inp.value = "";
  inp.click();
}
$("input-anexar-pdf").addEventListener("change", async () => {
  const inp = $("input-anexar-pdf");
  const id = inp.dataset.artigoId;
  const arquivo = inp.files && inp.files[0];
  if (!id || !arquivo) return;
  const fd = new FormData();
  fd.append("arquivo", arquivo);
  try {
    const a = await api(`/api/artigos/${id}/pdf`, { method: "POST", body: fd });
    toast(a.resumo_status === "processando" ? "PDF attached — summary started" : "PDF attached");
    listarBiblioteca();
  } catch (e) { toast("Erro: " + e.message); }
});
async function toggleFavorito(id) {
  try {
    const a = await api(`/api/artigos/${id}`);
    await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ favorito: a.favorito ? 0 : 1 }) });
    listarBiblioteca();
  } catch (e) { toast("Erro: " + e.message); }
}
async function mudarLeitura(id, valor) {
  try { await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ read_status: valor }) }); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}
function abrirLink(el) { const href = el.dataset.href; if (href) window.open(href, "_blank"); }
async function excluir(id) {
  if (!confirm("Delete this article and its PDF from your computer?")) return;
  try { await api(`/api/artigos/${id}`, { method: "DELETE" }); listarBiblioteca(); toast("Article deleted"); }
  catch (e) { toast("Erro: " + e.message); }
}

/* ---------------- Save da busca ---------------- */
async function salvarDaBusca(r) {
  try {
    await api("/api/artigos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(r) });
    toast("Article added to the library");
    $("status-busca").textContent = "Added ✓";
  } catch (e) {
    if (e.duplicado) { toast("Already in the library"); $("status-busca").textContent = "Already in the library ✓"; }
    else toast("Erro: " + e.message);
  }
}

/* ---------------- Resumir todos ---------------- */
$("btn-resumir-todos").addEventListener("click", async () => {
  if (!confirm("Generate summaries for articles with a PDF that don't have one yet? This may take a while.")) return;
  try {
    const r = await api("/api/resumir-todos", { method: "POST" });
    toast(`Summaries scheduled for ${r.agendados} of ${r.total} article(s)`);
  } catch (e) { toast("Erro: " + e.message); }
});

/* ---------------- Exportar ---------------- */
$("exportar-bibtex").addEventListener("click", () => window.open("/api/export?formato=bibtex", "_blank"));
$("exportar-json").addEventListener("click", () => window.open("/api/export?formato=json", "_blank"));
$("exportar-markdown").addEventListener("click", () => window.open("/api/export?formato=markdown", "_blank"));
$("exportar-backup").addEventListener("click", () => window.open("/api/backup", "_blank"));

/* ---------------- Stats e Dashboard ---------------- */
async function carregarStats() {
  try {
    const s = await api("/api/stats");
    const chip = (rotulo, valor, titulo = "") => `<span class="chip-stats" ${titulo ? `title="${esc(titulo)}"` : ""}><b>${valor}</b> ${esc(rotulo)}</span>`.replace('title=""', "");
    $("faixa-stats").innerHTML = s.total
      ? chip("articles", s.total) + chip("with PDF", s.com_pdf) + chip("summarized", s.com_resumo) +
        chip("favorites", s.favoritos) + chip("not read", s.nao_lidos) + chip("citations", s.citacoes_total)
      : "";
  } catch { }
}
function dashBarra(nome, valor, fator) {
  const largura = Math.round(Math.min(100, (valor / Math.max(1, fator)) * 100));
  return `<div class="barra-h"><span>${esc(nome)}</span><div class="barra-pista"><div class="barra-cheia" style="width:${largura}%"></div></div><span class="barra-valor">${valor}</span></div>`;
}
$("btn-dashboard").addEventListener("click", async (e) => {
  const painel = $("painel-dashboard");
  if (!painel.hidden) { painel.hidden = true; return; }
  painel.hidden = false;
  painel.innerHTML = '<p class="nao-id">Loading statistics...</p>';
  try {
    const d = await api("/api/dashboard");
    const anos = Object.entries(d.por_ano || {}).sort((a, b) => a[0] - b[0]);
    const anosMax = Math.max(1, ...anos.map(([, v]) => v));
    const fontes = Object.entries(d.por_fonte || {}).slice(0, 8);
    const fontesMax = Math.max(1, ...fontes.map(([, v]) => v));
    const totFonte = (d.por_fonte) ? Object.values(d.por_fonte).reduce((a, b) => a + b, 0) : 0;
    const leit = { "nao_lido": "Not read", "lendo": "In progress", "lido": "Read" };
    painel.innerHTML = `
      <div class="dash-bloco"><h4>Articles by year</h4>
        ${anos.length ? anos.map(([a, v]) => dashBarra(a, v, anosMax)).join("") : '<p class="nao-id">No data.</p>'}
        <div class="dash-total">${_totalBiblioteca} article(s) in total</div>
      </div>
      <div class="dash-bloco"><h4>Distribution by source</h4>
        ${fontes.length ? fontes.map(([f, v]) => dashBarra(ROTULO_FONTE[f] || f, v, fontesMax)).join("") : '<p class="nao-id">No data.</p>'}
        <div class="dash-total">${totFonte} article(s)</div>
      </div>
      <div class="dash-bloco"><h4>Reading status</h4>
        ${Object.entries(leit).map(([k, n]) => `<div class="dash-total"><b>${d.por_leitura?.[k] || 0}</b> ${n}</div>`).join("")}
        <div class="dash-total" style="margin-top:8px">📖 ${d.paginas_lidas} page(s) read across ${d.sendo_lidos} article(s) in progress</div>
      </div>`;
  } catch (e) { painel.innerHTML = '<p class="nao-id">Error: ' + esc(e.message) + "</p>"; }
});

/* ---------------- Tags (filtro) ---------------- */
async function carregarTags() {
  try {
    const tags = await api("/api/tags");
    $("filtro-tag").innerHTML = '<option value="">Tag (todas)</option>' +
      tags.map(t => `<option value="${esc(t.tag)}">#${esc(t.tag)} (${t.quantidade})</option>`).join("");
  } catch { }
}

/* ---------------- Tendeências ---------------- */
async function carregarTendencias() {
  const dias = $("sel-periodo").value;
  $("status-tendencias").textContent = "";
  try {
    const d = await api(`/api/destaques?dias=${dias}`);
    const diarios = d.diarios || [];
    $("hf-lista").innerHTML = diarios.length ? diarios.map(r => cartaoArtigo(r, true)).join("") : "";
    $("botao-tendencias").textContent = "Refresh";
    $("hf-titulo").hidden = !diarios.length;
    $("hf-dica").hidden = !diarios.length;
    $("destaques-lista").innerHTML = d.destaques.length
      ? d.destaques.map(r => cartaoArtigo(r, true)).join("")
      : '<p class="vazio">No recent highlights for your area in this period. Try a longer period or review your area in Settings.</p>';
    $("aviso-area-tendencias").textContent = "Based on your research area (configured in Settings).";
    $("topicos-lista").innerHTML = d.topicos.length
      ? d.topicos.map(t => `<button class="chip" onclick="buscarTema('${esc(t.termo).replace(/'/g, "\\'")}')" title="${esc((t.exemplos || []).join(" · "))}">${esc(t.termo)} — ${t.trabalhos} paper(s), ${t.citacoes} cit.</button>`).join("")
      : '<p class="nao-id">No topics detected in this period.</p>';
    $("dica-topicos").hidden = !d.topicos.length;
  } catch (e) {
    $("destaques-lista").innerHTML = '<p class="vazio">Could not load the highlights.</p>';
  }
}
function buscarTema(termo) {
  $("campo-busca").value = termo;
  document.querySelector('.aba[data-aba="buscar"]').click();
  buscar();
}
$("botao-tendencias").addEventListener("click", carregarTendencias);
$("sel-periodo").addEventListener("change", carregarTendencias);

/* ---------------- Importar ---------------- */
const zonaBib = $("zona-drop-bib");
if (zonaBib) {
  ["dragenter", "dragover"].forEach(ev => zonaBib.addEventListener(ev, e => { e.preventDefault(); zonaBib.classList.add("solto"); }));
  ["dragleave", "drop"].forEach(ev => zonaBib.addEventListener(ev, e => { e.preventDefault(); zonaBib.classList.remove("solto"); }));
  zonaBib.addEventListener("drop", e => {
    const f = e.dataTransfer.files[0];
    if (f) escolherArquivoBib(f);
  });
  zonaBib.addEventListener("click", () => $("arquivo-import-bib").click());
  $("arquivo-import-bib").addEventListener("change", e => { if (e.target.files[0]) escolherArquivoBib(e.target.files[0]); });
}
function escolherArquivoBib(f) {
  $("nome-arquivo-bib").textContent = f.name;
}
if ($("botao-importar-bib")) {
  $("botao-importar-bib").addEventListener("click", async () => {
    const f = $("arquivo-import-bib").files[0];
    if (!f) { toast("Choose a .bib or .ris file first"); return; }
    const catSel = $("imp-bib-categoria-select").value.trim();
    const catNova = $("imp-bib-categoria-nova").value.trim();
    const categoriaEscolhida = catNova || catSel;
    const baixarPdfs = $("imp-bib-baixar-pdfs").checked;

    const form = new FormData();
    form.append("arquivo", f);
    form.append("categoria", categoriaEscolhida);
    form.append("baixar_pdfs", baixarPdfs);

    $("status-importar-bib").textContent = "Importing & processing bibliography...";
    try {
      const r = await fetch("/api/importar/bibliografia", { method: "POST", body: form });
      const res = await r.json();
      if (!r.ok) {
        $("status-importar-bib").textContent = "Error: " + (res.detail || "Failed to import");
        return;
      }
      $("status-importar-bib").textContent = `✓ ${res.mensagem}`;
      toast(`Imported: +${res.adicionados} new, ${res.duplicados} skipped`);
      $("nome-arquivo-bib").textContent = "";
      $("arquivo-import-bib").value = "";
      $("imp-bib-categoria-nova").value = "";
      await carregarCategorias();
    } catch (e) {
      $("status-importar-bib").textContent = "Error: " + e.message;
    }
  });
}

const zona = $("zona-drop");
["dragenter", "dragover"].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.add("solto"); }));
["dragleave", "drop"].forEach(ev => zona.addEventListener(ev, e => { e.preventDefault(); zona.classList.remove("solto"); }));
zona.addEventListener("drop", e => {
  const f = e.dataTransfer.files[0];
  if (f) escolherArquivo(f);
});
zona.addEventListener("click", () => $("arquivo-import").click());
$("arquivo-import").addEventListener("change", e => { if (e.target.files[0]) escolherArquivo(e.target.files[0]); });
function escolherArquivo(f) {
  $("nome-arquivo").textContent = f.name;
  if (!$("imp-titulo").value.trim()) $("imp-titulo").value = f.name.replace(/\.pdf$/i, "").replace(/[_]+/g, " ");
}
$("botao-importar").addEventListener("click", async () => {
  const f = $("arquivo-import").files[0];
  if (!f) { toast("Choose a PDF first"); return; }
  const form = new FormData();
  form.append("arquivo", f);
  form.append("titulo", $("imp-titulo").value.trim());
  form.append("autores", $("imp-autores").value.trim());
  form.append("ano", $("imp-ano").value);
  form.append("classificacao", $("imp-classificacao").value.trim());
  form.append("categoria", $("imp-categoria").value.trim());
  $("status-importar").textContent = "Importing...";
  try {
    const r = await fetch("/api/importar", { method: "POST", body: form });
    if (!r.ok) {
      let msg = await r.text();
      try { const det = JSON.parse(msg).detail; msg = typeof det === "string" ? det : (det && det.mensagem) || msg; } catch { }
      $("status-importar").textContent = r.status === 409 ? "Already in the library" : "Error: " + msg.slice(0, 120);
      return;
    }
    $("status-importar").textContent = "Imported ✓";
    ["imp-titulo", "imp-autores", "imp-ano", "imp-classificacao", "imp-categoria"].forEach(id => $(id).value = "");
    $("nome-arquivo").textContent = "";
    $("arquivo-import").value = "";
  } catch (e) { $("status-importar").textContent = "Error: " + e.message; }
});

/* ---------------- Modal de detalhes ---------------- */
$("fechar-modal").addEventListener("click", () => $("modal-detalhe").hidden = true);
$("modal-detalhe").addEventListener("click", e => { if (e.target === $("modal-detalhe")) $("modal-detalhe").hidden = true; });

async function abrirDetalhe(id) {
  _detalheAtualId = id;
  try {
    const a = await api(`/api/artigos/${id}`);
    let resumoHtml = '<p class="nao-id">No summary yet. Click Summarize.</p>';
    if (a.resumo_status === "processando") resumoHtml = '<p class="nao-id">Summary in progress...</p>';
    else if (a.resumo_status === "falha") resumoHtml = `<p class="nao-id">Failed: ${esc(a.resumo_mensagem || "unknown error")}</p>`;
    else if (a.resumo_llm) {
      const campos = JSON.parse(a.resumo_llm);
      const mapaPt = { objetivos: "objectives", metodologia: "methodology", motivacao: "motivation", resultados: "results", contribuicoes: "contributions", limitacoes: "limitations", novidade: "novelty", trabalhos_relacionados: "related_work", trabalhos_futuros: "future_work" };
      resumoHtml = Object.entries(campos).map(([chave, valor]) => {
        const idEn = mapaPt[chave] || Object.keys(mapaPt).find(k => mapaPt[k] === chave) || chave;
        const rotulo = ROTULO_CAMPOS[idEn] || ((_pessoais.find(p => p.id === idEn) || {}).rotulo) || (idEn.charAt(0).toUpperCase() + idEn.slice(1).replace(/_/g, " "));
        return `<div class="secao-resumo"><h4>${esc(rotulo)}</h4><p class="${valor === "Not identified in the text" || valor === "Não identificado no texto" ? "nao-id" : ""}">${esc(valor)}</p></div>`;
      }).join("") || '<p class="nao-id">No summary yet.</p>';
    }
    const tags = tagsDe(a);
    $("conteudo-detalhe").innerHTML = `
      <h3>${esc(a.titulo)}</h3>
      <div class="meta-linha">${autoresHtml(a.autores)} · ${a.ano || "—"} · ${esc(ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "")} · source: ${esc(ROTULO_FONTE[a.fonte] || a.fonte)}${a.acesso_aberto ? " · Open access" : ""}</div>
      ${a.classificacao ? `<div class="meta-linha">${esc(a.classificacao)}</div>` : ""}
      ${a.doi ? `<div class="meta-linha"><b>DOI:</b> <a href="https://doi.org/${encodeURIComponent(limparDoi(a.doi))}" target="_blank" rel="noopener">${esc(limparDoi(a.doi))}</a></div>` : ""}
      <div class="acoes-detalhe">
        ${a.caminho_pdf ? `<button class="botao-mini" onclick="abrirLeitor(${a.id})">Open reader</button>` : ""}
        <button class="botao-mini" onclick="window.open('/api/artigos/${a.id}/markdown','_blank')">⬇ Markdown</button>
        <a href="${esc(a.url_pagina || "#")}" target="_blank" class="botao-mini">Article page</a>
      </div>
      <div class="secao-resumo"><h4>Abstract</h4><p>${esc(a.resumo || "Not available")}</p></div>
      <div class="secao-resumo"><h4>Structured summary</h4>${resumoHtml}</div>
      <div class="secao-resumo"><h4>Metrics</h4><div id="det-metricas"><button class="botao-mini" onclick="metricasArtigo(${a.id})">📊 Get metrics (citations, trends)</button></div></div>
      <div class="secao-resumo"><h4>Notes</h4>
        <textarea id="det-notas" class="textarea-notas" placeholder="Your notes about this article...">${esc(a.notas || "")}</textarea>
      </div>
      <div class="secao-resumo"><h4>Tags</h4>
        <div class="editor-tags">
          <input id="det-nova-tag" type="text" placeholder="Type a tag and press Enter" list="todas-tags" ${tags.length ? '' : ''}>
          <datalist id="todas-tags"></datalist>
          <div id="det-tags-lista" class="editor-tags"></div>
        </div>
      </div>
      <div class="secao-resumo"><h4>Organization</h4>
        <div class="form-grid" style="margin-top:6px">
          <label>Classification <input id="det-classif" value="${esc(a.classificacao || "")}"></label>
          <label>Category ${gerenciarCategoria(a)}</label>
        </div>
        <div class="options-celula">
          <label class="check-inline">Reading
            <select id="det-leitura">
              <option value="nao_lido" ${a.read_status === "nao_lido" ? "selected" : ""}>Not read</option>
              <option value="lendo" ${a.read_status === "lendo" ? "selected" : ""}>In progress</option>
              <option value="lido" ${a.read_status === "lido" ? "selected" : ""}>Read</option>
            </select>
          </label>
          <label class="check-inline"><input type="checkbox" id="det-favorito" ${a.favorito ? "checked" : ""}> ★ Favorite</label>
        </div>
        <div style="margin-top:12px"><button class="botao-mini" onclick="salvarDetalhe(${a.id})">💾 Save</button> <button class="botao-mini" onclick="exportarDetalheMarkdown(${a.id})">⬇ Export .md</button></div>
      </div>`;
    const dl = $("todas-tags");
    try {
      const tagsAll = await api("/api/tags");
      dl.innerHTML = tagsAll.map(t => `<option value="${esc(t.tag)}">`).join("");
    } catch { }
    renderDetTags(tags);
    $("modal-detalhe").hidden = false;
    $("det-nova-tag").addEventListener("keydown", async (e) => {
      if (e.key === "Enter") { e.preventDefault(); await addDetTag(); }
    });
  } catch (e) { toast("Erro: " + e.message); }
}
async function addDetTag() {
  const inp = $("det-nova-tag");
  const v = inp.value.trim();
  if (!v) return;
  const atuais = [...$("det-tags-lista").querySelectorAll(".tag-min")].map(x => x.textContent.replace(/^#/, "").replace(/\s*✕/, "").trim());
  if (atuais.some(t => t.toLowerCase() === v.toLowerCase())) { inp.value = ""; toast("Tag already exists"); return; }
  const novo = [...atuais, v];
  renderDetTags(novo);
  await apiSaveTags(novo);
  inp.value = "";
}
function renderDetTags(tags) {
  $("det-tags-lista").innerHTML = tags.map(t => `<span class="tag-min" onclick="removerDetTag(this)" title="Clique para remover">#${esc(t)} ✕</span>`).join("");
}
async function removerDetTag(el) {
  const alvo = el.textContent.replace(/^#/, "").replace(/\s*✕/, "").trim();
  const atuais = [...$("det-tags-lista").querySelectorAll(".tag-min")].map(x => x.textContent.replace(/^#/, "").replace(/\s*✕/, "").trim());
  await apiSaveTags(atuais.filter(t => t.toLowerCase() !== alvo.toLowerCase()));
}
async function apiSaveTags(tags) {
  if (!_detalheAtualId) return;
  try { await api(`/api/artigos/${_detalheAtualId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tags: tags }) }); carregarTags(); listarBiblioteca(); }
  catch (e) { toast("Erro: " + e.message); }
}
function exportarDetalheMarkdown(id) { window.open(`/api/artigos/${id}/markdown`, "_blank"); }
function gerenciarCategoria(a) {
  return `<div style="display:flex;gap:6px;align-items:center;margin-top:3px">
    <select id="det-categoria">
      <option value="">(no category)</option>
      ${categorias.map(c => `<option value="${c.id}" ${c.id === a.categoria_id ? "selected" : ""}>${esc(c.nome)}</option>`).join("")}
    </select>
    <input id="det-nova-categoria" placeholder="ou criar nova..." style="width:160px">
  </div>`;
}
async function salvarDetalhe(id) {
  const body = { classificacao: $("det-classif").value, categoria_id: $("det-categoria").value || null };
  if ($("det-nova-categoria").value.trim()) body.nova_categoria = $("det-nova-categoria").value.trim();
  if ($("det-leitura")) body.read_status = $("det-leitura").value;
  if ($("det-favorito")) body.favorito = $("det-favorito").checked ? 1 : 0;
  const notas = $("det-notas") ? $("det-notas").value : "";
  body.notas = notas;
  const tags = [...$("det-tags-lista").querySelectorAll(".tag-min")].map(x => x.textContent.replace(/#/g, "").replace(" ✕", ""));
  body.tags = tags;
  try {
    await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await carregarCategorias();
    $("modal-detalhe").hidden = true;
    listarBiblioteca();
    carregarTags();
    toast("Saved");
  } catch (e) { toast("Erro: " + e.message); }
}

async function metricasArtigo(id) {
  const alvo = $("det-metricas");
  alvo.innerHTML = '<span class="nao-id">Loading metrics...</span>';
  try {
    const m = await api(`/api/artigos/${id}/metricas`);
    if (!m.encontrado) { alvo.innerHTML = '<p class="nao-id">No metrics available (no DOI and the title was not found in OpenAlex under this spelling).</p>'; return; }
    const p_anos = m.por_ano || [];
    const max = Math.max(1, ...p_anos.map(p => p.citacoes || 0));
    const barras = p_anos.slice(-6).map(p => {
      const largura = Math.round(((p.citacoes || 0) / max) * 100);
      return `<div class="barra-h"><span class="barra-ano">${p.ano}</span><div class="barra-pista"><div class="barra-cheia" style="width:${largura}%"></div></div><span class="barra-valor">${p.citacoes}</span></div>`;
    }).join("") || '<p class="nao-id">No yearly citation data.</p>';
    alvo.innerHTML = `
      <div class="dash-total"><b>${m.citacoes}</b> citations · <b>${m.referencias}</b> references${m.acesso_aberto ? " · Open access" : ""}</div>
      ${m.conceitos && m.conceitos.length ? `<div class="linha-metrica" style="margin:8px 0">${m.conceitos.map(c => `<span class="selo fonte">${esc(c)}</span>`).join("")}</div>` : ""}
      ${barras}
      ${m.doi ? `<div class="meta-linha">DOI: <a href="https://doi.org/${m.doi}" target="_blank" rel="noopener">${m.doi}</a></div>` : ""}`;
  } catch (e) { alvo.innerHTML = '<p class="nao-id">Error: ' + esc(e.message) + "</p>"; }
}

/* ---------------- Leitor de PDF ---------------- */
function abrirLeitor(id) {
  $("modal-leitor").hidden = false;
  $("leitor-iframe").src = `/api/artigos/${id}/pdf`;
  const titulo = $("conteudo-detalhe").hidden ? "" : "";
  _leitorAtual = id;
  carregarInfoLeitor(id);
}
function fecharLeitor() {
  $("modal-leitor").hidden = true;
  $("leitor-iframe").src = "";
  _leitorAtual = null;
}
$("leitor-fechar").addEventListener("click", fecharLeitor);
$("modal-leitor").addEventListener("click", e => { if (e.target === $("modal-leitor")) fecharLeitor(); });
$("leitor-ant").addEventListener("click", () => navegarLeitor(-1));
$("leitor-prox").addEventListener("click", () => navegarLeitor(1));
$("leitor-progresso").addEventListener("input", (e) => {
  const v = Number(e.target.value);
  atualizarExibirLeitor(v);
});
$("leitor-marcar-lido").addEventListener("click", async () => {
  if (!_leitorAtual) return;
  try {
    const total = (_leitorInfo && _leitorInfo.total) || 0;
    await api(`/api/artigos/${_leitorAtual}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ marcar_leitura: "sim", progresso_leitura: total, paginas_total: total ? (_leitorInfo.total || 0) : 0 }) });
    toast("Marked as read ✓ (progress saved)");
    listarBiblioteca();
  } catch (e) { toast("Erro: " + e.message); }
});
function navegarLeitor(delta) {
  const info = _leitorInfo;
  if (!info || !info.total) return;
  const prox = Math.min(Math.max(1, info.atual + delta), info.total);
  registrarPagina(info, prox);
}
function atualizarExibirLeitor(pct) {
  $("leitor-pct").textContent = pct + "%";
  $("leitor-progresso").value = pct;
}
let _leitorInfo = { total: 0, atual: 1 };

async function carregarInfoLeitor(id) {
  try {
    const info = await api(`/api/artigos/${id}/reader`);
    _leitorInfo = { total: info.paginas_total || 0, atual: Math.min(Math.max(1, info.progresso_leitura || 1), info.paginas_total || 1) };
    const art = await api(`/api/artigos/${id}`);
    $("leitor-titulo").textContent = art.titulo || "Reading";
    if (info.total) {
      const pct = Math.round((_leitorInfo.atual / info.total) * 100);
      atualizarExibirLeitor(pct);
      $("leitor-pagina").textContent = `Page ${_leitorInfo.atual} of ${info.total}`;
      $("leitor-progresso").max = info.total;
      $("leitor-progresso").value = _leitorInfo.atual;
    }
  } catch (e) {
    $("leitor-titulo").textContent = "Reading (error loading info)";
  }
}
function registrarPagina(info, pagina) {
  _leitorInfo.atual = pagina;
  if (info.total) {
    atualizarExibirLeitor(Math.round((pagina / info.total) * 100));
    $("leitor-pagina").textContent = `Page ${pagina} of ${info.total}`;
  }
  salvarProgressoLeitura(_leitorAtual, pagina);
}
async function salvarProgressoLeitura(id, pagina) {
  try {
    await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ progresso_leitura: pagina, marcar_leitura: "sim" }) });
  } catch { }
}

/* ---------------- Configurações de resumo ---------------- */
function salvarCamposConfig(campos, pessoais) {
  return api("/api/configuracoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resumo_campos: campos, resumo_campos_personalizados: pessoais }),
  });
}
$("cfg-adicionar-campo").addEventListener("click", async () => {
  const nome = $("cfg-novo-campo").value.trim();
  if (!nome) { toast("Type a name for the new section"); return; }
  const instr = $("cfg-novo-campo-instr").value.trim();
  const id = nome.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (!id) { toast("Use letters and numbers for the section name"); return; }
  if (_idsBase.includes(id)) { toast("A section with that name already exists"); return; }
  const marcados = [...$("cfg-campos-resumo").querySelectorAll("input:checked")].map(i => i.value);
  try {
    await salvarCamposConfig([...marcados, id], [..._pessoais, { id, rotulo: nome, instrucao: instr }]);
    $("cfg-novo-campo").value = "";
    $("cfg-novo-campo-instr").value = "";
    toast("Section added");
  } catch (e) { toast("Erro: " + e.message); }
});
$("cfg-campos-resumo").addEventListener("click", async (e) => {
  const bt = e.target.closest(".remover-campo");
  if (!bt) return;
  const id = bt.dataset.id;
  const marcados = [...$("cfg-campos-resumo").querySelectorAll("input:checked")].map(i => i.value).filter(v => v !== id);
  try {
    await salvarCamposConfig(marcados, _pessoais.filter(p => p.id !== id));
    toast("Section removed");
  } catch (e) { toast("Erro: " + e.message); }
});

async function carregarConfig() {
  try {
    const c = await api("/api/configuracoes");
    $("cfg-provider").value = c.summary_provider;
    $("cfg-ollama-url").value = c.ollama_base_url;
    $("cfg-ollama-model").value = c.ollama_model;
    $("cfg-abacus-key").value = c.abacus_api_key || "";
    $("cfg-abacus-url").value = c.abacus_base_url;
    $("cfg-abacus-model").value = c.abacus_model;
    $("cfg-idioma-resumo").value = c.sumario_idioma || "English";
    $("cfg-area-pesquisa").value = c.area_pesquisa || "";
    const disponiveis = c.resumo_campos_disponiveis || [];
    const selecionados = c.resumo_campos || [];
    _pessoais = c.resumo_campos_personalizados || [];
    const base = disponiveis.filter(x => !x.personalizado);
    const todos = [...base, ..._pessoais.map(p => ({ id: p.id, rotulo: p.rotulo, personalizado: true }))];
    _idsBase = todos.map(x => x.id);
    $("cfg-campos-resumo").innerHTML = todos.map(campo =>
      `<span class="campo-item"><label class="check-inline"><input type="checkbox" value="${campo.id}" ${selecionados.includes(campo.id) ? "checked" : ""}> ${esc(campo.rotulo)}</label>` +
      (campo.personalizado ? `<button class="remover-campo" data-id="${campo.id}" title="Remove section">✕</button>` : "") +
      `</span>`
    ).join("") || "<p class='nao-id'>No sections available.</p>";
    const st = await api("/api/status-ferramentas");
    const ollama = st.ollama_ok
      ? `<span class="ok">✓ Ollama active (${st.modelos_ollama.length} local model(s))${st.modelo_padrao_baixado ? "" : " — default model not downloaded yet (it is downloaded on the first summary)"}</span>`
      : `<span class="erro">✗ Ollama is not running. Start it with “ollama serve” or open the Ollama app.</span>`;
    $("status-ferramentas").innerHTML = ollama +
      `<span>Current provider: <b>${c.summary_provider === "abacus" ? "Abacus AI" : "Local Ollama"}</b></span>` +
      (c.api_key_definida ? `<span class="ok">✓ Abacus key configured</span>` : `<span>Abacus key: not configured (required for the Abacus provider)</span>`);
  } catch (e) { $("status-ferramentas").innerHTML = `<span class="erro">Error loading: ${esc(e.message)}</span>`; }
}
$("salvar-config").addEventListener("click", async () => {
  const body = {
    summary_provider: $("cfg-provider").value,
    ollama_base_url: $("cfg-ollama-url").value.trim(),
    ollama_model: $("cfg-ollama-model").value,
    abacus_base_url: $("cfg-abacus-url").value.trim(),
    abacus_model: $("cfg-abacus-model").value.trim(),
    sumario_idioma: $("cfg-idioma-resumo").value,
    area_pesquisa: $("cfg-area-pesquisa").value.trim(),
  };
  const marcados = [...$("cfg-campos-resumo").querySelectorAll("input:checked")].map(i => i.value);
  if (marcados.length) body.resumo_campos = marcados;
  if ($("cfg-abacus-key").value) body.abacus_api_key = $("cfg-abacus-key").value.trim();
  try {
    await api("/api/configuracoes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    $("status-config").textContent = "Saved";
    setTimeout(carregarConfig, 800);
  } catch (e) { $("status-config").textContent = "Error: " + e.message; }
});

/* ---------------- Categorias (admin) ---------------- */
async function carregarCategoriasAdmin() {
  const div = $("lista-categorias-admin");
  try {
    const cats = await api("/api/categorias");
    div.innerHTML = cats.length ? cats.map(c => `
      <div class="linha-categoria">
        <span class="bolinha" style="background:${c.cor || "#4f8cff"}"></span>
        <input type="text" value="${esc(c.nome)}" data-id="${c.id}" data-campo="nome" title="Click away or press Enter to save">
        <input type="color" value="${c.cor || "#4f8cff"}" data-id="${c.id}" data-campo="cor" title="Cor da etiqueta">
        <span class="contagem" id="contagem-${c.id}">…</span>
        <button class="botao-mini perigo" onclick="excluirCategoria(${c.id})">🗑</button>
      </div>`).join("") : '<p class="nao-id">No categories yet.</p>';
    cats.forEach(c => document.querySelectorAll(`[data-id="${c.id}"]`).forEach(el => {
      el.addEventListener("change", () => salvarCategoria(c.id));
    }));
    const url = "/api/artigos?" + new URLSearchParams();
    const artigos = await api("/api/artigos");
    const contagem = {};
    artigos.forEach(a => { if (a.categoria_id) contagem[a.categoria_id] = (contagem[a.categoria_id] || 0) + 1; });
    cats.forEach(c => { const el = $("contagem-" + c.id); if (el) el.textContent = (contagem[c.id] || 0) + " article(s)"; });
  } catch (e) { div.innerHTML = `<p class="nao-id">Erro: ${esc(e.message)}</p>`; }
}
async function salvarCategoria(id) {
  const nomeEl = document.querySelector(`input[data-id="${id}"][data-campo="nome"]`);
  const corEl = document.querySelector(`input[data-id="${id}"][data-campo="cor"]`);
  try {
    await api(`/api/categorias/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: nomeEl.value, cor: corEl.value }) });
    toast("Category saved");
    carregarCategorias();
  } catch (e) { toast("Erro: " + e.message); }
}
async function excluirCategoria(id) {
  if (!confirm("Delete this category from the library?")) return;
  const artigos = await api("/api/artigos");
  for (const a of artigos.filter(x => x.categoria_id === id)) {
    await api(`/api/artigos/${a.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ categoria_id: null }) }).catch(() => {});
  }
  try { await api(`/api/categorias/${id}`, { method: "DELETE" }); carregarCategoriasAdmin(); carregarCategorias(); toast("Category deleted"); }
  catch (e) { toast("Erro: " + e.message); }
}

/* ---------------- Polling de progresso ---------------- */
let _estadoBiblioteca = null;
setInterval(async () => {
  const ativo = document.querySelector(".aba.ativa");
  if (ativo && ativo.dataset.aba === "biblioteca") {
    const artigos = await api("/api/artigos").catch(() => null);
    if (!artigos) return;
    const assinatura = artigos.map(a => `${a.id}|${a.pdf_status}|${a.resumo_status}`).join(";");
    if (_estadoBiblioteca !== null && assinatura !== _estadoBiblioteca) listarBiblioteca();
    _estadoBiblioteca = assinatura;
  }
}, 3000);

(async function init() {
  carregarCategorias();
  carregarTags();
  listarBiblioteca();
  chipsRapidos();
})();
