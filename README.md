# Simple RAG Project

A small teaching project that shows every RAG step:

```text
S3 PDF → text → chunks → embeddings → MongoDB Atlas → LLM answer
```

## Project structure

```text
app.py            Streamlit UI
s3_storage.py     S3 upload, listing, and in-memory PDF download
ingestion.py      PDF loading, text extraction, chunking, ingestion
embeddings.py     Local deterministic vector generation
vector_store.py   MongoDB Atlas storage and vector search
llm.py            Configured LLM answer generation
db.py             Database connection checks
.env.example      Environment variable example
requirements.txt  Python dependencies
.streamlit/       Streamlit upload-size configuration
```

## Tools

| Tool | Purpose |
| --- | --- |
| Python 3 | Runs the application and RAG pipeline |
| Streamlit | Provides the web interface |
| MongoDB Atlas | Stores chunks and runs Atlas Vector Search |
| Amazon S3 | Stores uploaded PDFs (maximum 30 MB per file) |
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
| `boto3` | Uploads, lists, and downloads PDFs from Amazon S3 |

The exact package versions are listed in [`requirements.txt`](requirements.txt).

## Setup options

## Lightweight Docker setup

Docker Desktop works on Windows, macOS, and Linux. The default setup uses
Google AI Studio for answers, so it starts only the app; no database or large
local model is downloaded locally.

1. Copy `.env.example` to `.env`.
2. Set `GEMINI_API_KEY` in `.env`.
3. Configure the S3 bucket settings below and provide AWS credentials through
   the standard boto3 credential chain.
4. Run from this folder:

   ```bash
   docker compose up -d --build
   ```

4. Open http://localhost:8501.

Stop the app with `docker compose down`. Database records remain in the Docker
volume. Embeddings are generated locally without downloading an embedding
model.

The Docker defaults can be changed in `.env`:

```dotenv
VECTOR_STORE=mongodb
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
AWS_REGION=ap-south-1
AWS_S3_BUCKET=your-pdf-bucket
AWS_S3_PREFIX=documents
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

## S3 document storage

The UI uploads PDFs directly to `AWS_S3_BUCKET/AWS_S3_PREFIX`. It then lists
the PDFs in that prefix; selecting one downloads it into memory for the
existing extraction, chunking, embedding, and vector-database workflow. No
temporary upload file or local `datasets/` selection is used by the app.

Create the bucket before starting the app, then configure:

```dotenv
AWS_REGION=ap-south-1
AWS_S3_BUCKET=your-pdf-bucket
AWS_S3_PREFIX=documents
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

You may set `AWS_S3_BUCKET_URL` instead of `AWS_S3_BUCKET` when you have a
full `s3://` or HTTPS bucket URL. The upload is verified with `head_object`,
and the same prefix is used when listing PDFs for ingestion.

For local development, boto3 can use `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` in the environment, an AWS profile, or an IAM role.
For Docker or production, prefer an IAM role/task role instead of putting
long-lived access keys in `.env`.

The application needs these minimum permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::your-pdf-bucket",
      "Condition": {"StringLike": {"s3:prefix": ["documents", "documents/*"]}}
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::your-pdf-bucket/documents/*"
    }
  ]
}
```

The Streamlit server is configured with `maxUploadSize = 30`, and the
application validates the size again before uploading and downloading.

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

## CI/CD deployment to AWS EC2

The workflow in `.github/workflows/docker-publish.yml` validates pull requests,
publishes the Docker image on pushes to `main`, and deploys the existing Compose
application to the EC2 instance. Configure these GitHub repository secrets:

```text
EC2_HOST       Public DNS name or IP address
EC2_USER       EC2 login user, such as ubuntu
EC2_SSH_KEY    Private SSH key for the instance
EC2_APP_DIR    Existing project directory on the instance
```

Keep the production `.env` only on the EC2 instance. The deployment runs
`git pull --ff-only`, then `docker compose up -d --build`; it does not replace
the instance environment file or Docker volumes.

## Detailed workflow documentation

The exact code-level RAG trace, SQL, prompt template, implemented limitations,
and separate recommendations are documented in
[`RAG_WORKFLOW.md`](RAG_WORKFLOW.md).
