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

## Setup

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

## Request flow

1. Upload or select a PDF.
2. Extract and display the PDF text.
3. Split the text into chunks and display them.
4. Create chunk embeddings with `all-MiniLM-L6-v2`.
5. Save chunks and embeddings in PostgreSQL/pgvector.
6. Convert the question with the same embedding function.
7. Search pgvector and display the top five chunks.
8. Send the question and retrieved chunks to Ollama.
9. Display the final answer.
