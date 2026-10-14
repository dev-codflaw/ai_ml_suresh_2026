# Exact Implemented RAG Workflow

This document describes only behavior that exists in this repository. The
main entry point is `app.py`, which calls the ingestion, embedding, database,
and Ollama modules.

## 1. Document ingestion

- **Python file/functions:** `app.py` → `main()`; uploaded files are passed
  through `save_uploaded_pdf()`, and both uploaded and dataset paths are then
  passed to `ingestion.py` → `ingest_document(file_path)`.
- **Package/library:** `streamlit`, `tempfile`, and `pathlib.Path`.
- **Configuration:** No environment variable controls ingestion.
- **Input:** Either the file selected by `st.file_uploader(..., type=["pdf"])`
  or a file selected from `datasets/*.pdf`.
- **Processing:** `save_uploaded_pdf()` writes the uploaded bytes to a
  temporary file with a `.pdf` suffix. After ingestion, `app.py` deletes that
  temporary path with `unlink(missing_ok=True)`.
- **Output:** `ingest_document()` returns a dictionary containing
  `document_name`, extracted `text`, `chunks`, `embedding_dimension`, and
  `example_embedding`. `app.py` stores it in
  `st.session_state["ingestion_result"]` and resets
  `st.session_state["retrieved_chunks"]`.
- **Next:** The selected path is passed to `extract_text()`.

TXT ingestion is **not currently implemented**. The UI accepts only PDF files,
the dataset selector searches only for `*.pdf`, and the ingestion module uses
PyMuPDF to open a PDF.

## 2. PDF/TXT text extraction

- **Python file/functions:** `ingestion.py` → `load_pdf(file_path)` and
  `extract_text(file_path)`.
- **Package/library:** `fitz` from `PyMuPDF`.
- **Input:** The path passed to `ingest_document()`.
- **Processing:** `load_pdf()` calls `fitz.open(str(file_path))`. Inside the
  document context, `extract_text()` calls `page.get_text("text")` for every
  page and joins the page strings with `"\n"`.
- **Output:** One plain-text string. `ingest_document()` strips whitespace and
  raises `ValueError("The PDF does not contain readable text.")` if empty.
- **Next:** The stripped string goes to `create_chunks(text)`.

There is no TXT reader, encoding selection, OCR fallback, page metadata
capture, or table/image extraction path.

## 3. Document chunking

- **Python file/function:** `ingestion.py` → `create_chunks(text)`.
- **Package/library:** `langchain_text_splitters.RecursiveCharacterTextSplitter`.
- **Input:** The complete extracted PDF text.
- **Processing:** The function creates a splitter with `chunk_size=800` and
  `chunk_overlap=100`, then calls `split_text(text)`. Other splitter settings
  use the library defaults.
- **Output:** A `list[str]` of overlapping text chunks.
- **Next:** `ingest_document()` embeds every chunk, starting with the first.

## 4. Embedding generation

- **Python file/functions:** `embeddings.py` → `get_embeddings(texts)` and
  `get_embedding(text)`.
- **Package/library:** Python standard library (`hashlib`, `math`, and `re`).
- **Vectorizer:** A stable hashing vectorizer with 384 dimensions.
- **Input:** Each document chunk during ingestion and the user question during
  retrieval.
- **Processing:** Each word and short character n-gram is hashed into one of
  384 positions. The resulting vector is L2-normalized, and the same
  deterministic process is used for documents and questions.
- **Output:** A list of floating-point values. The expected dimension is 384;
  the UI also reports `len(first_embedding)`.
- **Next:** Document vectors go to `save_chunk()`; the question vector goes to
  `similarity_search()`.

Vectors are generated locally by the Python standard library. No embedding
package, model download, API, or remote embedding endpoint is used.

## 5. Vector database storage

- **Python files/functions:** `vector_store.py` → `create_table()` and
  `save_chunk()`; `db.py` → `get_connection()`.
- **Database/library:** PostgreSQL with the `pgvector` extension, accessed with
  `psycopg`/`psycopg-binary`.
- **Configuration:** `db.py` loads `.env` using `python-dotenv` and reads
  `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.
- **Table:** `vector_embeddings`.
- **Vector column:** `embedding vector(384)`.
- **Schema created by the code:**

  ```sql
  CREATE TABLE IF NOT EXISTS vector_embeddings (
      id SERIAL PRIMARY KEY,
      source TEXT NOT NULL,
      document_name TEXT NOT NULL,
      chunk_text TEXT NOT NULL,
      embedding vector(384) NOT NULL
  );
  ```

  `create_table()` also runs `CREATE EXTENSION IF NOT EXISTS vector` and
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for the four data columns. It
  does not create a vector index.
- **Input:** `document_name`, one chunk string, and its 384-value embedding.
- **Processing:** `save_chunk()` executes:

  ```sql
  INSERT INTO vector_embeddings
      (source, document_name, chunk_text, embedding)
  VALUES (%s, %s, %s, %s::vector)
  ```

  Both `source` and `document_name` receive the file basename.
- **Output:** One persisted row; PostgreSQL generates `id` using `SERIAL`.
- **Next:** Rows are searched by `similarity_search()`.

Metadata stored for every chunk is the generated integer `id`, source basename,
document basename, chunk text, and embedding vector. There is no separate
document ID, page number, chunk index, timestamp, checksum, or source URI.

Duplicate handling is **not implemented**. There is no unique constraint,
deduplication check, delete-before-reinsert operation, or upsert. Ingesting the
same PDF repeatedly inserts another set of rows. Chunk IDs are database-
generated sequential `SERIAL` values; document IDs and deterministic chunk IDs
do not exist.

## 6. User question/query input

- **Python file/function:** `app.py` → `main()`.
- **Package/library:** `streamlit`.
- **Input:** `st.text_input("Question")`, read when the user clicks
  `Step 6: Retrieve similar chunks`.
- **Processing:** Blank or whitespace-only questions produce a warning.
  Otherwise, the question is passed directly to `get_embedding()`.
- **Output:** Retrieved chunk dictionaries are stored in
  `st.session_state["retrieved_chunks"]`.
- **Next:** The list is displayed and can be passed to
  `generate_answer(question, retrieved_chunks)`.

## 7. Query embedding generation

- **Python file/functions:** `app.py` → `main()` calls `embeddings.py` →
  `get_embedding(question)`.
- **Package/model:** The same local 384-dimensional hashing vectorizer used
  for document chunks.
- **Input:** Non-empty text from `st.text_input("Question")`.
- **Processing/output:** The same deterministic vectorizer produces a
  384-dimensional Python list.
- **Next:** The list is passed to
  `vector_store.similarity_search(question_embedding, top_k=5)`.

## 8. Vector similarity search

- **Python file/function:** `vector_store.py` →
  `similarity_search(query_embedding, top_k=5)`.
- **Database:** PostgreSQL with pgvector, through `psycopg`.
- **Metric:** Cosine distance using pgvector's `<=>` operator. The returned
  `similarity` field is calculated as `1 - cosine_distance`.
- **Exact SQL:**

  ```sql
  SELECT id, document_name, chunk_text,
         1 - (embedding <=> %s::vector) AS similarity
  FROM vector_embeddings
  WHERE embedding IS NOT NULL AND chunk_text IS NOT NULL
  ORDER BY embedding <=> %s::vector
  LIMIT %s
  ```

- **Top-k:** `5`, supplied by `app.py`.
- **Threshold:** None. Results are returned regardless of similarity value.
- **Filters:** Only `embedding IS NOT NULL` and `chunk_text IS NOT NULL`. No
  document, source, tenant, or metadata filter is applied.
- **Output:** Each result becomes a dictionary with `id`, `document_name`,
  `chunk_text`, and `similarity`.
- **Ordering:** PostgreSQL orders by ascending cosine distance, and the Python
  list preserves that order.
- **Next:** The list is displayed by `app.py`. The user can click the nearby
  `Ask LLM` button to pass the retrieved chunks to `generate_answer()`.

## 9. Retrieved chunks/context construction

- **Python file/function:** There is no separate context-builder function.
  Context is constructed inside `llm.py` →
  `generate_answer(question, context_chunks)`.
- **Input:** The ordered dictionaries returned by `similarity_search()`.
- **Processing:** Only each `chunk_text` is used. IDs, document names, and
  similarity values are not included in the LLM context. The chunks are joined
  with two newlines and labeled sequentially.
- **Output/context format:**

  ```text
  Chunk 1:
  <chunk_text>

  Chunk 2:
  <chunk_text>
  ```

- **Next:** This context string is interpolated into the LLM prompt.

## 10. Prompt sent to the LLM

- **Python file/function:** `llm.py` → `generate_answer()`.
- **Provider/endpoint:** Ollama HTTP API at
  `{OLLAMA_URL.rstrip('/')}/api/generate`.
- **Configuration:** `OLLAMA_URL` defaults to `http://localhost:11434` and
  `OLLAMA_MODEL` defaults to `llama3.2:3b`; both are loaded from `.env`.
- **Exact prompt template:**

  ```text
  Answer the question using only the context below.
  If the answer is not in the context, say: "I do not know based on the provided document."
  Do not use outside knowledge.

  Question:
  {question}

  Context:
  {context}
  ```

- **System prompt:** None. One `prompt` string is sent; no separate system
  message is constructed.
- **Request settings:** `model=OLLAMA_MODEL`, the constructed `prompt`,
  `stream=False`, and an HTTP `timeout=120` seconds. No temperature, top-p,
  seed, stop sequence, or other generation setting is supplied.
- **Next:** Ollama returns JSON that is parsed by `generate_answer()`.

## 11. LLM response generation

- **Model:** The Ollama model configured by `OLLAMA_MODEL`, default
  `llama3.2:3b`.
- **Execution:** `requests.post()` sends the request to the local Ollama
  server. The application does not call a hosted LLM provider directly.
- **Error handling:** A non-2xx response raises `RuntimeError` containing the
  HTTP status and response detail. `app.py` catches it and displays
  `Ollama request failed: ...`.
- **Output:** On success, the code reads `response.json()["response"]` and
  returns `.strip()` as a plain string.
- **Next:** `app.py` displays the string immediately below the `Ask LLM`
  button under `Step 9: Final answer`; the response is not hidden in an
  expander.

## 12. Structured output

**Not currently implemented.** The request asks for ordinary generated text,
and `generate_answer()` returns only the stripped value of the JSON `response`
field. There is no schema, JSON-mode request, Pydantic model, function/tool
call, or structured parser.

## 13. Hallucination/grounding handling

The only grounding behavior is the prompt instruction in `llm.py` to:

- answer using only the supplied context;
- return the exact fallback sentence
  `I do not know based on the provided document.` when the answer is absent;
- not use outside knowledge.

There is no programmatic hallucination detector, confidence score, similarity
threshold, answer verification step, citation insertion, source/page citation
handling, or post-generation grounding check. The UI displays each retrieved
chunk's `document_name` and similarity, but those values are not included in
the LLM context.

## 14. RAG evaluation and test cases

**Not currently implemented.** There are no test files, evaluation scripts,
test dataset, ground-truth question/answer pairs, retrieval tests, response
quality tests, evaluation framework, or measured metrics. The PDFs under
`datasets/` are ingestion inputs, not an evaluation set.

## Low-level workflow

```text
DOCUMENT INGESTION

PDF
↓
[app.py: main() / save_uploaded_pdf(); Streamlit uploader or datasets/*.pdf]
Text Extraction
↓
[ingestion.py: extract_text() / load_pdf(); PyMuPDF (fitz), page.get_text("text")]
Chunking
↓
[ingestion.py: create_chunks(); RecursiveCharacterTextSplitter, chunk size 800, overlap 100]
Embedding
↓
[embeddings.py: get_embedding(); local hashing vectorizer, 384 dimensions]
Vector Database
↓
[PostgreSQL + pgvector; vector_embeddings.embedding vector(384)]
```

```text
QUERY / RETRIEVAL

User Question
↓
[app.py: main(); Streamlit st.text_input("Question")]
Query Embedding
↓
[embeddings.py: get_embedding(); same local hashing vectorizer]
Similarity Search
↓
[vector_store.py: similarity_search(); cosine distance (<=>), ORDER BY distance, LIMIT 5]
Retrieved Chunks
↓
[llm.py: generate_answer(); joins chunk_text as Chunk 1, Chunk 2, etc.]
LLM Prompt
↓
[Ollama /api/generate; OLLAMA_MODEL, default llama3.2:3b]
Generated Answer
```

```text
EVALUATION

Question + Expected Answer
↓
Retrieval Evaluation
Not currently implemented.
```

## Suggested additions (not part of the current implementation)

- Add TXT support with an explicit text-file loader and UI type choice.
- Add a stable document fingerprint and unique constraint, then make ingestion
  idempotent instead of inserting duplicates.
- Store page number, chunk index, and source path so answers can provide
  citations.
- Add a pgvector index, configurable similarity threshold, and optional
  source/document filters for larger or multi-document collections.
- Include source metadata and similarity in the LLM context or answer contract
  if citations are required.
- Add structured output validation and a post-generation check that flags
  answers unsupported by retrieved context.
- Add retrieval fixtures and end-to-end tests with expected chunks, questions,
  answers, and metrics such as recall@k and answer groundedness.
