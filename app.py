import streamlit as st
import zipfile
import io
from collections import defaultdict
from pypdf import PdfWriter, PdfReader

st.set_page_config(page_title="PDF Folder Merger", page_icon="📄", layout="centered")

st.title("📄 PDF Folder Merger")
st.markdown(
    "Upload a **ZIP file** containing folders of PDFs. "
    "Each folder's PDFs will be merged into one PDF named after that folder."
)

def get_pdf_groups(zip_file: zipfile.ZipFile) -> dict[str, list[str]]:
    """
    Walk the zip and group PDF paths by their immediate parent folder.
    Handles both flat (folder/file.pdf) and nested (outer/folder/file.pdf) structures.
    Returns dict of {folder_name: [sorted list of zip member paths]}.
    """
    groups: dict[str, list[str]] = defaultdict(list)

    for name in zip_file.namelist():
        # Skip directories themselves and non-pdf files
        if name.endswith("/"):
            continue
        if not name.lower().endswith(".pdf"):
            continue

        parts = name.split("/")
        # The immediate parent folder of the PDF
        if len(parts) < 2:
            # PDF at the root of the zip — group under "Root"
            folder = "Root"
        else:
            folder = parts[-2]  # immediate parent directory name

        groups[folder].append(name)

    # Sort files within each group to preserve original order
    for folder in groups:
        groups[folder].sort()

    return dict(groups)


def merge_pdfs(zip_file: zipfile.ZipFile, pdf_paths: list[str]) -> bytes:
    """Merge the given list of PDF paths from the zip into a single PDF bytes object."""
    writer = PdfWriter()
    for path in pdf_paths:
        with zip_file.open(path) as f:
            data = io.BytesIO(f.read())
            reader = PdfReader(data)
            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


# ── Upload widget ──────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Drop your ZIP file here, or click to browse",
    type=["zip"],
    label_visibility="collapsed",
)

if uploaded_file is not None:
    st.success(f"✅ Loaded **{uploaded_file.name}**")

    with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
        groups = get_pdf_groups(zf)

        if not groups:
            st.error("No PDF files were found inside the ZIP.")
        else:
            st.markdown(f"Found **{len(groups)}** folder(s) containing PDFs:")

            # ── Process and display download buttons ───────────────────────────
            for folder_name, pdf_paths in sorted(groups.items()):
                with st.spinner(f"Merging {len(pdf_paths)} PDF(s) in **{folder_name}**…"):
                    merged_bytes = merge_pdfs(zf, pdf_paths)

                output_filename = f"{folder_name}.pdf"

                col1, col2 = st.columns([3, 2])
                with col1:
                    st.markdown(
                        f"**{folder_name}** &nbsp;·&nbsp; "
                        f"<span style='color:grey'>{len(pdf_paths)} file(s) merged</span>",
                        unsafe_allow_html=True,
                    )
                    # Show the individual files that were merged
                    with st.expander("Files included (in order)"):
                        for p in pdf_paths:
                            st.text(p.split("/")[-1])
                with col2:
                    st.download_button(
                        label=f"⬇ Download {output_filename}",
                        data=merged_bytes,
                        file_name=output_filename,
                        mime="application/pdf",
                        key=folder_name,
                    )

                st.divider()

st.markdown(
    "<br><p style='text-align:center;color:grey;font-size:0.8em'>"
    "Files are processed entirely in-memory and never stored on any server."
    "</p>",
    unsafe_allow_html=True,
)
