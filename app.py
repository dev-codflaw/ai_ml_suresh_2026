"""Simple Streamlit UI for PDF search and question answering."""

import streamlit as st

from db import check_database_connection
from embeddings import get_embedding
from ingestion import ingest_document
from llm import check_llm_connection, generate_answer, get_llm_label
from s3_storage import (
    MAX_UPLOAD_SIZE_BYTES,
    check_s3_connection,
    download_pdf,
    list_documents,
    upload_pdf,
)
from vector_store import get_vector_store_label, similarity_search


MAX_UPLOAD_SIZE_MB = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)


def show_ingestion_summary(result: dict) -> None:
    """Show a compact summary after a document is ingested."""
    st.success(f"Document ready — {len(result['chunks'])} chunks saved.")
    with st.expander("Document details"):
        st.write(f"**File:** {result['document_name']}")
        st.write(f"**Embedding size:** {result['embedding_dimension']}")
        st.text_area("Extracted text preview", result["text"][:3000], height=140)


@st.cache_data(ttl=5, show_spinner=False)
def get_service_status() -> tuple[tuple[bool, str], tuple[bool, str], tuple[bool, str]]:
    """Check services frequently so status changes appear quickly."""
    return check_database_connection(), check_llm_connection(), check_s3_connection()


def show_service_status(llm_label: str, vector_store_label: str) -> None:
    """Show compact connection status for the database, LLM, and S3."""
    (
        (database_ok, database_message),
        (llm_ok, llm_message),
        (s3_ok, s3_message),
    ) = get_service_status()

    left, middle, right = st.columns(3)
    with left:
        st.caption(f"Database · {vector_store_label}")
        if database_ok:
            st.success("Connected", icon="✅")
        else:
            st.error(database_message, icon="❌")
    with middle:
        st.caption(f"LLM · {llm_label}")
        if llm_ok:
            st.success("Connected", icon="✅")
        else:
            st.error(llm_message, icon="❌")
    with right:
        st.caption("Document storage · Amazon S3")
        if s3_ok:
            st.success("Connected", icon="✅")
        else:
            st.error(s3_message, icon="❌")


@st.cache_data(ttl=5, show_spinner=False)
def get_s3_documents() -> list[dict]:
    """Load the current PDF list from S3."""
    return list_documents()


def format_document_option(key: str | None, documents_by_key: dict[str, dict]) -> str:
    """Format an S3 object for the document select box."""
    if key is None:
        return "Choose an uploaded PDF"
    document = documents_by_key[key]
    size_mb = document["size"] / (1024 * 1024)
    return f"{document['name']} ({size_mb:.2f} MB)"


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
    st.caption("Upload a PDF to S3, search it, and ask a question.")

    st.subheader("Connection status")
    show_service_status(llm_label, vector_store_label)

    st.subheader("1. Upload a document to S3")
    st.caption(f"PDF only · maximum size {MAX_UPLOAD_SIZE_MB} MB")
    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])

    if st.button("Upload to S3", type="primary"):
        if uploaded_file is None:
            st.warning("Choose a PDF first.")
        elif uploaded_file.size > MAX_UPLOAD_SIZE_BYTES:
            st.error(f"PDF files must be {MAX_UPLOAD_SIZE_MB} MB or smaller.")
        else:
            with st.status("Uploading document...", expanded=True) as progress:
                try:
                    progress.write("Uploading the PDF to S3...")
                    uploaded = upload_pdf(uploaded_file.name, uploaded_file.getvalue())
                    if not uploaded["verified"]:
                        raise RuntimeError("S3 upload verification failed.")
                    st.session_state["selected_s3_key"] = uploaded["key"]
                    progress.update(
                        label="Upload complete",
                        state="complete",
                        expanded=False,
                    )
                    get_s3_documents.clear()
                    st.session_state["upload_message"] = (
                        f"{uploaded['name']} uploaded to S3."
                    )
                    st.rerun()
                except Exception as error:
                    progress.update(
                        label="Upload failed",
                        state="error",
                        expanded=True,
                    )
                    show_operation_error("S3 upload", error)

    upload_message = st.session_state.pop("upload_message", None)
    if upload_message:
        st.success(upload_message)

    try:
        documents = get_s3_documents()
    except Exception as error:
        documents = []
        show_operation_error("Loading S3 documents", error)

    st.subheader("2. Uploaded documents")
    documents_by_key = {document["key"]: document for document in documents}
    document_keys = [None, *documents_by_key]
    selected_key = st.session_state.get("selected_s3_key")
    if selected_key not in documents_by_key:
        selected_key = None
    selected_key = st.selectbox(
        "Select a document to ingest",
        document_keys,
        index=document_keys.index(selected_key),
        format_func=lambda key: format_document_option(key, documents_by_key),
    )
    st.session_state["selected_s3_key"] = selected_key

    if st.button("Ingest selected document", disabled=selected_key is None):
        document = documents_by_key[selected_key]
        with st.status("Ingesting document...", expanded=True) as progress:
            try:
                progress.write("Downloading the PDF from S3...")
                pdf_bytes = download_pdf(selected_key)
                progress.write("Reading the PDF and creating chunks...")
                result = ingest_document(pdf_bytes, document_name=document["name"])
                progress.write("Saving the chunks to the database...")
                st.session_state["ingestion_result"] = result
                st.session_state["retrieved_chunks"] = []
                st.session_state["retrieved_question"] = ""
                st.session_state["retrieval_complete"] = False
                st.session_state["generated_answer"] = None
                st.session_state["answer_question"] = ""
                progress.update(
                    label="Document ingested",
                    state="complete",
                    expanded=False,
                )
            except Exception as error:
                progress.update(
                    label="Ingestion failed",
                    state="error",
                    expanded=True,
                )
                show_operation_error("Document ingestion", error)

    result = st.session_state.get("ingestion_result")
    if result is not None:
        show_ingestion_summary(result)

    st.divider()
    st.subheader("3. Search the document")
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

            st.subheader("4. Ask the LLM")
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
