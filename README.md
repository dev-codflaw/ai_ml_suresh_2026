# Simple RAG Project

A small teaching project that shows every RAG step:

```text
PDF → text → chunks → embeddings → pgvector → Ollama answer
```

## Project structure

```text
app.py            Streamlit UI
ingestion.py      PDF loading, text extraction, chunking, ingestion
embeddings.py     SentenceTransformer model and embeddings
vector_store.py   PostgreSQL + pgvector storage and search
llm.py            Ollama answer generation
db.py             PostgreSQL connection
.env.example      Environment variable example
requirements.txt  Python dependencies
datasets/         Example PDF files
```

## Tools

| Tool | Purpose |
| --- | --- |
| Python 3 | Runs the application and RAG pipeline |
| Streamlit | Provides the web interface |
| PostgreSQL | Stores document chunks and metadata |
| pgvector | Stores embeddings and performs similarity search |
| Ollama | Runs the local language model used to generate answers |
| Git | Version control for the project |

## Libraries

| Library | Purpose |
| --- | --- |
| `psycopg` / `psycopg-binary` | Connects Python to PostgreSQL |
| `PyMuPDF` | Extracts text from PDF documents |
| `langchain-text-splitters` | Splits extracted text into manageable chunks |
| `sentence-transformers` | Creates 384-dimensional document and question embeddings using `all-MiniLM-L6-v2` |
| `streamlit` | Builds the interactive application UI |
| `requests` | Sends prompts to the Ollama HTTP API |
| `python-dotenv` | Loads configuration values from `.env` |
| `typing_extensions` | Provides typing compatibility helpers |

The exact package versions are listed in [`requirements.txt`](requirements.txt).

## Setup options

## One-click Docker setup

Docker is the recommended way to run the complete local stack. It starts the
Streamlit app, PostgreSQL with pgvector, and Ollama together. Docker Desktop
works on Windows, macOS, and Linux.

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Run the launcher from this folder:

   - Windows: double-click `start.bat`.
   - macOS/Linux: run `./start.sh`.
   - PowerShell: run `./start.ps1`.

The launcher builds the app image, starts PostgreSQL and Ollama, downloads the
configured Ollama model (`llama3.2:3b` by default), and makes the app available
at <http://localhost:8501>. The first run can take several minutes because the
Docker images, embedding model, and Ollama model must be downloaded.

Stop the stack with `stop.bat`, `stop.ps1`, or `./stop.sh`. Database records and
downloaded Ollama models are kept in Docker volumes, so stopping the stack does
not delete them.

The Docker defaults can be changed in `.env`:

```dotenv
DB_NAME=ai_ml_vectordb
DB_USER=postgres
DB_PASSWORD=testing@123
OLLAMA_MODEL=llama3.2:3b
APP_HOST_PORT=8501
POSTGRES_HOST_PORT=5432
OLLAMA_HOST_PORT=11434
```

If one of these host ports is already in use, change the corresponding value
and open the app using the new `APP_HOST_PORT`.

## Manual Python setup

Run these commands from this folder:

```bash
python3 -m venv suresh_env
source suresh_env/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update the database details in `.env`.

Create the pgvector extension once if your database user cannot create it:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The application creates the table automatically:

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    document_name TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
```

If `document_chunks` already exists, the application adds any missing columns
automatically. Existing rows are not deleted.

## Start Ollama

Install Ollama, then run:

```bash
ollama pull llama3.2:3b
ollama serve
```

To test the model interactively, use another terminal:

```bash
ollama run llama3.2:3b
```

Keep the Ollama server running while using the app.

Set another model in `.env` if needed.

## Run the app

```bash
streamlit run app.py
```

## Detailed workflow documentation

The exact code-level RAG trace, SQL, prompt template, implemented limitations,
and separate recommendations are documented in
[`RAG_WORKFLOW.md`](RAG_WORKFLOW.md).
