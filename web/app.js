const ROTULO_TIPO = {
  artigo_periodico: "Journal article", preprint: "Preprint", revisao: "Review",
  capitulo_livro: "Book chapter", anais_congresso: "Conference proceedings",
  livro: "Book", tese_dissertacao: "Thesis/Dissertation", relatorio: "Report",
};
const ROTULO_FONTE = {
  openalex: "OpenAlex", arxiv: "arXiv", semanticscholar: "Semantic Scholar",
  pubmed: "PubMed", crossref: "Crossref", doaj: "DOAJ", europepmc: "Europe PMC",
  manual: "Manual",
};
const ROTULO_PDF = {
  nao_baixado: "Not downloaded", nao_disponivel: "No open version", baixando: "Downloading…",
  baixado: "PDF downloaded", falha: "Download failed",
};
const ROTULO_RESUMO = {
  nao_iniciado: "No summary", processando: "Summarizing…", pronto: "Summary ready", falha: "Summary failed",
};
const CAMPOS_RESUMO = [
  ["objectives", "Objectives"], ["methodology", "Methodology"], ["results", "Results"],
  ["contributions", "Contributions"], ["limitations", "Limitations"],
];

const $ = (id) => document.getElementById(id);
let categorias = [];

const ROTULO_LEITURA = { nao_lido: "Not read", lendo: "Reading", lido: "Read" };

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
  return `<span class="selo ${classe}">${esc(texto)}</span>`;
}

async function carregarCategorias() {
  try {
    categorias = await api("/api/categorias");
  } catch { categorias = []; }
  $("filtro-categoria").innerHTML = '<option value="">Any category</option>' +
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
  if (!Array.isArray(lista) || !lista.length) return "Authors not informed";
  const visiveis = lista.slice(0, limite);
  const resto = lista.length > limite ? " et al." : "";
  return visiveis.join(", ") + resto;
}

function cartaoArtigo(a, emBusca = false) {
  const cat = a.categoria_nome
    ? `<span class="etiqueta-categoria" style="background:${a.categoria_cor || "#4f8cff"}">${esc(a.categoria_nome)}</span>`
    : "";
  const acoesBusca = emBusca ? `
    <button class="botao-mini" onclick="salvarDaBusca(${JSON.stringify(a).replace(/"/g, "&quot;")})">＋ Add to library</button>
    <button class="botao-mini" data-href="${esc(a.url_pagina || "")}" onclick="abrirLink(this)">🔗 Page</button>` : `
    <button class="botao-mini" onclick="baixarPdf(${a.id})">⭳ ${a.pdf_status === "baixado" ? "Re-download" : "Download PDF"}</button>
    <button class="botao-mini" onclick="resumir(${a.id})">✨ Summarize</button>
    ${a.pdf_status === "baixado" ? `<button class="botao-mini" onclick="abrirPdf(${a.id})">📄 Open PDF</button>` : ""}
    <button class="botao-mini" onclick="abrirDetalhe(${a.id})">Details</button>
    <button class="botao-mini" onclick="toggleFavorito(${a.id})">${a.favorito ? "★ Unfavorite" : "☆ Favorite"}</button>
    <select class="botao-mini" onchange="mudarLeitura(${a.id}, this.value)">
      <option value="nao_lido" ${a.read_status === "nao_lido" ? "selected" : ""}>Not read</option>
      <option value="lendo" ${a.read_status === "lendo" ? "selected" : ""}>Reading</option>
      <option value="lido" ${a.read_status === "lido" ? "selected" : ""}>Read</option>
    </select>
    <button class="botao-mini perigo" onclick="excluir(${a.id})">🗑</button>`;
  const statusPdf = a.pdf_status === "baixando" ? selo("andando", ROTULO_PDF[a.pdf_status]) :
    (a.pdf_status === "baixado" ? selo("ok", ROTULO_PDF[a.pdf_status]) :
     (a.pdf_status === "falha" || a.pdf_status === "nao_disponivel" ? selo("erro", ROTULO_PDF[a.pdf_status]) : selo("vazio", ROTULO_PDF[a.pdf_status])));
  const resumoStatus = a.resumo_status === "pronto" ? selo("ok", "Summary ready") :
    (a.resumo_status === "processando" ? selo("andando", "Summarizing…") :
     (a.resumo_status === "falha" ? selo("erro", "Summary failed") : selo("vazio", "No summary")));
  const oa = a.acesso_aberto ? selo("ok", "Open access") : "";
  const fav = a.favorito ? `<span class="selo ok">★ Favorite</span>` : "";
  const leitura = selo("vazio", ROTULO_LEITURA[a.read_status] || "Not read");
  const cit = (!emBusca && a.citacoes) ? selo("fonte", `📊 ${a.citacoes} cit.`) : "";
  const idioma = (!emBusca && a.idioma) ? selo("fonte", a.idioma) : "";
  return `<article class="cartao">
    <div class="meta">${cat}${selo("fonte", ROTULO_FONTE[a.fonte] || a.fonte)}${selo("ano", a.ano || "—")}${selo("tipo", ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "—")}${oa}${fav}${leitura}${cit}${idioma}</div>
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
["filtro-categoria", "filtro-tipo", "filtro-status", "filtro-resumo", "filtro-fonte", "filtro-acesso", "filtro-ordenacao", "filtro-leitura", "filtro-favoritos", "filtro-idioma", "filtro-adicionado"]
  .forEach(id => $(id).addEventListener("change", listarBiblioteca));
["filtro-busca-biblioteca", "filtro-ano-min", "filtro-ano-max", "filtro-citacoes", "filtro-autor"]
  .forEach(id => $(id).addEventListener("input", debounce(listarBiblioteca, 400)));
$("limpar-filtros").addEventListener("click", () => {
  ["filtro-categoria", "filtro-tipo", "filtro-status", "filtro-resumo", "filtro-fonte", "filtro-acesso", "filtro-ordenacao", "filtro-leitura", "filtro-favoritos", "filtro-idioma", "filtro-adicionado"]
    .forEach(id => { $(id).value = ""; });
  ["filtro-busca-biblioteca", "filtro-ano-min", "filtro-ano-max", "filtro-citacoes", "filtro-autor"].forEach(id => { $(id).value = ""; });
  listarBiblioteca();
});
$("fechar-modal").addEventListener("click", () => $("modal-detalhe").hidden = true);
$("modal-detalhe").addEventListener("click", e => { if (e.target === $("modal-detalhe")) $("modal-detalhe").hidden = true; });

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function buscar() {
  const q = $("campo-busca").value.trim();
  if (!q) { toast("Type keywords to search"); return; }
  const params = new URLSearchParams({ q });
  if ($("filtro-tipo-busca").value) params.set("tipo_origem", $("filtro-tipo-busca").value);
  if ($("ano-min").value) params.set("ano_min", $("ano-min").value);
  if ($("ano-max").value) params.set("ano_max", $("ano-max").value);
  const fontes = [...$("filtro-fonte-busca").selectedOptions].map(o => o.value);
  if (fontes.length) params.set("fontes", fontes.join(","));
  if ($("filtro-idioma-busca").value) params.set("idioma", $("filtro-idioma-busca").value);
  if ($("filtro-oa-busca").checked) params.set("acesso_aberto", "1");
  if ($("filtro-ord-busca").value) params.set("ordenacao", $("filtro-ord-busca").value);
  $("status-busca").textContent = "Searching...";
  try {
    const t0 = Date.now();
    const resultados = await api("/api/busca?" + params.toString());
    $("status-busca").textContent = `${resultados.length} result(s) in ${((Date.now() - t0) / 1000).toFixed(1)}s`;
    const div = $("resultados-busca");
    div.innerHTML = resultados.length
      ? resultados.map(r => cartaoArtigo(r, true)).join("")
      : '<p class="vazio">No articles found. Try other keywords or loosen the filters.</p>';
  } catch (e) {
    $("status-busca").textContent = "Search error: " + e.message;
  }
}

async function salvarDaBusca(r) {
  try {
    await api("/api/artigos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(r),
    });
    toast("Article added to library");
    $("status-busca").textContent = "Added ✓";
  } catch (e) { toast("Error: " + e.message); }
}

async function listarBiblioteca() {
  const params = new URLSearchParams();
  const mapear = (id, nome) => { if ($(id).value) params.set(nome, $(id).value); };
  mapear("filtro-categoria", "categoria_id");
  mapear("filtro-tipo", "tipo_origem");
  mapear("filtro-status", "pdf_status");
  mapear("filtro-resumo", "tem_resumo");
  mapear("filtro-fonte", "fonte");
  if ($("filtro-acesso").value) params.set("acesso_aberto", "sim");
  mapear("filtro-leitura", "read_status");
  if ($("filtro-favoritos").value) params.set("favorito", "sim");
  mapear("filtro-idioma", "idioma");
  mapear("filtro-citacoes", "citacoes_min");
  mapear("filtro-adicionado", "adicionado");
  mapear("filtro-autor", "autor");
  mapear("filtro-ano-min", "ano_min");
  mapear("filtro-ano-max", "ano_max");
  mapear("filtro-ordenacao", "ordenacao");
  if ($("filtro-busca-biblioteca").value.trim()) params.set("busca", $("filtro-busca-biblioteca").value.trim());
  try {
    const artigos = await api("/api/artigos?" + params.toString());
    const div = $("lista-biblioteca");
    div.innerHTML = artigos.length
      ? artigos.map(a => cartaoArtigo(a)).join("")
      : '<p class="vazio">Empty library. Search for articles or import PDFs.</p>';
  } catch (e) { toast("Error: " + e.message); }
}

async function baixarPdf(id) {
  try { await api(`/api/artigos/${id}/download`, { method: "POST" }); toast("Download started"); listarBiblioteca(); }
  catch (e) { toast("Error: " + e.message); }
}

async function resumir(id) {
  try { await api(`/api/artigos/${id}/resumir`, { method: "POST" }); toast("Summary started"); listarBiblioteca(); }
  catch (e) { toast("Error: " + e.message); }
}

function abrirPdf(id) { window.open(`/api/artigos/${id}/pdf`, "_blank"); }

async function toggleFavorito(id) {
  try {
    const a = await api(`/api/artigos/${id}`);
    await api(`/api/artigos/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ favorito: a.favorito ? 0 : 1 }),
    });
    listarBiblioteca();
  } catch (e) { toast("Error: " + e.message); }
}

async function mudarLeitura(id, valor) {
  try {
    await api(`/api/artigos/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read_status: valor }),
    });
    listarBiblioteca();
  } catch (e) { toast("Error: " + e.message); }
}

function abrirLink(el) {
  const href = el.dataset.href;
  if (href) window.open(href, "_blank");
}

async function excluir(id) {
  if (!confirm("Delete this article and its PDF from your computer?")) return;
  try { await api(`/api/artigos/${id}`, { method: "DELETE" }); listarBiblioteca(); toast("Article deleted"); }
  catch (e) { toast("Error: " + e.message); }
}

async function abrirDetalhe(id) {
  try {
    const a = await api(`/api/artigos/${id}`);
    let resumoHtml = `<p class="nao-id">No summary yet. Click "Summarize" on the card.</p>`;
    if (a.resumo_status === "processando") resumoHtml = `<p class="nao-id">Summary in progress...</p>`;
    else if (a.resumo_status === "falha") resumoHtml = `<p class="nao-id">Failed: ${esc(a.resumo_mensagem || "unknown error")}</p>`;
    else if (a.resumo_llm) {
      const campos = JSON.parse(a.resumo_llm);
      const mapaPt = { objetivos: "objectives", metodologia: "methodology", resultados: "results", contribuicoes: "contributions", limitacoes: "limitations" };
      resumoHtml = CAMPOS_RESUMO.map(([en, rot]) => {
        const chavePt = Object.keys(mapaPt).find(k => mapaPt[k] === en) || en;
        const valor = campos[en] ?? campos[chavePt] ?? "";
        return `<div class="secao-resumo"><h4>${rot}</h4><p class="${valor === "Not identified in the text" || valor === "Não identificado no texto" ? "nao-id" : ""}">${esc(valor)}</p></div>`;
      }).join("");
    }
    $("conteudo-detalhe").innerHTML = `
      <h3>${esc(a.titulo)}</h3>
      <div class="meta-linha">${autoresHtml(a.autores)} · ${a.ano || "—"} · ${esc(ROTULO_TIPO[a.tipo_origem] || a.tipo_origem || "")} · source: ${esc(ROTULO_FONTE[a.fonte] || a.fonte)}${a.acesso_aberto ? " · Open access" : ""}</div>
      ${a.classificacao ? `<div class="meta-linha">🧭 ${esc(a.classificacao)}</div>` : ""}
      ${a.doi ? `<div class="meta-linha">DOI: ${esc(a.doi)}</div>` : ""}
      ${a.caminho_pdf ? `<a href="/api/artigos/${a.id}/pdf" target="_blank" class="botao-mini">📄 Open PDF</a>` : ""}
      <a href="${esc(a.url_pagina || "#")}" target="_blank" class="botao-mini">🔗 Article page</a>
      <div class="secao-resumo"><h4>Abstract</h4><p>${esc(a.resumo || "Not available")}</p></div>
      <div class="secao-resumo"><h4>Structured summary</h4>${resumoHtml}</div>
      <div class="secao-resumo"><h4>Organization</h4>
        <p>Classification: <input id="det-classif" value="${esc(a.classificacao || "")}" style="width:220px"></p>
        <p>${gerenciarCategoria(a)}</p>
        <p>Reading status: <select id="det-leitura">
          <option value="nao_lido" ${a.read_status === "nao_lido" ? "selected" : ""}>Not read</option>
          <option value="lendo" ${a.read_status === "lendo" ? "selected" : ""}>Reading</option>
          <option value="lido" ${a.read_status === "lido" ? "selected" : ""}>Read</option>
        </select> <label><input type="checkbox" id="det-favorito" ${a.favorito ? "checked" : ""}> ★ Favorite</label></p>
        <button class="botao-mini" onclick="salvarDetalhe(${a.id})">Save organization</button>
      </div>`;
    $("modal-detalhe").hidden = false;
  } catch (e) { toast("Error: " + e.message); }
}

function gerenciarCategoria(a) {
  return `Category: <select id="det-categoria">
      <option value="">(no category)</option>
      ${categorias.map(c => `<option value="${c.id}" ${c.id === a.categoria_id ? "selected" : ""}>${esc(c.nome)}</option>`).join("")}
    </select>
    <input id="det-nova-categoria" placeholder="or create new..." style="width:180px">`;
}

async function salvarDetalhe(id) {
  const body = { classificacao: $("det-classif").value, categoria_id: $("det-categoria").value || null };
  if ($("det-nova-categoria").value.trim()) body.nova_categoria = $("det-nova-categoria").value.trim();
  if ($("det-leitura")) body.read_status = $("det-leitura").value;
  if ($("det-favorito")) body.favorito = $("det-favorito").checked ? 1 : 0;
  try {
    await api(`/api/artigos/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await carregarCategorias();
    $("modal-detalhe").hidden = true;
    listarBiblioteca();
    toast("Organization saved");
  } catch (e) { toast("Error: " + e.message); }
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
    await fetch("/api/importar", { method: "POST", body: form });
    $("status-importar").textContent = "Imported ✓";
    ["imp-titulo", "imp-autores", "imp-ano", "imp-classificacao", "imp-categoria"].forEach(id => $(id).value = "");
    $("nome-arquivo").textContent = "";
    $("arquivo-import").value = "";
  } catch (e) { $("status-importar").textContent = "Error: " + e.message; }
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
      ? `<span class="ok">✓ Ollama running (${st.modelos_ollama.length} local model(s))${st.modelo_padrao_baixado ? "" : " — default model not downloaded yet (first summary will pull it)"}</span>`
      : `<span class="erro">✗ Ollama is not running. Start it with "ollama serve" or open the Ollama app.</span>`;
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
  };
  if ($("cfg-abacus-key").value) body.abacus_api_key = $("cfg-abacus-key").value.trim();
  try {
    await api("/api/configuracoes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    $("status-config").textContent = "Saved ✓";
    setTimeout(carregarConfig, 800);
  } catch (e) { $("status-config").textContent = "Error: " + e.message; }
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
