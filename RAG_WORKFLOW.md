# Exact Implemented RAG Workflow

The application implements this flow:

```text
S3 PDF → text → chunks → local vectors → MongoDB Atlas Vector Search → LLM answer
```

MongoDB Atlas and Gemini are the lightweight defaults. Ollama remains an
optional local LLM provider.

## 1. Document ingestion

`app.py` uploads PDFs to the configured S3 bucket and lists the PDFs under the
configured prefix. The selected object is downloaded into memory and passed to
`ingestion.py`, which then:

1. Extracts text from every page with PyMuPDF.
2. Splits the text into overlapping chunks of about 800 characters.
3. Generates deterministic 384-dimensional vectors locally.
4. Creates the Atlas vector index when needed.
5. Inserts all chunks into the configured MongoDB collection.

TXT files, OCR, page metadata, table extraction, and image extraction are not
implemented.

## 2. Embeddings

`embeddings.py` uses only the Python standard library. Words and short
character n-grams are hashed into a stable 384-dimensional normalized vector.
The same algorithm is used for document chunks and user questions, so no
embedding model download or embedding API is required.

## 3. MongoDB Atlas storage

The default configuration is read from `.env`:

```dotenv
VECTOR_STORE=mongodb
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_ml_vectordb
MONGODB_COLLECTION=vector_embeddings
MONGODB_INDEX_NAME=vector_index
```

Each stored document contains:

```json
{
  "source": "document.pdf",
  "document_name": "document.pdf",
  "chunk_text": "...",
  "embedding": [0.0]
}
```

The application creates a 384-dimensional cosine `vectorSearch` index on the
`embedding` field when the configured Atlas user has permission to create it.
If index creation is not permitted, create an index named `vector_index` on
`embedding` with 384 dimensions and cosine similarity in Atlas.

Duplicate handling is not implemented. Ingesting the same PDF again inserts
another set of documents.

## 4. Retrieval

When the user clicks Search, the question is converted to the same local vector
and searched with Atlas `$vectorSearch`. The application requests the top five
chunks, using at least 50 candidates. No similarity threshold or document
filter is applied.

Each result contains its MongoDB ID, document name, chunk text, and Atlas
similarity score. The retrieved chunk text is joined into the LLM context.

## 5. LLM answer generation

The default provider is Gemini through the Google AI Studio HTTP API:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta
```

The prompt instructs the model to use only the retrieved context and return:

```text
I do not know based on the provided document.
```

when the context does not contain the answer. Ollama can be selected with
`LLM_PROVIDER=ollama`; Docker starts it only when the `ollama` profile is
enabled.

## 6. Current limitations

- No TXT or OCR ingestion.
- No document deduplication or deletion UI.
- No page-level citations.
- No similarity threshold or answer verification step.
- No automated retrieval or answer evaluation suite.
- PostgreSQL support is not included in the lightweight Docker image; it can
  be added later as an optional backend.
