# Simple RAG Project

A small teaching project that shows every RAG step:

```text
PDF → text → chunks → embeddings → PostgreSQL/pgvector or MongoDB Atlas → LLM answer
```

## Project structure

```text
app.py            Streamlit UI
ingestion.py      PDF loading, text extraction, chunking, ingestion
embeddings.py     SentenceTransformer model and embeddings
vector_store.py   PostgreSQL/pgvector or MongoDB Atlas storage and search
llm.py            Configured LLM answer generation
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
| MongoDB Atlas | Stores chunks and runs Atlas Vector Search |
| Ollama or Google AI Studio | Generates answers through the selected LLM provider |
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
| `pymongo` | Connects to MongoDB Atlas and manages the vector index |
| `typing_extensions` | Provides typing compatibility helpers |

The exact package versions are listed in [`requirements.txt`](requirements.txt).

## Setup options

## One-click Docker setup

Docker is the recommended way to run the complete local stack. It starts the
Streamlit app, PostgreSQL with pgvector, and the one selected LLM provider.
Docker Desktop works on Windows, macOS, and Linux.

1. Install and start [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Run the launcher from this folder:

   - Windows: double-click `start.bat`.
   - macOS/Linux: run `./start.sh`.
   - PowerShell: run `./start.ps1`.

The launcher reads `LLM_PROVIDER` from `.env`, builds the app image, starts
PostgreSQL, and starts only the selected LLM provider. With Ollama it also
downloads the configured model (`llama3.2:3b` by default). The first run can
take several minutes because Docker images, the embedding model, and—when
selected—the Ollama model must be downloaded.

Stop the stack with `stop.bat`, `stop.ps1`, or `./stop.sh`. Database records and
downloaded Ollama models are kept in Docker volumes, so stopping the stack does
not delete them.

The Docker defaults can be changed in `.env`:

```dotenv
DB_NAME=ai_ml_vectordb
DB_USER=postgres
DB_PASSWORD=testing@123
VECTOR_STORE=postgres
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
MONGODB_URI=
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
APP_HOST_PORT=8501
POSTGRES_HOST_PORT=5432
OLLAMA_HOST_PORT=11434
```

`LLM_PROVIDER=ollama` uses the local Ollama container. To use Google AI Studio
instead, set `LLM_PROVIDER=gemini` and add the API key only in `.env`:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The application sends requests to only the selected provider. Keep `.env` out
of Git; it is already ignored by `.gitignore`. Restart the Docker stack after
changing the provider or its credentials.

For direct Compose commands, use the Ollama profile when Ollama is selected:

```bash
# Ollama
docker compose --profile ollama up -d --build --wait postgres ollama
docker compose --profile ollama run --rm ollama-model
docker compose --profile ollama up -d --build --wait app

# Gemini
docker compose up -d --build --wait
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

Update the database details in `.env`. Set `VECTOR_STORE=postgres` for the
existing local PostgreSQL/pgvector backend, or use MongoDB Atlas:

```dotenv
VECTOR_STORE=mongodb
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
```

For MongoDB Atlas, the app creates the `vectorSearch` index automatically on
the first ingestion. The index uses the same 384-dimensional
`all-MiniLM-L6-v2` embeddings as PostgreSQL. Atlas Vector Search requires a
supported Atlas cluster and permission to create search indexes. If the Atlas
user cannot create indexes, create a Vector Search index named
`vector_index` on `embedding` with 384 dimensions and cosine similarity, then
run the app again.

The UI shows the active vector database and LLM. Ingestion extracts the PDF,
creates chunks, batches the embeddings, and stores all chunks in one operation.
Question retrieval uses the same embedding model and searches the selected
vector database before sending the retrieved context to the LLM.

Create the pgvector extension once if your database user cannot create it:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The application creates the table automatically:

```sql
CREATE TABLE vector_embeddings (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    document_name TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
```

If `vector_embeddings` already exists, the application adds any missing columns
automatically. Existing rows are not deleted.

## Start Ollama manually

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

Set another model in `.env` if needed. When using `LLM_PROVIDER=gemini`, the
manual Ollama steps are not required.

## Run the app

```bash
streamlit run app.py
```

## Detailed workflow documentation

The exact code-level RAG trace, SQL, prompt template, implemented limitations,
and separate recommendations are documented in
[`RAG_WORKFLOW.md`](RAG_WORKFLOW.md).
