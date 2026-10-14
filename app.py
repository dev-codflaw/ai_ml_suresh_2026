"""Simple Streamlit UI for PDF search and question answering."""

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


def show_ingestion_summary(result: dict) -> None:
    """Show a compact summary after a document is ingested."""
    st.success(f"Document ready — {len(result['chunks'])} chunks saved.")
    with st.expander("Document details"):
        st.write(f"**File:** {result['document_name']}")
        st.write(f"**Embedding size:** {result['embedding_dimension']}")
        st.text_area("Extracted text preview", result["text"][:3000], height=140)


@st.cache_data(ttl=5, show_spinner=False)
def get_service_status() -> tuple[tuple[bool, str], tuple[bool, str]]:
    """Check services frequently so status changes appear quickly."""
    return check_database_connection(), check_llm_connection()


def show_service_status(llm_label: str, vector_store_label: str) -> None:
    """Show compact connection status for the database and LLM."""
    (database_ok, database_message), (llm_ok, llm_message) = get_service_status()

    left, right = st.columns(2)
    with left:
        st.caption(f"Database · {vector_store_label}")
        if database_ok:
            st.success("Connected", icon="✅")
        else:
            st.error(database_message, icon="❌")
    with right:
        st.caption(f"LLM · {llm_label}")
        if llm_ok:
            st.success("Connected", icon="✅")
        else:
            st.error(llm_message, icon="❌")


def show_operation_error(operation: str, error: Exception) -> None:
    """Show one short error with optional technical details."""
    st.error(f"{operation} failed. Check the connection status and try again.")
    with st.expander("Technical details"):
        st.code(str(error))


def main() -> None:
    st.set_page_config(page_title="PDF Question Answering", page_icon="📚")
    st.title("PDF Question Answering")
    llm_label = get_llm_label()
    vector_store_label = get_vector_store_label()
    st.caption("Add a PDF, search it, and ask a question.")

    st.subheader("Connection status")
    show_service_status(llm_label, vector_store_label)

    st.subheader("1. Add a document")
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
    existing_pdfs = sorted(DATASET_DIR.glob("*.pdf"))
    selected_pdf = st.selectbox(
        "Or select an existing PDF",
        [None] + existing_pdfs,
        format_func=lambda path: "Choose a PDF" if path is None else path.name,
    )

    if st.button("Save document", type="primary"):
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
            with st.status("Saving document...", expanded=True) as progress:
                try:
                    progress.write("Reading the PDF and creating chunks...")
                    result = ingest_document(source_path)
                    progress.write("Saving the chunks to the database...")
                    st.session_state["ingestion_result"] = result
                    st.session_state["retrieved_chunks"] = []
                    st.session_state["retrieved_question"] = ""
                    st.session_state["retrieval_complete"] = False
                    st.session_state["generated_answer"] = None
                    st.session_state["answer_question"] = ""
                    progress.update(
                        label="Document saved",
                        state="complete",
                        expanded=False,
                    )
                except Exception as error:
                    progress.update(
                        label="Document save failed",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error("Document save", error)
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)

    result = st.session_state.get("ingestion_result")
    if result is not None:
        show_ingestion_summary(result)

    st.divider()
    st.subheader("2. Search the document")
    question = st.text_input(
        "Enter your question",
        placeholder="For example: What is this document about?",
    )

    if st.button("Search", type="primary"):
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            st.session_state["retrieved_chunks"] = []
            st.session_state["retrieved_question"] = ""
            st.session_state["retrieval_complete"] = False
            st.session_state["generated_answer"] = None
            st.session_state["answer_question"] = ""
            with st.status("Searching...", expanded=True) as progress:
                try:
                    progress.write("Preparing the question...")
                    question_embedding = get_embedding(question)
                    progress.write("Searching the database...")
                    st.session_state["retrieved_chunks"] = similarity_search(
                        question_embedding,
                        top_k=5,
                    )
                    st.session_state["retrieved_question"] = question.strip()
                    st.session_state["retrieval_complete"] = True
                    progress.update(
                        label="Search complete",
                        state="complete",
                        expanded=False,
                    )
                except Exception as error:
                    progress.update(
                        label="Search failed",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error("Search", error)

    retrieved_chunks = st.session_state.get("retrieved_chunks", [])
    retrieved_question = st.session_state.get("retrieved_question", "")
    retrieval_complete = st.session_state.get("retrieval_complete", False)
    if retrieval_complete and retrieved_question == question.strip():
        if retrieved_chunks:
            st.success(f"Search complete — found {len(retrieved_chunks)} matching chunks.")
        else:
            st.warning("Search complete — no matching chunks were found.")

        if retrieved_chunks:
            st.subheader("Search results")
            with st.expander(f"Show {len(retrieved_chunks)} matching chunks"):
                for number, chunk in enumerate(retrieved_chunks, start=1):
                    st.markdown(
                        f"**Chunk {number} · similarity {chunk['similarity']:.3f}**"
                    )
                    st.write(chunk["chunk_text"])

            st.subheader("3. Ask the LLM")
            if st.button("Ask LLM"):
                st.session_state["generated_answer"] = None
                st.session_state["answer_question"] = ""
                with st.status("Generating answer...", expanded=True) as progress:
                    try:
                        progress.write(f"Sending the question to {llm_label}...")
                        answer = generate_answer(question, retrieved_chunks)
                        st.session_state["generated_answer"] = answer
                        st.session_state["answer_question"] = question.strip()
                        progress.update(
                            label="Answer complete",
                            state="complete",
                            expanded=False,
                        )
                    except Exception as error:
                        progress.update(
                            label="Answer failed",
                            state="error",
                            expanded=True,
                        )
                        show_operation_error("LLM response", error)

        answer = st.session_state.get("generated_answer")
        if answer is not None and st.session_state.get("answer_question") == question.strip():
            st.success("Answer ready.")
            st.subheader("Answer")
            st.write(answer)


if __name__ == "__main__":
    main()
