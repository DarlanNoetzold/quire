# Quire

Local and private research library application.

Quire streamlines scientific discovery and reading into a self-hosted workspace that runs locally on your machine: unified querying across 16+ academic sources, open-access PDF retrieval, AI-driven structured paper summaries, integrated reader with progress tracking, notes and tags, statistical analytics, and export options (BibTeX, Markdown, JSON, and complete ZIP backups).

---

## Features

### Unified Search (16+ Academic Sources)
- Filter by keywords, publication type, publication year range, data sources, language, open-access status, and sorting order (relevance, newest, oldest, most cited, title).
- Integrated sources: OpenAlex, arXiv, PubMed, Crossref, DOAJ, Europe PMC, Semantic Scholar, dblp, HAL, Zenodo, OpenAIRE, PLOS, OpenReview, OSF, Figshare, and DataCite.

### Trending & Literature Monitoring
- Highlights across 7, 30, and 90-day intervals.
- Configurable topic monitoring tailored to research domains.
- Daily paper updates via Hugging Face Daily Papers.
- Single-click library addition.

### PDF Acquisition & Manual Ingestion
- Automated DOI resolution pipeline (OpenAlex -> Unpaywall -> Crossref) plus primary publisher PDF links.
- Manual drag-and-drop ingestion for documents behind paywalls or offline files.
- Metadata auto-extraction (title, authors, year, classification) using embedded DOI indexing.

### Structured Paper Summaries
- Configurable section breakdown: objectives, methodology, key findings, core contributions, limitations, novelty, and related/future work.
- Multi-language generation support (English and Portuguese).
- Execution engines: Local via Ollama (zero data leaves the host) or remote via Abacus AI API.

### In-App Document Reader
- Built-in PDF reader with persistent reading progress tracking per page.
- Markdown annotations and reading notes linked per article.
- Categorization tags with filtering and navigation.
- Status toggle to mark papers as read.

### Library Organization & Analytics
- Custom categories with editable color palettes and taxonomy.
- Filtering by category, document type, source, PDF status, summary status, reading state, favorites, language, citation count threshold, author, and date added.
- 12 sorting dimensions including "currently reading first" and "last read".
- Statistical dashboard tracking publications by year, source distribution, and reading velocity.

### Data Management & Export
- Formats supported: BibTeX, JSON, and Markdown (individual article or batch export).
- Full database and PDF repository backup via ZIP archive.
- Batch job queuing for background summarization of pending documents.

---

## Architecture & Project Structure

```
quire/
├── app/
│   ├── config.py      # App settings, directory bindings, and provider configs
│   ├── db.py          # SQLite schema, queries, filters, and indexing
│   ├── sources.py     # 16 source query engines + Unpaywall/Crossref/OpenAlex APIs
│   ├── downloader.py  # Open-access PDF download pipeline
│   ├── summarizer.py  # Text extraction and structured LLM prompting
│   ├── jobs.py        # Background asynchronous workers
│   └── api.py         # FastAPI application endpoints and static mounting
├── web/               # Frontend user interface (HTML5, Vanilla CSS, JS)
├── tests/             # Unit and integration test suite (pytest)
├── data/              # SQLite database, logs, and downloaded PDFs (runtime generated)
├── run.sh             # Linux / WSL startup shell script
├── start.bat          # Windows batch startup script
└── ecosystem.config.js # Optional PM2 process configuration
```

---

## Prerequisites

- Python 3.10 or higher
- Node.js & npm (if using PM2)
- Ollama running locally (optional, for local summarization)
- Abacus AI API key (optional, for cloud routing model `route-llm`)

---

## Installation & Setup

1. Clone repository:
```bash
git clone <repository_url> quire
cd quire
```

2. Create virtual environment and install dependencies:

**Linux / WSL:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (cmd/PowerShell):**
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Running the Application

### Method 1: Using PM2 (Production / Background Process)

PM2 keeps the FastAPI server running as a persistent background daemon, handles automatic restarts, and captures log output.

1. Install PM2 globally (requires Node.js):
```bash
npm install -g pm2
```

2. Ensure the virtual environment has dependencies installed:
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

3. Start Quire with PM2:

**Option A: Direct CLI command (Linux / WSL)**
```bash
pm2 start ".venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000" --name quire
```

**Option A (Windows PowerShell / cmd)**
```cmd
pm2 start ".venv\Scripts\python.exe -m uvicorn app.api:app --host 0.0.0.0 --port 8000" --name quire
```

**Option B: Using an ecosystem file**
Create `ecosystem.config.js` in the project root:
```javascript
module.exports = {
  apps: [
    {
      name: "quire",
      script: ".venv/bin/uvicorn",
      args: "app.api:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      env: {
        PYTHONUNBUFFERED: "1"
      },
      error_file: "data/pm2-err.log",
      out_file: "data/pm2-out.log",
      time: true
    }
  ]
};
```
Then launch:
```bash
pm2 start ecosystem.config.js
```

4. Useful PM2 commands:
```bash
pm2 status quire      # Check process status
pm2 logs quire        # View real-time logs
pm2 restart quire     # Restart server
pm2 stop quire        # Stop server
pm2 delete quire      # Remove from PM2 registry
pm2 save              # Save PM2 process list across system reboots
```

### Method 2: Standard Shell Scripts

**Linux / WSL:**
```bash
chmod +x run.sh
./run.sh
```

**Windows:**
Double-click `start.bat` or run:
```cmd
start.bat
```

Once running, open your browser at:
`http://localhost:8000`

---

## Running Tests

Run the test suite with pytest:
```bash
.venv/bin/pytest tests/
```
