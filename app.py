import streamlit as st
import zipfile
import io
import re
from collections import defaultdict
from pypdf import PdfWriter, PdfReader

st.set_page_config(
    page_title="PDF Folder Merger",
    page_icon="📄",
    layout="centered"
)

st.title("PDF Folder Merger")

st.markdown("""
### How to use

1. Download lot folders as a ZIP.
2. Upload the ZIP below.
3. PDFs are automatically sorted numerically.
4. PDFs are merged by folder.
5. Lot numbers found in text-based PDFs are validated.
""")

# ============================================================
# CONFIG
# ============================================================

LOT_REGEX = re.compile(
    r"\b[A-Z]{1,4}-[A-Z0-9]+-\d{3,}\b",
    re.IGNORECASE
)

# ============================================================
# SORTING
# ============================================================

def pdf_sort_key(path):

    filename = path.split("/")[-1]

    match = re.match(r"^\s*(\d+)", filename)

    if match:
        return (int(match.group(1)), filename)

    return (9999, filename)

# ============================================================
# GROUP PDFS
# ============================================================

def get_pdf_groups(zip_file):

    groups = defaultdict(list)

    for name in zip_file.namelist():

        if name.endswith("/"):
            continue

        if not name.lower().endswith(".pdf"):
            continue

        parts = name.split("/")

        if len(parts) < 2:
            folder = "Root"
        else:
            folder = parts[-2]

        groups[folder].append(name)

    for folder in groups:
        groups[folder].sort(key=pdf_sort_key)

    return dict(groups)

# ============================================================
# MERGE PDFS
# ============================================================

def merge_pdfs(zip_file, pdf_paths):

    writer = PdfWriter()

    for path in pdf_paths:

        with zip_file.open(path) as f:

            reader = PdfReader(io.BytesIO(f.read()))

            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()

    writer.write(output)

    return output.getvalue()

# ============================================================
# TEXT EXTRACTION
# ============================================================

def extract_text(pdf_bytes):

    text = ""

    try:

        reader = PdfReader(io.BytesIO(pdf_bytes))

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    except Exception:
        pass

    return text

# ============================================================
# LOT EXTRACTION
# ============================================================

def extract_lot_numbers(text):

    return sorted(
        set(
            match.upper()
            for match in LOT_REGEX.findall(text)
        )
    )

# ============================================================
# VALIDATION
# ============================================================

def validate_pdf(pdf_bytes, expected_lot):

    text = extract_text(pdf_bytes)

    if not text.strip():

        return {
            "status": "NO_TEXT",
            "lots": []
        }

    lots = extract_lot_numbers(text)

    if not lots:

        return {
            "status": "NO_LOT_FOUND",
            "lots": []
        }

    if expected_lot in lots:

        return {
            "status": "PASS",
            "lots": lots
        }

    return {
        "status": "FAIL",
        "lots": lots
    }

# ============================================================
# UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload ZIP File",
    type=["zip"]
)

# ============================================================
# PROCESS
# ============================================================

if uploaded_file is not None:

    st.success(f"Loaded: {uploaded_file.name}")

    with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:

        groups = get_pdf_groups(zf)

        if not groups:

            st.error("No PDFs found inside ZIP.")

        else:

            st.markdown(
                f"Found **{len(groups)}** folder(s)"
            )

            for folder_name, pdf_paths in sorted(groups.items()):

                st.divider()

                st.subheader(folder_name)

                folder_lots = extract_lot_numbers(folder_name)

                if folder_lots:
                    expected_lot = folder_lots[0]
                else:
                    expected_lot = folder_name.upper()

                pass_count = 0
                fail_count = 0

                validation_results = []

                for pdf_path in pdf_paths:

                    with zf.open(pdf_path) as f:
                        pdf_bytes = f.read()

                    result = validate_pdf(
                        pdf_bytes,
                        expected_lot
                    )

                    validation_results.append(
                        (
                            pdf_path.split("/")[-1],
                            result
                        )
                    )

                with st.expander("Validation Results"):

                    for filename, result in validation_results:

                        status = result["status"]

                        if status == "PASS":

                            pass_count += 1

                            st.success(
                                f"✓ {filename}"
                            )

                        elif status == "NO_TEXT":

                            st.info(
                                f"ℹ {filename} (scanned PDF or no text)"
                            )

                        elif status == "NO_LOT_FOUND":

                            st.warning(
                                f"⚠ {filename} (no lot number found)"
                            )

                        else:

                            fail_count += 1

                            st.error(
                                f"✗ {filename} | Found: {', '.join(result['lots'])}"
                            )

                st.write(
                    f"Validation Summary: "
                    f"{pass_count} passed, "
                    f"{fail_count} failed"
                )

                with st.spinner(
                    f"Merging {folder_name}..."
                ):

                    merged_pdf = merge_pdfs(
                        zf,
                        pdf_paths
                    )

                st.download_button(
                    label=f"⬇ Download {folder_name}.pdf",
                    data=merged_pdf,
                    file_name=f"{folder_name}.pdf",
                    mime="application/pdf",
                    key=folder_name
                )

st.markdown(
    """
    <br>
    <p style='text-align:center;color:grey;font-size:0.8em'>
    Files are processed in memory only and are not stored.
    </p>
    """,
    unsafe_allow_html=True
)
