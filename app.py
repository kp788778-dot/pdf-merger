import streamlit as st
from pypdf import PdfMerger
from zipfile import ZipFile
from io import BytesIO
from pathlib import Path
import tempfile
import os


st.set_page_config(
    page_title="PDF Merger",
    page_icon="",
    layout="centered"
)

st.title("PDF Merger")
st.write("Upload a ZIP file containing PDFs to combine them into one document.")

uploaded_zip = st.file_uploader(
    "Upload ZIP File",
    type=["zip"]
)

output_name = st.text_input(
    "Output PDF Name",
    value="combined_document.pdf"
)

if uploaded_zip is not None:

    if st.button("Merge PDFs"):

        with st.spinner("Processing PDFs..."):

            try:
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:

                    zip_path = os.path.join(temp_dir, "uploaded.zip")

                    # Save uploaded zip temporarily
                    with open(zip_path, "wb") as f:
                        f.write(uploaded_zip.getbuffer())

                    # Extract zip
                    with ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)

                    # Find all PDFs recursively
                    pdf_files = sorted(
                        Path(temp_dir).rglob("*.pdf")
                    )

                    if not pdf_files:
                        st.error("No PDF files found in ZIP.")
                        st.stop()

                    merger = PdfMerger()

                    st.write("### PDFs Added In Order:")

                    for pdf in pdf_files:
                        st.write(f"• {pdf.name}")
                        merger.append(str(pdf))

                    # Save merged PDF to memory
                    output_buffer = BytesIO()
                    merger.write(output_buffer)
                    merger.close()

                    output_buffer.seek(0)

                    st.success("PDFs merged successfully!")

                    st.download_button(
                        label="⬇ Download Merged PDF",
                        data=output_buffer,
                        file_name=output_name,
                        mime="application/pdf"
                    )

            except Exception as e:
                st.error(f"Error: {e}")
