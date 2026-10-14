"""Streamlit UI for the small, step-by-step RAG example."""

import tempfile
from pathlib import Path

import streamlit as st

from db import check_database_connection
from embeddings import get_embedding
from ingestion import ingest_document
from llm import check_llm_connection, generate_answer, get_llm_label
from vector_store import get_vector_store_label, similarity_search


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


@st.cache_data(ttl=30, show_spinner=False)
def get_service_status() -> tuple[tuple[bool, str], tuple[bool, str]]:
    """Check services once every 30 seconds while the UI is rerunning."""
    return check_database_connection(), check_llm_connection()


def show_service_status(llm_label: str, vector_store_label: str) -> None:
    """Show clear service names and configuration/connection alerts."""
    (database_ok, database_message), (llm_ok, llm_message) = get_service_status()

    database_status = st.success if database_ok else st.error
    llm_status = st.success if llm_ok else st.error

    left, right = st.columns(2)
    with left:
        st.markdown(f"**Database**  \n{vector_store_label}")
        database_status(database_message)
    with right:
        st.markdown(f"**LLM**  \n{llm_label}")
        llm_status(llm_message)


def show_operation_error(operation: str, error: Exception) -> None:
    """Show a friendly connection error and keep technical details available."""
    st.error(
        f"Application connection failed during {operation}. "
        "Check the service status above and try again."
    )
    with st.expander("Technical details"):
        st.code(str(error))


def main() -> None:
    st.set_page_config(page_title="Simple RAG", page_icon="📚")
    st.title("Simple RAG Demo")
    llm_label = get_llm_label()
    vector_store_label = get_vector_store_label()
    st.caption("PDF → chunks → embeddings → vector database")
    show_service_status(llm_label, vector_store_label)

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
            with st.status("Ingesting document...", expanded=True) as progress:
                try:
                    progress.write("Extracting text and creating chunks...")
                    result = ingest_document(source_path)
                    progress.write("Embeddings created and saved to the vector database.")
                    st.session_state["ingestion_result"] = result
                    st.session_state["retrieved_chunks"] = []
                    st.session_state["retrieved_question"] = ""
                    st.session_state["generated_answer"] = None
                    st.session_state["answer_question"] = ""
                    progress.update(
                        label=f"Ingestion complete — saved {len(result['chunks'])} chunks",
                        state="complete",
                        expanded=False,
                    )
                    st.success(
                        f"Saved {len(result['chunks'])} chunks to {vector_store_label}."
                    )
                except Exception as error:
                    progress.update(
                        label="Application connection failed during ingestion",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error("document ingestion", error)
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
            st.session_state["retrieved_chunks"] = []
            st.session_state["retrieved_question"] = ""
            st.session_state["generated_answer"] = None
            st.session_state["answer_question"] = ""
            with st.status("Retrieving similar chunks...", expanded=True) as progress:
                try:
                    progress.write("Creating the question embedding...")
                    question_embedding = get_embedding(question)
                    progress.write("Searching the vector database...")
                    st.session_state["retrieved_chunks"] = similarity_search(
                        question_embedding,
                        top_k=5,
                    )
                    st.session_state["retrieved_question"] = question
                    result_count = len(st.session_state["retrieved_chunks"])
                    progress.update(
                        label=f"Retrieval complete — found {result_count} chunks",
                        state="complete",
                        expanded=False,
                    )
                    if not result_count:
                        st.info("No matching chunks were found.")
                except Exception as error:
                    progress.update(
                        label="Application connection failed during retrieval",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error("chunk retrieval", error)

    retrieved_chunks = st.session_state.get("retrieved_chunks", [])
    retrieved_question = st.session_state.get("retrieved_question", "")
    if retrieved_chunks and retrieved_question == question:
        st.subheader("Step 7: Retrieved chunks")
        for number, chunk in enumerate(retrieved_chunks, start=1):
            st.info(
                f"Chunk {number} | similarity: {chunk['similarity']:.3f}\n\n"
                f"{chunk['chunk_text']}"
            )

        if st.button("Ask LLM", type="primary"):
            st.session_state["generated_answer"] = None
            st.session_state["answer_question"] = ""
            with st.status(f"Generating answer with {llm_label}...", expanded=True) as progress:
                try:
                    progress.write(f"Sending the question and retrieved context to {llm_label}...")
                    answer = generate_answer(question, retrieved_chunks)
                    st.session_state["generated_answer"] = answer
                    st.session_state["answer_question"] = question
                    progress.update(
                        label=f"Answer generated by {llm_label}",
                        state="complete",
                        expanded=False,
                    )
                except Exception as error:
                    progress.update(
                        label=f"Application connection failed while contacting {llm_label}",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error(f"{llm_label} response generation", error)

        answer = st.session_state.get("generated_answer")
        if answer is not None and st.session_state.get("answer_question") == question:
            st.subheader("Step 9: Final answer")
            st.caption(f"Response from: {llm_label}")
            st.write(answer)


if __name__ == "__main__":
    main()
