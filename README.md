# Quire

**Local and private research library.** Unified search across 16 academic sources, open-access PDF retrieval, LLM-generated structured summaries, an integrated reader, systematic review with numeric-evidence extraction, and export to BibTeX, JSON, Markdown and full ZIP backups.

Current version: **1.24** · Runs entirely on your machine · SQLite + FastAPI + build-free web UI

---

## Table of contents

- [What it is](#what-it-is)
- [Features](#features)
- [Requirements](#requirements)
- [Quick install](#quick-install)
- [Running with Docker](#running-with-docker)
- [Manual installation](#manual-installation)
- [Running in the background with PM2](#running-in-the-background-with-pm2)
- [Configuration](#configuration)
- [Usage flow](#usage-flow)
- [REST API](#rest-api)
- [Data, backup and portability](#data-backup-and-portability)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [License](#license)

---

## What it is

Quire is a self-hosted application that brings scientific literature discovery, reading and organization into a single workspace. There is no account, no telemetry and no intermediary server: articles, PDFs, notes and summaries live in a local SQLite database and a local folder. The only outbound calls are to public search APIs (OpenAlex, arXiv, Crossref and others) and, optionally, to an LLM provider for summaries.

## Features

### Unified search across 16 sources
Simultaneous queries against OpenAlex, arXiv, PubMed, Crossref, DOAJ, Europe PMC, Semantic Scholar, dblp, HAL, Zenodo, OpenAIRE, PLOS, OpenReview, OSF, Figshare and DataCite, with DOI/title deduplication.

Filters: keywords, publication type, year range, sources (multi-select), language, open access, author, subject and minimum citations. Sorting by relevance, newest, oldest, most cited and title.

### Trending and monitoring
- Highlights over 7, 30 and 90-day windows.
- Topic monitoring configurable per research area.
- Daily paper updates via Hugging Face Daily Papers.
- One-click addition to the library.

### PDF acquisition
- Automated DOI resolution pipeline: OpenAlex → Unpaywall → Crossref, plus primary publisher links.
- Manual drag-and-drop ingestion for paywalled documents or offline files.
- Automatic metadata extraction (title, authors, year, classification) from the DOI embedded in the PDF.

### Structured summaries
- Configurable fields: objectives, motivation, methodology, results, contributions, limitations, novelty, related work, future work and experimental setup — plus custom fields.
- Generation in English or Portuguese.
- Engines: local **Ollama** (no data leaves the machine) or **Abacus AI** (`route-llm`) over the API.

### Integrated reader
- In-browser PDF reader with per-page reading progress.
- Markdown annotations and notes linked to each article.
- Categorization tags with filtering and navigation.
- Read/unread toggle.

### Organization and analytics
- Categories with an editable color palette.
- Filters by category, type, source, PDF status, summary status, reading state, favorites, language, minimum citations, author and date added.
- 12 sorting dimensions, including "currently reading first" and "last read".
- Statistical dashboard with publications by year, source distribution and reading velocity.

### Systematic review
- Create reviews with a title and description, aggregating articles from the library.
- Automatic detection of numeric evidence in summaries (percentages, sample sizes, metrics such as F1, AUC, RMSE).
- Manual editing of extractions, comparative chart by field/unit and CSV export.

### Export and backup
- BibTeX, JSON and Markdown (single article or the whole library).
- Full backup of the database and PDF repository as a single ZIP.

## Requirements

| Item | Version | Required |
|---|---|---|
| Python | 3.10+ | Yes |
| curl | any | Yes (installer) |
| Docker + Compose | 20.10+ | Docker mode only |
| Node.js + PM2 | 16+ | PM2 mode only |
| Ollama | recent | Optional (local summaries) |
| Abacus AI key | — | Optional (cloud summaries) |

## Quick install

A single command installs dependencies, creates the virtual environment, registers the `quire` command and starts the server:

```bash
git clone --branch v1.24 --depth 1 https://github.com/DarlanNoetzold/quire.git
cd quire && ./install.sh
```

When it finishes, open **http://localhost:8000**.

Variables accepted by the installer:

| Variable | Default | Effect |
|---|---|---|
| `QUIRE_DIR` | `~/quire` | Install directory (remote mode) |
| `QUIRE_VERSION` | `v1.24` | Tag downloaded when no local code is present |
| `QUIRE_PORT` | `8000` | HTTP port |
| `QUIRE_HOST` | `0.0.0.0` | Listen address |
| `QUIRE_NO_START` | `0` | `1` installs without starting the server |
| `QUIRE_FORCE` | `0` | `1` overwrites an existing installation |
| `GITHUB_TOKEN` | — | Required to download from a private repository |

Once installed, the `quire` command controls the service:

```bash
quire start     # starts in the background and waits for /api/health
quire status    # shows whether it is running and on which port
quire logs      # follows data/quire.log
quire stop      # terminates the process
quire restart   # restarts
```

## Running with Docker

```bash
docker compose up -d --build
```

The interface is served at `http://localhost:8000` and the database/PDFs live in `./data` (persistent volume). For another port: `QUIRE_PORT=8085 docker compose up -d`.

```bash
docker compose logs -f     # logs
docker compose down        # stop
```

## Manual installation

```bash
git clone https://github.com/DarlanNoetzold/quire.git
cd quire
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Shortcuts included in the repository:

- `./run.sh` — Linux/WSL, creates the venv if needed and starts with `--reload`.
- `start.bat` — Windows, creates the venv, opens the browser and starts the server.
- `./start_quire.sh` — Linux, no reload, port from `QUIRE_PORT` (default `8085`).

## Running in the background with PM2

```bash
npm install -g pm2
pm2 start ".venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000" --name quire
pm2 save
pm2 startup
```

On Windows, use `.venv\Scripts\python.exe -m uvicorn app.api:app --host 0.0.0.0 --port 8000`.

## Configuration

Settings live in `data/settings.json` and can be edited from the **Settings** screen (`GET/POST /api/configuracoes`).

| Key | Default | Description |
|---|---|---|
| `summary_provider` | `ollama` | `ollama` (local) or `abacus` (cloud) |
| `ollama_base_url` | `http://127.0.0.1:11434` | Ollama endpoint |
| `ollama_model` | `qwen2.5:3b` | Model used for local summaries |
| `abacus_base_url` | `https://routellm.abacus.ai/v1` | OpenAI-compatible endpoint |
| `abacus_model` | `route-llm` | Abacus router model |
| `abacus_api_key` | empty | API key (masked on read) |
| `max_chars` | `45000` | Character limit of the text sent to the LLM |
| `resumo_campos` | objectives, methodology, results, contributions, limitations | Structured summary fields |
| `resumo_campos_personalizados` | `[]` | Extra fields with label and instruction |
| `sumario_idioma` | `English` | `English` or `Portuguese` |
| `area_pesquisa` | default topics | Area used for monitoring and highlights |
| `email_unpaywall` | `quire@example.com` | Email required by the Unpaywall API |
| `user_agent` | `Quire/1.24 ...` | User-Agent for outbound requests |

For local summaries, Ollama must be running (`ollama serve`) with the model pulled (`ollama pull qwen2.5:3b`). The `GET /api/status-ferramentas` endpoint reports whether Ollama responds and whether the default model is available.

## Usage flow

1. **Search** — enter keywords, adjust filters and sources, add results to the library.
2. **Library** — filter, sort, categorize and favorite; use *Download* to fetch the open-access PDF or *Import* to upload a local PDF.
3. **Summary** — generate the structured summary (single article or batch via `POST /api/resumir-todos`).
4. **Reader** — read the PDF in the browser, track progress, notes and tags.
5. **Review** — create a review, add articles, detect numeric evidence and export the CSV.
6. **Dashboard** — follow statistics and highlights.
7. **Settings** — configure the LLM provider, summary fields, language and research area.

## REST API

Interactive documentation at `http://localhost:8000/docs`.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/busca` | Unified search across sources |
| GET | `/api/destaques?dias=7` | Highlights for a day window |
| GET | `/api/stats` | Library statistics |
| GET | `/api/dashboard` | Dashboard data |
| GET | `/api/artigos` | List with filters and sorting |
| POST | `/api/artigos` | Add article |
| GET | `/api/artigos/{id}` | Article detail |
| PATCH | `/api/artigos/{id}` | Update fields |
| DELETE | `/api/artigos/{id}` | Delete article |
| DELETE | `/api/artigos` | Bulk delete |
| POST | `/api/artigos/{id}/download` | Download open-access PDF |
| POST | `/api/artigos/{id}/pdf` | Upload PDF manually |
| DELETE | `/api/artigos/{id}/pdf` | Remove PDF |
| GET | `/api/artigos/{id}/pdf` | Serve the PDF |
| GET | `/api/artigos/{id}/reader` | Reading metadata |
| GET | `/api/artigos/{id}/metricas` | Citation metrics |
| GET | `/api/artigos/{id}/markdown` | Article as Markdown |
| POST | `/api/artigos/{id}/resumir` | Generate summary |
| POST | `/api/resumir-todos` | Queue pending summaries |
| POST | `/api/importar` | Import a PDF |
| POST | `/api/importar/bibliografia` | Import BibTeX/RIS |
| GET | `/api/export?formato=bibtex\|json\|markdown` | Export the library |
| GET | `/api/backup` | ZIP with database and PDFs |
| GET/POST | `/api/configuracoes` | Read/write settings |
| GET | `/api/status-ferramentas` | Ollama and provider status |
| GET/POST | `/api/categorias` | List/create categories |
| PATCH/DELETE | `/api/categorias/{id}` | Edit/remove category |
| GET | `/api/tags` | List tags |
| GET/POST | `/api/revisoes` | List/create reviews |
| GET/DELETE | `/api/revisoes/{id}` | Review detail/removal |
| PUT/DELETE | `/api/revisoes/{id}/artigos/{artigo_id}` | Add/remove article from review |
| POST | `/api/revisoes/{id}/extracoes/detectar` | Detect numeric evidence |
| PUT | `/api/revisoes/{id}/extracoes` | Save extractions |
| GET | `/api/revisoes/{id}/grafico` | Chart data |
| GET | `/api/revisoes/{id}/csv` | Export extractions as CSV |

## Data, backup and portability

Everything lives under `data/`:

```
data/
├── biblioteca.db     # SQLite: articles, categories, tags, reviews, extractions
├── settings.json     # settings
├── pdfs/             # downloaded or imported PDFs
└── quire.log         # server log (installer mode)
```

- Backup from the UI: `GET /api/backup` produces `quire-backup.zip` with the database and PDFs.
- Restore: stop the server, replace the contents of `data/` with the ZIP contents and restart.
- `data/` is in `.gitignore`; no personal content goes into the repository.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Current suite: 20 tests (import, review, extraction, search filters, summarization, bulk delete) + 3 subtests. Run it from the project root so that `app` is importable.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` in pytest | pytest invoked outside the root | run `.venv/bin/python -m pytest tests/ -q` from the root |
| `Failed to create the venv` | `python3-venv` missing | `sudo apt install python3-venv` |
| Port already in use (`address already in use`) | another process on the port | `QUIRE_PORT=8085 ./install.sh` or `quire stop` |
| Summaries fail with `ollama` | Ollama stopped or model missing | `ollama serve` and `ollama pull qwen2.5:3b` |
| `401` from the Abacus provider | missing/invalid key | set the key in Settings |
| PDF not downloaded | article has no open version | use *Import* with the PDF you already have |
| Slow search | too many sources selected | reduce the sources or the year range |

## Project structure

```
quire/
├── app/
│   ├── api.py          # FastAPI: routes, export, backup, static files
│   ├── config.py       # directories, default settings, field catalog
│   ├── db.py           # SQLite schema, queries, filters, indexes
│   ├── sources.py      # 16 search engines + Unpaywall/Crossref/OpenAlex
│   ├── downloader.py   # open-access PDF pipeline
│   ├── importer.py     # BibTeX/RIS import
│   ├── summarizer.py   # text extraction and structured prompts
│   ├── review.py       # systematic review and numeric evidence
│   └── jobs.py         # asynchronous workers
├── web/                # interface (HTML, CSS and JS, no build step)
├── tests/              # pytest suite
├── data/               # database, PDFs and logs (generated at runtime)
├── install.sh          # single-command installer/launcher
├── Dockerfile          # production image
├── docker-compose.yml  # single-command run
├── run.sh / start.bat / start_quire.sh
└── requirements.txt
```

## License

Personal and academic use. Contact the author before redistributing.
