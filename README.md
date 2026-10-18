# Paper Reader

Local app that unifies your scientific paper reading workflow: **search, download PDFs, generate structured summaries, and organize by classification**. Everything runs on your own computer.

## Features

- **Unified search** by keywords with filters for source type (journal article, preprint, review, book chapter...) and year range, across **11 sources**:
  - [OpenAlex](https://openalex.org) — global catalog (journals, repositories, automatic field classification)
  - [arXiv](https://arxiv.org) — preprints
  - [PubMed](https://pubmed.ncbi.nlm.nih.gov) — biomedical literature (MeSH classification)
  - [Crossref](https://www.crossref.org) — DOI metadata with direct PDF links
  - [DOAJ](https://doaj.org) — open-access journals
  - [Europe PMC](https://europepmc.org) — life science literature, including preprints
  - [Semantic Scholar](https://www.semanticscholar.org) — when its rate limit allows (free tier without key)
  - [dblp](https://dblp.org) — computer science (journals and conferences)
  - [HAL](https://hal.science) — French/international repository with direct PDFs
  - [Zenodo](https://zenodo.org) — open publications with direct PDFs
  - [OpenAIRE](https://www.openaire.eu) — European funded research
- **Automatic PDF download from open sources**: OpenAlex → [Unpaywall](https://unpaywall.org) → Crossref, in order. Articles without an automatic open version can be **imported manually** (drag-and-drop).
- **Structured summary** that extracts only what you ask for: **Objectives, Methodology, Results, Contributions and Limitations** (not a generic summary).
- **Library organized by classification**: category suggested automatically (OpenAlex concepts) or set by you, filtered by category, source type, source, PDF status, summary status, open access, reading status (not read/reading/read), favorites, language, minimum citations, author, year range and date added, with **11 sort orders** (date added, title, year, classification, source, citations, favorites, author).

## Requirements

- Python 3.10+ (WSL or Windows)
- [Ollama](https://ollama.com) installed and running (local model ~2 GB, pulled automatically on the first summary)
- Optional: Abacus AI API key (https://routellm.abacus.ai/v1, model `route-llm`) to use the online provider

## How to run

**On WSL/Linux:**

```bash
./run.sh
```

**On Windows:**

```
start.bat
```

Open http://localhost:8000 in your browser.

## How to use

1. **Search**: type keywords, apply filters and click "Search". Add articles to the library with "＋".
2. **Download**: in the library, click "Download PDF" — the app tries the open sources in order. If no open version exists, the message explains it and you use the **Import** tab (the PDF stays only on your PC).
3. **Summarize**: click "Summarize" — the text is extracted, the article sections (abstract, methodology, results, conclusion) are located and sent to the model. The first use pulls the local model automatically.
4. **Organize**: in the article details, adjust classification and category. Filter the library by any criterion and choose a sort order.
5. **Settings**: switch between local Ollama (default) and Abacus AI, choose the model and manage the API key.

## Notes

- PDFs and the database live in `data/` inside the project — nothing leaves your machine. Articles are sent **only** to the chosen provider (local if you use Ollama) to generate the summary.
- The summary uses a **focused excerpt** of the article (abstract + main sections, ~14k chars), which keeps the light model fast and accurate.
- Automatic download uses **only open/legal sources** (OpenAlex, arXiv, Unpaywall, Crossref). Paywalled content goes through manual import.
- Scanned PDFs (no text layer) cannot be summarized without OCR.

## Structure

```
leitor-artigos/
├── app/
│   ├── config.py      # settings and paths
│   ├── db.py          # SQLite (articles, categories, filters, sorting)
│   ├── sources.py     # unified search (7 sources) + Unpaywall/Crossref lookup
│   ├── downloader.py  # download from open sources
│   ├── summarizer.py  # section extraction + structured summary (Ollama/Abacus)
│   ├── jobs.py        # background tasks
│   └── api.py         # FastAPI
├── web/               # interface (HTML/CSS/JS, no build)
├── data/              # SQLite + PDFs (created at runtime, out of git)
└── run.sh / start.bat
```
