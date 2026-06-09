import streamlit as st
import zipfile
import io
import re
from collections import defaultdict

from pypdf import PdfWriter, PdfReader

from pdf2image import convert_from_bytes
import pytesseract

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
3. PDFs will be merged by folder.
4. Lot numbers will be validated automatically.
""")

# ============================================================
# CONFIG
# ============================================================

LOT_REGEX = re.compile(
    r"\b[A-Z]{1,4}-[A-Z0-9]+-\d{3,}\b",
    re.IGNORECASE
)

OCR_PAGE_LIMIT = 5

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
# GROUP FILES
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
# PDF MERGING
# ============================================================

def merge_pdfs(zip_file, pdf_paths):

    writer = PdfWriter()

    for path in pdf_paths:

        with zip_file.open(path) as f:

            pdf_data = io.BytesIO(f.read())

            reader = PdfReader(pdf_data)

            for page in reader.pages:
                writer.add_page(page)

    output = io.BytesIO()

    writer.write(output)

    return output.getvalue()

# ============================================================
# TEXT EXTRACTION
# ============================================================

def extract_text_from_pdf_bytes(pdf_bytes):

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
# OCR FALLBACK
# ============================================================

def ocr_pdf_bytes(pdf_bytes):

    text = ""

    try:

        images = convert_from_bytes(
            pdf_bytes,
            first_page=1,
            last_page=OCR_PAGE_LIMIT
        )

        for image in images:

            text += pytesseract.image_to_string(image)

    except Exception:
        pass

    return text

# ============================================================
# LOT DETECTION
# ============================================================

def find_lot_numbers(text):

    lots = set()

    for match in LOT_REGEX.findall(text):
        lots.add(match.upper())

    return lots

# ============================================================
# VALIDATION
# ============================================================

def validate_pdf(pdf_bytes, expected_lot):

    text = extract_text_from_pdf_bytes(pdf_bytes)

    used_ocr = False

    if len(text.strip()) < 50:

        used_ocr = True

        text = ocr_pdf_bytes(pdf_bytes)

    lots_found = find_lot_numbers(text)

    if not lots_found:

        return {
            "status": "NO LOT FOUND",
            "lots": [],
            "ocr": used_ocr
        }

    if expected_lot in lots_found:

        return {
            "status": "PASS",
            "lots": sorted(lots_found),
            "ocr": used_ocr
        }

    return {
        "status": "FAIL",
        "lots": sorted(lots_found),
        "ocr": used_ocr
    }

# ============================================================
# UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload ZIP",
    type=["zip"]
)

# ============================================================
# PROCESS
# ============================================================

if uploaded_file is not None:

    with zipfile.ZipFile(
        io.BytesIO(uploaded_file.read())
    ) as zf:

        groups = get_pdf_groups(zf)

        if not groups:

            st.error("No PDFs found.")

        else:

            for folder_name, pdf_paths in sorted(groups.items()):

                st.divider()

                st.subheader(folder_name)

                expected_lot = folder_name.upper()

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

                failures = 0

                for filename, result in validation_results:

                    status = result["status"]

                    if status == "PASS":

                        st.success(
                            f"✓ {filename}"
                        )

                    elif status == "NO LOT FOUND":

                        st.warning(
                            f"⚠ {filename} | No lot number found"
                        )

                    else:

                        failures += 1

                        st.error(
                            f"✗ {filename} | Found {', '.join(result['lots'])}"
                        )

                st.markdown(
                    f"**Validation Summary:** "
                    f"{len(validation_results)-failures}/{len(validation_results)} passed"
                )

                with st.spinner(
                    f"Merging {folder_name}"
                ):

                    merged_pdf = merge_pdfs(
                        zf,
                        pdf_paths
                    )

                st.download_button(
                    f"⬇ Download {folder_name}.pdf",
                    merged_pdf,
                    file_name=f"{folder_name}.pdf",
                    mime="application/pdf",
                    key=folder_name
                )
