"""Streamlit UI for the small, step-by-step RAG example."""

import tempfile
from pathlib import Path

import streamlit as st

from embeddings import get_embedding
from ingestion import ingest_document
from llm import generate_answer
from vector_store import similarity_search


BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / "datasets"


def save_uploaded_pdf(uploaded_file) -> Path:
    """Save a Streamlit upload to a temporary PDF file."""
    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temporary_file.write(uploaded_file.getbuffer())
    temporary_file.close()
    return Path(temporary_file.name)


def show_ingestion_steps(result: dict) -> None:
    """Show the intermediate values so the RAG steps are visible."""
    st.subheader("Step 1: Extracted text")
    st.text_area("PDF text", result["text"][:5000], height=180)

    st.subheader("Step 2: Generated chunks")
    st.write(f"Created {len(result['chunks'])} chunks.")
    for number, chunk in enumerate(result["chunks"], start=1):
        with st.expander(f"Chunk {number}"):
            st.write(chunk)

    st.subheader("Step 3: Embedding")
    st.write(f"Embedding dimension: {result['embedding_dimension']}")
    st.code(str(result["example_embedding"][:10]) + " ...")


def main() -> None:
    st.set_page_config(page_title="Simple RAG", page_icon="📚")
    st.title("Simple RAG Demo")
    st.caption("PDF → chunks → embeddings → pgvector → Ollama")

    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    existing_pdfs = sorted(DATASET_DIR.glob("*.pdf"))
    selected_pdf = st.selectbox(
        "Or select an existing PDF",
        [None] + existing_pdfs,
        format_func=lambda path: "Choose a PDF" if path is None else path.name,
    )

    if st.button("Ingest document"):
        source_path = None
        temporary_path = None

        if uploaded_file is not None:
            temporary_path = save_uploaded_pdf(uploaded_file)
            source_path = temporary_path
        elif selected_pdf is not None:
            source_path = selected_pdf

        if source_path is None:
            st.warning("Upload or select a PDF first.")
        else:
            try:
                with st.spinner("Extracting, chunking, embedding, and saving..."):
                    result = ingest_document(source_path)
                st.session_state["ingestion_result"] = result
                st.session_state["retrieved_chunks"] = []
                st.success(f"Saved {len(result['chunks'])} chunks.")
            except Exception as error:
                st.error(f"Ingestion failed: {error}")
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

    result = st.session_state.get("ingestion_result")
    if result is not None:
        show_ingestion_steps(result)

    st.divider()
    st.subheader("Ask a question")
    question = st.text_input("Question")

    if st.button("Step 6: Retrieve similar chunks"):
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.spinner("Creating the question embedding and searching..."):
                    question_embedding = get_embedding(question)
                    st.session_state["retrieved_chunks"] = similarity_search(
                        question_embedding,
                        top_k=5,
                    )
            except Exception as error:
                st.error(f"Search failed: {error}")

    retrieved_chunks = st.session_state.get("retrieved_chunks", [])
    if retrieved_chunks:
        st.subheader("Step 7: Retrieved chunks")
        for number, chunk in enumerate(retrieved_chunks, start=1):
            st.info(
                f"Chunk {number} | similarity: {chunk['similarity']:.3f}\n\n"
                f"{chunk['chunk_text']}"
            )

        if st.button("Step 8: Generate answer with Ollama"):
            try:
                with st.spinner("Asking Ollama..."):
                    answer = generate_answer(question, retrieved_chunks)
                st.subheader("Step 9: Final answer")
                st.write(answer)
            except Exception as error:
                st.error(f"Ollama request failed: {error}")


if __name__ == "__main__":
    main()
