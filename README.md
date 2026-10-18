# Leitor de Artigos

Aplicação local para unificar o fluxo de leitura de artigos científicos: **buscar, baixar PDF, resumir de forma estruturada e organizar por classificação**. Tudo roda no seu computador.

## Funcionalidades

- **Busca unificada** por palavras-chave com filtros de tipo de origem (artigo de periódico, preprint, revisão, capítulo...) e ano, usando:
  - [OpenAlex](https://openalex.org) — catálogo global (periódicos, preprints, repositórios), com classificação por área automática
  - [arXiv](https://arxiv.org) — preprints
- **Download automático do PDF por fontes abertas**: OpenAlex → [Unpaywall](https://unpaywall.org) → Crossref, na ordem. Artigos sem versão aberta automática podem ser **importados manualmente** (drag-and-drop).
- **Resumo estruturado** extraindo apenas as informações pedidas: **Objetivos, Metodologia, Resultados, Contribuições e Limitações** (não é um resumo genérico).
- **Biblioteca organizada por classificação**: categoria sugerida automaticamente (conceitos do OpenAlex) ou definida por você, com filtros por categoria, tipo de origem, status de PDF e de resumo.

## Requisitos

- Python 3.10+ (WSL ou Windows)
- [Ollama](https://ollama.com) instalado e rodando (modelo local ~2 GB, baixado automaticamente no primeiro resumo)
- Opcional: chave de API da Abacus AI (https://routellm.abacus.ai/v1, modelo `route-llm`) para usar o provedor online

## Como rodar

**No WSL/Linux:**

```bash
./run.sh
```

**No Windows:**

```
start.bat
```

Abra http://localhost:8000 no navegador.

## Como usar

1. **Buscar**: digite palavras-chave, aplique filtros e clique em "Buscar". Adicione artigos à biblioteca com "＋".
2. **Baixar**: na biblioteca, clique "Baixar PDF" — o app tenta as fontes abertas na ordem. Se não houver versão aberta, a mensagem explica e você usa a aba **Importar** (o PDF fica só no seu PC).
3. **Resumir**: clique "Resumir" — o texto é extraído, as seções do artigo (abstract, metodologia, resultados, conclusão) são localizadas e enviadas ao modelo. O primeiro uso baixa o modelo local automaticamente.
4. **Organizar**: no detalhe do artigo, ajuste classificação e categoria. Filtre a biblioteca por qualquer critério.
5. **Configurações**: troque entre Ollama local (padrão) e Abacus AI, escolha o modelo e gerencie a chave da API.

## Notas

- Os PDFs e o banco de dados ficam em `data/` dentro do projeto — nada sai da sua máquina. Os artigos são enviados **somente** ao provedor escolhido (local se usar Ollama) para gerar o resumo.
- O resumo usa um **trecho focado** do artigo (abstract + seções principais, ~14 mil caracteres), o que mantém o modelo leve rápido e preciso.
- O download automático usa **exclusivamente fontes abertas/legais** (OpenAlex, arXiv, Unpaywall, Crossref). Conteúdo atrás de paywall entra pela importação manual.
- PDFs escaneados (sem camada de texto) não podem ser resumidos sem OCR.

## Estrutura

```
leitor-artigos/
├── app/
│   ├── config.py      # configurações e caminhos
│   ├── db.py          # SQLite (artigos, categorias)
│   ├── sources.py     # busca unificada (OpenAlex, arXiv, Unpaywall, Crossref)
│   ├── downloader.py  # download por fontes abertas
│   ├── summarizer.py  # extração de seções + resumo estruturado (Ollama/Abacus)
│   ├── jobs.py        # tarefas em segundo plano
│   └── api.py         # FastAPI
├── web/               # interface (HTML/CSS/JS, sem build)
├── data/              # SQLite + PDFs (criado em runtime, fora do git)
└── run.sh / start.bat
```
