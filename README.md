# Quire 📚

**Sua biblioteca de pesquisa, local e privada.**

O Quire unifica o fluxo de leitura científica num único app que roda 100% no seu
computador: **busca em 16+ fontes**, **download legal de PDFs abertos**, **resumos
estruturados** gerados por IA local, **leitor de PDF com progresso**, **notas e
tags** por artigo, **gráficos estatísticos** e **exportação** para BibTeX,
Markdown, JSON ou backup completo.

## Funcionalidades

### 🔍 Busca unificada (16+ fontes)
Busca por palavras-chave com filtros: tipo de artigo, intervalo de anos, fontes
(multi-seleção), idioma, só acesso aberto e ordenação (relevância, mais novos/
antigos, mais citados, título).
Fontes: **OpenAlex, arXiv, PubMed, Crossref, DOAJ, Europe PMC, Semantic Scholar,
dblp, HAL, Zenodo, OpenAIRE, PLOS, OpenReview, OSF, Figshare, DataCite**.

### ⚡ Em alta
Destaques dos últimos 7/30/90 dias e **tópicos em alta na sua área** (lista de
palavras-chave configurável), além dos papers do dia da **Hugging Face Daily
Papers**. Tudo adicionável à biblioteca com um clique.

### 📥 Download legal de PDFs
Resolvedores de DOI (OpenAlex → Unpaywall → Crossref) + o próprio link do PDF do
artigo. Sem versão aberta? **Importe manualmente** (arraste e solte) — o app tenta
preencher título, autores, ano e classificação pelo DOI encontrado no PDF.

### ✨ Resumos estruturados
Gera **apenas o que você pedir**: objetivos, metodologia, resultados,
contribuições, limitações, novidade, trabalhos relacionados/futuros e seções
personalizadas — com idioma selecionável (inglês/português). Roda localmente
via **Ollama** (seus PDFs nunca saem do PC) ou via **Abacus AI** (opcional).

### 📖 Leitor com progresso e notas
- **Leitor de PDF embutido** com barra de progresso por página; o progresso é
  salvo automaticamente e aparece em cada card da biblioteca.
- **Anotações editáveis** por artigo (notas de leitura).
- **Tags** por artigo, filtráveis e clicáveis.
- **Marcar como lido** direto no leitor.

### 📚 Biblioteca organizada
- Classificação com **categoria e cor editáveis** (renomear, mudar cor, excluir).
- Filtros: categoria, tipo, fonte, status do PDF, resumo, leitura, favoritos,
  idioma, mínimo de citações, autor, ano e data de adição.
- **12 opções de ordenação**, incluindo "em leitura primeiro" e "última leitura".
- **Dashboard de estatísticas** com gráficos: artigos por ano, distribuição por
  fonte e status de leitura.
- **Stats rápidos** (total, com PDF, resumidos, favoritos, não lidos, citações).

### 📤 Exportação e dados
- **BibTeX**, **JSON** e **Markdown** da biblioteca inteira ou de um único artigo
  (resumo + notas + tags).
- **Backup completo (ZIP)** do banco e de todos os PDFs.
- **Resumir em lote**: um clique agenda resumo para todos os artigos com PDF que
  ainda não têm.

### 🛡️ Proteção e gestão de PDFs
- Proteção contra duplicatas (mesmo DOI/título rejeitado com aviso).
- Rebaixar, anexar ou **excluir só o PDF** (mantendo o registro).
- DOI mostrado quando não há PDF, com link ao editor e botão copiar.

### 📊 Métricas por artigo
No detalhe, "Obter métricas" busca citações totais, referências, barras de
citação por ano e conceitos de pesquisa no OpenAlex.

## Requisitos

- Python 3.10+ (WSL ou Windows)
- [Ollama](https://ollama.com) instalado e rodando (modelo local ~2 GB, baixado
  automaticamente no primeiro resumo)
- Opcional: chave da API Abacus AI (https://routellm.abacus.ai/v1, modelo `route-llm`)

## Como rodar

**No Windows:** `start.bat`

**No WSL/Linux:** `./run.sh`

Abra <http://localhost:8000>.

## Como usar

1. **Buscar**: digite palavras-chave, aplique filtros e clique em Buscar.
2. **Adicionar**: na busca, use "＋ Adicionar" para mandar para a biblioteca.
3. **Baixar**: na biblioteca, "Baixar PDF" tenta as fontes abertas em ordem.
4. **Ler**: com PDF, clique "📖 Ler" — o leitor abre e o progresso é salvo.
5. **Resumir**: clique "✨ Resumir"; use "⚡ Resumir todos" na biblioteca para o
   lote inteiro.
6. **Anotar e tagear**: em "Detalhes", edite notas e tags e salve.
7. **Organizar**: ajuste classificação/categoria em Detalhes, ou edite cores no
   painel de Categorias em Ajustes.
8. **Ajustes**: escolha Ollama local ou Abacus, o modelo, o idioma do resumo e a
   sua "área de pesquisa".
9. **Em alta**: veja destaques e tópicos da semana na sua área.

## Observações

- PDFs e o banco ficam em `data/` dentro do projeto — nada sai do seu PC. Para o
  resumo, o texto é enviado **somente** ao provedor escolhido (local se usar
  Ollama).
- Os filtros e ordenações ficaram mais completos; o dashboard usa dados reais da
  sua biblioteca.
- Download automático usa **apenas fontes abertas/legais**. Conteúdo com paywall
  vai pela importação manual.
- PDFs escaneados (sem camada de texto) não podem ser resumidos sem OCR.

## Estrutura

```
quire/
├── app/
│   ├── config.py      # ajustes e caminhos
│   ├── db.py          # SQLite (artigos, categorias, filtros, ordenação)
│   ├── sources.py     # busca unificada (16 fontes) + Unpaywall/Crossref/OpenAlex
│   ├── downloader.py  # download de fontes abertas
│   ├── summarizer.py  # extração de seções + resumo estruturado (Ollama/Abacus)
│   ├── jobs.py        # tarefas em segundo plano
│   └── api.py         # FastAPI
├── web/               # interface (HTML/CSS/JS, sem build)
├── data/              # SQLite + PDFs (criados em runtime, fora do git)
└── run.sh / start.bat
```
