# Simple RAG Project

A small teaching project that shows every RAG step:

```text
PDF → text → chunks → embeddings → MongoDB Atlas → LLM answer
```

## Project structure

```text
app.py            Streamlit UI
ingestion.py      PDF loading, text extraction, chunking, ingestion
embeddings.py     Local deterministic vector generation
vector_store.py   MongoDB Atlas storage and vector search
llm.py            Configured LLM answer generation
db.py             Database connection checks
.env.example      Environment variable example
requirements.txt  Python dependencies
datasets/         Example PDF files
```

## Tools

| Tool | Purpose |
| --- | --- |
| Python 3 | Runs the application and RAG pipeline |
| Streamlit | Provides the web interface |
| MongoDB Atlas | Stores chunks and runs Atlas Vector Search |
| Ollama or Google AI Studio | Generates answers through the selected LLM provider |
| Git | Version control for the project |

## Libraries

| Library | Purpose |
| --- | --- |
| `PyMuPDF` | Extracts text from PDF documents |
| Python standard library | Creates deterministic 384-dimensional document and question vectors without a model download |
| `streamlit` | Builds the interactive application UI |
| `requests` | Sends prompts to the configured LLM HTTP API |
| `python-dotenv` | Loads configuration values from `.env` |
| `pymongo` | Connects to MongoDB Atlas and manages the vector index |

The exact package versions are listed in [`requirements.txt`](requirements.txt).

## Setup options

## Lightweight Docker setup

Docker Desktop works on Windows, macOS, and Linux. The default setup uses
Google AI Studio for answers, so it starts only the app; no database or large
local model is downloaded locally.

1. Copy `.env.example` to `.env`.
2. Set `GEMINI_API_KEY` in `.env`.
3. Run from this folder:

   ```bash
   docker compose up -d --build
   ```

4. Open http://localhost:8501.

Stop the app with `docker compose down`. Database records remain in the Docker
volume. Embeddings are generated locally without downloading an embedding
model.

The GitHub Actions workflow at `.github/workflows/ci.yaml` builds the Docker
image for pushes and pull requests. Every branch push and manual workflow run
also publishes the image to
`<AWS_ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/suresh/rag`. Pull requests
build without publishing. Every branch push or manual workflow run also
deploys the published image to EC2 using AWS Systems Manager. Each image tag
includes the commit SHA, workflow run ID, and attempt number so it stays unique
when retrying builds in an immutable ECR repository.

Configure these GitHub Actions secrets: `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`, `AWS_REGION`, and
`EC2_INSTANCE_ID`. The AWS credentials need permissions to push to the ECR
repository and send and inspect SSM commands. The EC2 instance must be a
Systems Manager managed node with an instance role that can pull from this ECR
repository, Docker and AWS CLI installed, and its application environment
file at `/opt/sures-rag/.env`. The workflow replaces the running
`suresh-rag-app` container and serves it on port 8501. Configure the EC2
security group and network to allow intended clients to reach that port.

The Docker defaults can be changed in `.env`:

```dotenv
VECTOR_STORE=mongodb
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
APP_HOST_PORT=8501
OLLAMA_HOST_PORT=11434
```

To use Google AI Studio, set `LLM_PROVIDER=gemini` and add the API key only in
`.env`:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The application sends requests to only the selected provider. Keep `.env` out
of Git; it is already ignored by `.gitignore`. Restart the Docker stack after
changing the provider or its credentials.

For optional local Ollama use, set `LLM_PROVIDER=ollama` and run:

```bash
# Ollama
docker compose --profile ollama up -d --build --wait ollama
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

For the lightweight setup, set `VECTOR_STORE=mongodb` and provide a MongoDB
Atlas connection string:

```dotenv
VECTOR_STORE=mongodb
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
```

For MongoDB Atlas, the app creates the `vectorSearch` index automatically on
the first ingestion. The index uses the same 384-dimensional local vectors as
MongoDB Atlas. Atlas Vector Search requires a
supported Atlas cluster and permission to create search indexes. If the Atlas
user cannot create indexes, create a Vector Search index named
`vector_index` on `embedding` with 384 dimensions and cosine similarity, then
run the app again.

The UI shows the active vector database and LLM. Ingestion extracts the PDF,
creates chunks, batches the embeddings, and stores all chunks in one operation.
Question retrieval uses the same local vectorizer and searches the selected
vector database before sending the retrieved context to the LLM. Re-ingest
documents after changing the vectorizer because vectors from different
algorithms are not comparable.

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
