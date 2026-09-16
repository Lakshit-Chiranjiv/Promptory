# Promptory

**Git-like version control for your LLM prompts.**

Promptory is a self-hosted web app that lets you iterate on LLM prompts the same way you iterate on code — save versions with commit messages, diff any two versions side-by-side, define test cases once and replay them across every version, and export/import your entire prompt as a portable YAML file.

Built with FastAPI + SQLite + HTMX. No cloud account needed. Runs on your machine in under a minute.

---

## What It Does

| Feature | Description |
|---|---|
| **Version history** | Save any prompt as a new version (append-only, like git commits) |
| **Diff viewer** | Compare any two versions with a unified diff + side-by-side view |
| **Test cases** | Define input variable sets once, scoped to a prompt not a version |
| **Test runner** | Run all test cases against any version with one click — results inline |
| **Run history** | Full history of every LLM call per version, with timestamps and status |
| **YAML export** | Download a complete prompt snapshot (all versions + test cases) as a `.yaml` file |
| **YAML import** | Re-create any prompt on a different machine from its YAML file |
| **REST API** | Full JSON API for all operations — Swagger UI at `/docs` |

---

## Tech Stack

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Jinja2](https://img.shields.io/badge/Jinja2-B41717?style=for-the-badge&logo=jinja&logoColor=white)
![HTMX](https://img.shields.io/badge/HTMX-36C?style=for-the-badge&logo=htmx&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=astral&logoColor=white)

| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite (via [SQLAlchemy](https://www.sqlalchemy.org/)) |
| Templates | [Jinja2](https://jinja.palletsprojects.com/) + [HTMX](https://htmx.org/) |
| LLM client | [Groq](https://groq.com/) / OpenAI / Gemini / Ollama (configurable) |
| Package manager | [uv](https://docs.astral.sh/uv/) |

---

## Quickstart

Two ways to run Promptory. Pick one.

---

### 🐳 Option A — Docker (recommended, zero Python setup)

**Requires:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# 1. Clone
git clone https://github.com/your-username/Promptory.git
cd Promptory

# 2. Configure your LLM provider
cp .env.example .env
# Open .env and fill in LLM_PROVIDER, LLM_API_KEY, LLM_MODEL

# 3. Start
docker compose up
```

Open **`http://localhost:8000`**. Done.

The SQLite database is saved to `./data/` on your machine — it survives `docker compose down` and restart cycles.

Useful commands:
```bash
docker compose up --build   # force rebuild after code changes
docker compose up -d        # run in background
docker compose down         # stop
docker compose logs -f      # follow live logs
```

---

### 🐍 Option B — Python (local dev)

### 1. Clone the repo

```bash
git clone https://github.com/your-username/Promptory.git
cd Promptory
```

### 2. Create a virtual environment and install dependencies

```bash
# Using uv (recommended — install from https://docs.astral.sh/uv/)
uv sync

# Or using plain pip
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure your LLM provider

```bash
cp .env.example .env
```

Open `.env` and fill in three values:

```env
LLM_PROVIDER=groq            # openai | anthropic | gemini | groq | ollama
LLM_API_KEY=gsk_...          # your API key (leave blank for Ollama)
LLM_MODEL=llama-3.1-8b-instant
```

**Free options that work out of the box:**
- [Groq](https://console.groq.com/) — free tier, very fast, no card required
- [Google Gemini](https://aistudio.google.com/) — free tier, generous limits
- [Ollama](https://ollama.com/) — fully local, no API key, no internet

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

Open **`http://127.0.0.1:8000`** in your browser. That's it.

---

## Project Structure

```
Promptory/
├── app/
│   ├── main.py              # FastAPI app, router registration
│   ├── database.py          # SQLAlchemy engine + session factory
│   ├── models.py            # ORM table definitions (4 tables)
│   ├── schemas.py           # Pydantic request/response models
│   ├── routes/
│   │   ├── prompts.py       # GET/POST /prompts
│   │   ├── versions.py      # POST /prompts/{id}/versions, diff endpoint
│   │   ├── test_cases.py    # GET/POST /prompts/{id}/test-cases
│   │   ├── runs.py          # POST /prompts/{id}/versions/{v}/run
│   │   ├── yaml_io.py       # GET /prompts/{id}/export, POST /prompts/import
│   │   └── ui.py            # Browser-facing HTML routes (/p/, /v/)
│   ├── services/
│   │   ├── llm_service.py   # Provider-agnostic LLM call (Groq/OpenAI/Gemini/Ollama)
│   │   └── diff_service.py  # Unified diff via difflib
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html
│       ├── index.html
│       ├── prompt_detail.html
│       ├── diff_view.html
│       ├── run_results.html
│       └── partials/
│           └── run_result_rows.html   # HTMX fragment for inline run results
├── static/
│   └── style.css            # All styles
├── data/
│   └── promptory.db         # SQLite database (auto-created on first run)
├── .env.example             # Copy this to .env and fill in your keys
├── pyproject.toml           # Project metadata + dependencies
└── requirements.txt         # pip-compatible dependency list
```

---

## Database Schema

```
prompts
  id, name, description, created_at

prompt_versions                          (append-only — never updated)
  id, prompt_id → prompts, version_number, content, commit_message, created_at

test_cases                               (scoped to a prompt, not a version)
  id, prompt_id → prompts, input_variables (JSON string), expected_output, created_at

test_runs                                (one row per version × test case execution)
  id, prompt_version_id → prompt_versions, test_case_id → test_cases,
  actual_output, status (success|error), created_at
```

---

## REST API Reference

The full interactive API is available at **`http://127.0.0.1:8000/docs`** (Swagger UI).

### Prompts

| Method | URL | Description |
|---|---|---|
| `GET` | `/prompts/` | List all prompts |
| `POST` | `/prompts/` | Create a prompt `{"name": "...", "description": "..."}` |
| `GET` | `/prompts/{id}` | Get prompt with full version history |

### Versions

| Method | URL | Description |
|---|---|---|
| `GET` | `/prompts/{id}/versions` | List all versions for a prompt |
| `POST` | `/prompts/{id}/versions` | Save a new version `{"content": "...", "commit_message": "..."}` |
| `GET` | `/prompts/{id}/versions/{v1}/diff/{v2}` | Unified diff between two version numbers |

### Test Cases

| Method | URL | Description |
|---|---|---|
| `GET` | `/prompts/{id}/test-cases` | List all test cases for a prompt |
| `POST` | `/prompts/{id}/test-cases` | Add a test case `{"input_variables": "{\"key\": \"val\"}"}` |

### Runs

| Method | URL | Description |
|---|---|---|
| `POST` | `/prompts/{id}/versions/{v}/run` | Run all test cases against version `v`, record results |
| `GET` | `/prompts/{id}/versions/{v}/runs` | List all recorded runs for a version |

### YAML Export / Import

| Method | URL | Description |
|---|---|---|
| `GET` | `/prompts/{id}/export` | Download full prompt snapshot as `.yaml` |
| `POST` | `/prompts/import` | Upload a `.yaml` file, create a new prompt from it |

---

## Using Test Cases

Test cases use `{variable}` placeholder syntax matching your prompt content.

**Example prompt:**
```
Recommend a book based on:
- Genre: {genre}
- Country of origin: {origin}
```

**Example test case `input_variables`:**
```json
{"genre": "literary fiction", "origin": "Japan"}
```

When you hit **Run Tests**, Promptory substitutes the variables into the prompt and sends the result to your configured LLM. The output is saved and visible inline and in the full run history.

---

## YAML Export/Import

**Export** a prompt to a portable file:
```
GET http://127.0.0.1:8000/prompts/2/export
```
The browser downloads `book_finder_prompt_prompt.yaml` — a plain-text file you can commit to git or share with a teammate.

**Import** it on any Promptory instance:
```bash
# PowerShell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/prompts/import" `
  -Form @{ file = Get-Item ".\book_finder_prompt_prompt.yaml" }

# curl
curl -X POST http://127.0.0.1:8000/prompts/import \
  -F "file=@book_finder_prompt_prompt.yaml"
```

A brand-new prompt is created. Existing data is never modified.

---

## Supported LLM Providers

Configure via `.env`. No code changes needed to switch providers.

| Provider | `LLM_PROVIDER` | Free Tier | Needs `LLM_BASE_URL` |
|---|---|---|---|
| Groq | `groq` | ✅ Yes | No |
| Google Gemini | `gemini` | ✅ Yes | No |
| OpenAI | `openai` | ❌ Paid | No |
| Anthropic | `anthropic` | ❌ Paid | No |
| Ollama (local) | `ollama` | ✅ Fully free | Yes (`http://localhost:11434`) |

---

## Development

```bash
# Run with auto-reload (recommended during development)
uvicorn app.main:app --reload

# Run without reload (production-like)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The SQLite database file is created automatically at `data/promptory.db` on first run. Delete it to start fresh.