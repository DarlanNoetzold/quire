# Quire

**Biblioteca de pesquisa local e privada.** Busca unificada em 16 fontes acadêmicas, download de PDFs em acesso aberto, resumos estruturados por LLM, leitor integrado, revisão sistemática com extração de evidências numéricas e exportação em BibTeX, JSON, Markdown e backup completo em ZIP.

Versão atual: **1.24** · Roda 100% na sua máquina · SQLite + FastAPI + interface web sem build

---

## Sumário

- [O que é](#o-que-é)
- [Recursos](#recursos)
- [Requisitos](#requisitos)
- [Instalação rápida](#instalação-rápida)
- [Execução com Docker](#execução-com-docker)
- [Instalação manual](#instalação-manual)
- [Execução em segundo plano com PM2](#execução-em-segundo-plano-com-pm2)
- [Configuração](#configuração)
- [Fluxo de uso](#fluxo-de-uso)
- [API REST](#api-rest)
- [Dados, backup e portabilidade](#dados-backup-e-portabilidade)
- [Testes](#testes)
- [Solução de problemas](#solução-de-problemas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Licença](#licença)

---

## O que é

Quire é uma aplicação auto-hospedada que reúne descoberta, leitura e organização de literatura científica em um único workspace. Não há conta, telemetria ou servidor intermediário: os artigos, PDFs, anotações e resumos ficam em um banco SQLite e em uma pasta local. As únicas chamadas externas são as APIs públicas de busca (OpenAlex, arXiv, Crossref etc.) e, opcionalmente, um provedor de LLM para resumos.

## Recursos

### Busca unificada em 16 fontes
Consulta simultânea em OpenAlex, arXiv, PubMed, Crossref, DOAJ, Europe PMC, Semantic Scholar, dblp, HAL, Zenodo, OpenAIRE, PLOS, OpenReview, OSF, Figshare e DataCite, com deduplicação por DOI/título.

Filtros: palavras-chave, tipo de publicação, intervalo de anos, fontes (multi-seleção), idioma, acesso aberto, autor, assunto e citações mínimas. Ordenação por relevância, mais recente, mais antigo, mais citado e título.

### Destaques e monitoramento
- Destaques em janelas de 7, 30 e 90 dias.
- Monitoramento de tópicos configurável por área de pesquisa.
- Atualizações diárias via Hugging Face Daily Papers.
- Adição à biblioteca com um clique.

### Aquisição de PDF
- Pipeline automático de resolução de DOI: OpenAlex → Unpaywall → Crossref, mais links primários de editoras.
- Ingestão manual por arrastar-e-soltar para documentos pagos ou arquivos offline.
- Extração automática de metadados (título, autores, ano, classificação) por DOI embutido no PDF.

### Resumos estruturados
- Campos configuráveis: objetivos, motivação, metodologia, resultados, contribuições, limitações, novidade, trabalhos relacionados, trabalhos futuros e setup experimental — além de campos personalizados.
- Geração em inglês ou português.
- Motores: **Ollama** local (nenhum dado sai da máquina) ou **Abacus AI** (`route-llm`) via API.

### Leitor integrado
- Leitor de PDF no navegador com progresso de leitura por página.
- Anotações em Markdown e notas vinculadas a cada artigo.
- Tags de categorização com filtro e navegação.
- Marcação de lido/não lido.

### Organização e análise
- Categorias com paleta de cores editável.
- Filtros por categoria, tipo, fonte, status de PDF, status de resumo, leitura, favoritos, idioma, citações mínimas, autor e data de inclusão.
- 12 critérios de ordenação, incluindo "em leitura primeiro" e "lido por último".
- Painel estatístico com publicações por ano, distribuição por fonte e velocidade de leitura.

### Revisão sistemática
- Criação de revisões com título e descrição, agregando artigos da biblioteca.
- Detecção automática de evidências numéricas nos resumos (percentuais, amostras, métricas como F1, AUC, RMSE).
- Edição manual das extrações, gráfico comparativo por campo/unidade e exportação em CSV.

### Exportação e backup
- BibTeX, JSON e Markdown (artigo individual ou biblioteca inteira).
- Backup completo do banco e do repositório de PDFs em um ZIP.

## Requisitos

| Item | Versão | Obrigatório |
|---|---|---|
| Python | 3.10+ | Sim |
| curl | qualquer | Sim (instalador) |
| Docker + Compose | 20.10+ | Apenas para o modo Docker |
| Node.js + PM2 | 16+ | Apenas para o modo PM2 |
| Ollama | recente | Opcional (resumos locais) |
| Chave Abacus AI | — | Opcional (resumos na nuvem) |

## Instalação rápida

Um comando instala dependências, cria o ambiente virtual, registra o comando `quire` e sobe o servidor:

```bash
git clone --branch v1.24 --depth 1 https://github.com/DarlanNoetzold/quire.git
cd quire && ./install.sh
```

Ao final, abra **http://localhost:8000**.

Variáveis aceitas pelo instalador:

| Variável | Padrão | Efeito |
|---|---|---|
| `QUIRE_DIR` | `~/quire` | Diretório de instalação (modo remoto) |
| `QUIRE_VERSION` | `v1.24` | Tag baixada quando não há código local |
| `QUIRE_PORT` | `8000` | Porta HTTP |
| `QUIRE_HOST` | `0.0.0.0` | Endereço de escuta |
| `QUIRE_NO_START` | `0` | `1` instala sem iniciar o servidor |
| `QUIRE_FORCE` | `0` | `1` sobrescreve instalação existente |
| `GITHUB_TOKEN` | — | Necessário para baixar de repositório privado |

Depois de instalado, o comando `quire` controla o serviço:

```bash
quire start     # inicia em segundo plano e espera /api/health
quire status    # mostra se está rodando e em qual porta
quire logs      # acompanha data/quire.log
quire stop      # encerra o processo
quire restart   # reinicia
```

## Execução com Docker

```bash
docker compose up -d --build
```

A interface fica em `http://localhost:8000` e o banco/PDFs em `./data` (volume persistente). Para outra porta: `QUIRE_PORT=8085 docker compose up -d`.

```bash
docker compose logs -f     # logs
docker compose down        # parar
```

## Instalação manual

```bash
git clone https://github.com/DarlanNoetzold/quire.git
cd quire
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Atalhos incluídos no repositório:

- `./run.sh` — Linux/WSL, cria o venv se necessário e sobe com `--reload`.
- `start.bat` — Windows, cria o venv, abre o navegador e sobe o servidor.
- `./start_quire.sh` — Linux, sem reload, porta definida por `QUIRE_PORT` (padrão `8085`).

## Execução em segundo plano com PM2

```bash
npm install -g pm2
pm2 start ".venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000" --name quire
pm2 save
pm2 startup
```

No Windows, use `.venv\Scripts\python.exe -m uvicorn app.api:app --host 0.0.0.0 --port 8000`.

## Configuração

As configurações ficam em `data/settings.json` e podem ser editadas pela tela **Settings** da interface (`GET/POST /api/configuracoes`).

| Chave | Padrão | Descrição |
|---|---|---|
| `summary_provider` | `ollama` | `ollama` (local) ou `abacus` (nuvem) |
| `ollama_base_url` | `http://127.0.0.1:11434` | Endpoint do Ollama |
| `ollama_model` | `qwen2.5:3b` | Modelo usado nos resumos locais |
| `abacus_base_url` | `https://routellm.abacus.ai/v1` | Endpoint compatível com OpenAI |
| `abacus_model` | `route-llm` | Modelo do roteador Abacus |
| `abacus_api_key` | vazio | Chave da API (mascarada na leitura) |
| `max_chars` | `45000` | Limite de caracteres do texto enviado ao LLM |
| `resumo_campos` | objetivos, metodologia, resultados, contribuições, limitações | Campos do resumo estruturado |
| `resumo_campos_personalizados` | `[]` | Campos extras com rótulo e instrução |
| `sumario_idioma` | `English` | `English` ou `Portuguese` |
| `area_pesquisa` | tópicos padrão | Área usada no monitoramento e nos destaques |
| `email_unpaywall` | `quire@example.com` | E-mail exigido pela API do Unpaywall |
| `user_agent` | `Quire/1.24 ...` | User-Agent das requisições externas |

Para resumos locais, o Ollama precisa estar ativo (`ollama serve`) e o modelo baixado (`ollama pull qwen2.5:3b`). O endpoint `GET /api/status-ferramentas` informa se o Ollama responde e se o modelo padrão está disponível.

## Fluxo de uso

1. **Search** — digite palavras-chave, ajuste filtros e fontes, adicione os resultados à biblioteca.
2. **Library** — filtre, ordene, categorize e marque favoritos; use *Download* para buscar o PDF em acesso aberto ou *Import* para enviar um PDF local.
3. **Summary** — gere o resumo estruturado (individual ou em lote por `POST /api/resumir-todos`).
4. **Reader** — leia o PDF no navegador, registre progresso, notas e tags.
5. **Review** — crie uma revisão, adicione artigos, detecte evidências numéricas e exporte o CSV.
6. **Dashboard** — acompanhe estatísticas e destaques.
7. **Settings** — configure provedor de LLM, campos do resumo, idioma e área de pesquisa.

## API REST

Documentação interativa em `http://localhost:8000/docs`.

| Método | Rota | Função |
|---|---|---|
| GET | `/api/health` | Verificação de saúde |
| GET | `/api/busca` | Busca unificada nas fontes |
| GET | `/api/destaques?dias=7` | Destaques por janela de dias |
| GET | `/api/stats` | Estatísticas da biblioteca |
| GET | `/api/dashboard` | Dados do painel |
| GET | `/api/artigos` | Lista com filtros e ordenação |
| POST | `/api/artigos` | Adiciona artigo |
| GET | `/api/artigos/{id}` | Detalhe do artigo |
| PATCH | `/api/artigos/{id}` | Atualiza campos |
| DELETE | `/api/artigos/{id}` | Remove artigo |
| DELETE | `/api/artigos` | Remoção em lote |
| POST | `/api/artigos/{id}/download` | Baixa PDF em acesso aberto |
| POST | `/api/artigos/{id}/pdf` | Envia PDF manualmente |
| DELETE | `/api/artigos/{id}/pdf` | Remove PDF |
| GET | `/api/artigos/{id}/pdf` | Serve o PDF |
| GET | `/api/artigos/{id}/reader` | Metadados de leitura |
| GET | `/api/artigos/{id}/metricas` | Métricas de citação |
| GET | `/api/artigos/{id}/markdown` | Artigo em Markdown |
| POST | `/api/artigos/{id}/resumir` | Gera resumo |
| POST | `/api/resumir-todos` | Fila de resumos pendentes |
| POST | `/api/importar` | Importa um PDF |
| POST | `/api/importar/bibliografia` | Importa BibTeX/RIS |
| GET | `/api/export?formato=bibtex\|json\|markdown` | Exporta a biblioteca |
| GET | `/api/backup` | ZIP com banco e PDFs |
| GET/POST | `/api/configuracoes` | Lê/grava configurações |
| GET | `/api/status-ferramentas` | Estado do Ollama e do provedor |
| GET/POST | `/api/categorias` | Lista/cria categorias |
| PATCH/DELETE | `/api/categorias/{id}` | Edita/remove categoria |
| GET | `/api/tags` | Lista tags |
| GET/POST | `/api/revisoes` | Lista/cria revisões |
| GET/DELETE | `/api/revisoes/{id}` | Detalhe/remove revisão |
| PUT/DELETE | `/api/revisoes/{id}/artigos/{artigo_id}` | Adiciona/remove artigo da revisão |
| POST | `/api/revisoes/{id}/extracoes/detectar` | Detecta evidências numéricas |
| PUT | `/api/revisoes/{id}/extracoes` | Salva extrações |
| GET | `/api/revisoes/{id}/grafico` | Dados do gráfico |
| GET | `/api/revisoes/{id}/csv` | Exporta extrações em CSV |

## Dados, backup e portabilidade

Tudo vive em `data/`:

```
data/
├── biblioteca.db     # SQLite: artigos, categorias, tags, revisões, extrações
├── settings.json     # configurações
├── pdfs/             # PDFs baixados ou importados
└── quire.log         # log do servidor (modo instalador)
```

- Backup pela interface: `GET /api/backup` gera `quire-backup.zip` com banco e PDFs.
- Restauração: pare o servidor, substitua o conteúdo de `data/` pelo do ZIP e reinicie.
- `data/` está no `.gitignore`; nada de conteúdo pessoal vai para o repositório.

## Testes

```bash
.venv/bin/python -m pytest tests/ -q
```

Suíte atual: 20 testes (importação, revisão, extração, filtros de busca, resumo, remoção em lote) + 3 subtests. Execute a partir da raiz do projeto para que `app` seja importável.

## Solução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` no pytest | pytest chamado fora da raiz | rode `.venv/bin/python -m pytest tests/ -q` na raiz |
| `Falha ao criar o venv` | falta `python3-venv` | `sudo apt install python3-venv` |
| Porta ocupada (`address already in use`) | outro processo na porta | `QUIRE_PORT=8085 ./install.sh` ou `quire stop` |
| Resumos falham com `ollama` | Ollama parado ou modelo ausente | `ollama serve` e `ollama pull qwen2.5:3b` |
| `401` no provedor Abacus | chave ausente/inválida | informe a chave em Settings |
| PDF não baixado | artigo sem versão aberta | use *Import* com o PDF que você já possui |
| Busca lenta | muitas fontes selecionadas | reduza as fontes ou o intervalo de anos |

## Estrutura do projeto

```
quire/
├── app/
│   ├── api.py          # FastAPI: rotas, exportação, backup, estáticos
│   ├── config.py       # diretórios, settings padrão, catálogo de campos
│   ├── db.py           # schema SQLite, consultas, filtros, índices
│   ├── sources.py      # 16 motores de busca + Unpaywall/Crossref/OpenAlex
│   ├── downloader.py   # pipeline de PDF em acesso aberto
│   ├── importer.py     # importação BibTeX/RIS
│   ├── summarizer.py   # extração de texto e prompts estruturados
│   ├── review.py       # revisão sistemática e evidências numéricas
│   └── jobs.py         # workers assíncronos
├── web/                # interface (HTML, CSS e JS sem build)
├── tests/              # suíte pytest
├── data/               # banco, PDFs e logs (gerado em runtime)
├── install.sh          # instalador/launcher de um comando
├── Dockerfile          # imagem de produção
├── docker-compose.yml  # execução com um comando
├── run.sh / start.bat / start_quire.sh
└── requirements.txt
```

## Licença

Uso pessoal e acadêmico. Consulte o autor antes de redistribuir.
