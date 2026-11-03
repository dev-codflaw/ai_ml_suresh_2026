"""Simple Streamlit UI for PDF search and question answering."""

import tempfile
from pathlib import Path

import streamlit as st

from db import check_database_connection
from embeddings import get_embedding
from ingestion import ingest_document
from s3_storage import download_pdf, list_pdfs, pdf_url, upload_pdf
from llm import check_llm_connection, generate_answer, get_llm_label
from vector_store import get_vector_store_label, similarity_search


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
    st.set_page_config(page_title="Suresh RAG PDF Question Answering", page_icon="📚")
    st.title("RAG PDF Question Answering")
    llm_label = get_llm_label()
    vector_store_label = get_vector_store_label()
    st.caption("Upload PDFs to S3, ingest a selected file, then search and ask questions.")

    st.subheader("Connection status")
    show_service_status(llm_label, vector_store_label)

    st.subheader("1. Upload and ingest documents")
    upload_column, files_column = st.columns(2)
    with upload_column:
        st.markdown("#### Upload to S3")
        uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
        if st.button("Upload to S3", type="primary"):
            if uploaded_file is None:
                st.warning("Choose a PDF first.")
            else:
                try:
                    with st.spinner("Uploading to S3..."):
                        upload_pdf(uploaded_file.name, uploaded_file.getvalue())
                    st.success("Uploaded to S3. Select it on the right to start ingestion.")
                except Exception as error:
                    show_operation_error("S3 upload", error)
        st.caption("Uploading stores the PDF in S3 only. Ingestion starts when you click the button on the right.")

    with files_column:
        st.markdown("#### PDFs in S3")
        st.button("Refresh files")
        try:
            files = list_pdfs()
        except Exception as error:
            files = []
            show_operation_error("S3 file listing", error)

        if files:
            st.dataframe(
                [{"File": Path(item["Key"]).name,
                  "Uploaded": item["LastModified"],
                  "Size (KB)": round(item["Size"] / 1024, 1)} for item in files],
                hide_index=True,
            )
            by_key = {item["Key"]: item for item in files}
            selected_key = st.selectbox(
                "Choose a PDF to ingest",
                list(by_key),
                format_func=lambda key: (
                    f"{Path(key).name} · {by_key[key]['LastModified'].isoformat()} · {key}"
                ),
            )
            try:
                st.link_button("Open selected PDF", pdf_url(selected_key))
            except Exception as error:
                show_operation_error("PDF link", error)

            if st.button("Ingest selected PDF", type="primary"):
                with st.status("Ingesting selected PDF...", expanded=True) as progress:
                    try:
                        with tempfile.TemporaryDirectory() as directory:
                            source_path = Path(directory) / Path(selected_key).name
                            progress.write("Downloading the selected PDF from S3...")
                            download_pdf(selected_key, source_path)
                            progress.write("Extracting text, creating embeddings, and saving chunks...")
                            result = ingest_document(source_path, document_name=selected_key)
                        st.session_state["ingestion_result"] = result
                        st.session_state["retrieved_chunks"] = []
                        st.session_state["retrieved_question"] = ""
                        st.session_state["retrieval_complete"] = False
                        st.session_state["generated_answer"] = None
                        st.session_state["answer_question"] = ""
                        progress.update(label="Ingestion complete", state="complete", expanded=False)
                    except Exception as error:
                        progress.update(label="Ingestion failed", state="error", expanded=True)
                        show_operation_error("Document ingestion", error)
        else:
            st.info("No PDFs to show. Upload a PDF to S3 first.")


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
