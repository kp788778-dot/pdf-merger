"""
Downer Asphalt Lot Pack Manager
--------------------------------
Streamlit app that takes a ZIP of lot folders (each containing PDFs),
sorts the PDFs numerically, merges them per folder, and validates that
the lot number printed inside each PDF matches the folder/lot name.
"""

import streamlit as st
import zipfile
import io
import re
from collections import defaultdict
from pypdf import PdfWriter, PdfReader

# ============================================================
# CONFIG
# ============================================================

LOT_REGEX = re.compile(
    r"\b[A-Z]{1,4}-[A-Z0-9]+-\d{3,}\b",
    re.IGNORECASE
)


# ============================================================
# PAGE SETUP
# ============================================================

def configure_page():
    """Set Streamlit page title, icon, and layout. Must be the first
    Streamlit call made in the script."""
    st.set_page_config(
        page_title="Downer Asphalt Lot Pack Manager",
        page_icon="📄",
        layout="centered"
    )


def render_instructions():
    """Render the app title and the 'how to use' instructions block."""
    st.title("Downer Asphalt Lot Pack Manager")

    st.markdown("""
    ### How to use

    1. Download lot folders containing all documents as a ZIP.
    2. Upload the ZIP below.
    3. PDFs will be automatically sorted numerically.
    4. PDFs are merged by folder they are in.
    5. Lot numbers found in text-based PDFs are checked for Downer mistakes. Scanned paged will still need to be manually checked.
    """)


def render_footer():
    """Render the small disclaimer footer shown at the bottom of the app."""
    st.markdown(
        """
        <br>
        <p style='text-align:center;color:grey;font-size:0.8em'>
        Files are processed in memory only and are not stored.
        </p>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# SORTING
# ============================================================

def pdf_sort_key(path):
    """Return a sort key for a PDF path based on the leading number in
    its filename (e.g. '3 - report.pdf' sorts before '10 - report.pdf').
    Files without a leading number are sorted last, alphabetically."""
    filename = path.split("/")[-1]
    match = re.match(r"^\s*(\d+)", filename)

    if match:
        return (int(match.group(1)), filename)

    return (9999, filename)


# ============================================================
# GROUPING
# ============================================================

def get_pdf_groups(zip_file):
    """Scan the uploaded ZIP and group all PDF paths by the folder
    (lot) they live in. Returns a dict of {folder_name: [sorted pdf paths]}."""
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
# MERGING
# ============================================================

def merge_pdfs(zip_file, pdf_paths):
    """Merge the given list of PDF paths (already sorted) from the ZIP
    into a single PDF and return its bytes."""
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
# TEXT / LOT EXTRACTION
# ============================================================

def extract_text(pdf_bytes):
    """Extract all readable text from a PDF's bytes. Returns an empty
    string if the PDF is scanned/image-only or unreadable."""
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


def extract_lot_numbers(text):
    """Find all lot-number-like patterns in a block of text and return
    them as a sorted list of unique, uppercased strings."""
    return sorted(
        set(match.upper() for match in LOT_REGEX.findall(text))
    )


# ============================================================
# VALIDATION
# ============================================================

def determine_expected_lot(folder_name):
    """Work out the lot number a folder is expected to contain, based
    on the folder's own name (falls back to the uppercased folder name
    if no lot pattern is found in it)."""
    folder_lots = extract_lot_numbers(folder_name)

    if folder_lots:
        return folder_lots[0]

    return folder_name.upper()


def validate_pdf(pdf_bytes, expected_lot):
    """Check whether a single PDF's text contains the expected lot
    number. Returns a dict with a 'status' (PASS, FAIL, NO_LOT_FOUND,
    or NO_TEXT) and the list of lot numbers actually found."""
    text = extract_text(pdf_bytes)

    if not text.strip():
        return {"status": "NO_TEXT", "lots": []}

    lots = extract_lot_numbers(text)

    if not lots:
        return {"status": "NO_LOT_FOUND", "lots": []}

    if expected_lot in lots:
        return {"status": "PASS", "lots": lots}

    return {"status": "FAIL", "lots": lots}


def validate_folder(zf, pdf_paths, expected_lot):
    """Run validate_pdf() over every PDF in a folder. Returns a list of
    (filename, result) tuples for display."""
    validation_results = []

    for pdf_path in pdf_paths:
        with zf.open(pdf_path) as f:
            pdf_bytes = f.read()

        result = validate_pdf(pdf_bytes, expected_lot)
        validation_results.append((pdf_path.split("/")[-1], result))

    return validation_results


# ============================================================
# DISPLAY
# ============================================================

def display_validation_results(validation_results):
    """Render a Streamlit expander showing per-file validation status,
    colour-coded by outcome. Returns (pass_count, fail_count)."""
    pass_count = 0
    fail_count = 0

    with st.expander("Validation Results"):

        for filename, result in validation_results:
            status = result["status"]

            if status == "PASS":
                pass_count += 1
                st.success(filename)

            elif status == "NO_TEXT":
                st.info(f"{filename} (scanned PDF or no text)")

            elif status == "NO_LOT_FOUND":
                st.warning(f"{filename} (no lot number found)")

            else:
                fail_count += 1
                st.error(f"{filename} | Found: {', '.join(result['lots'])}")

    return pass_count, fail_count


def process_folder(zf, folder_name, pdf_paths):
    """Handle a single lot folder end-to-end: validate its PDFs, show
    the results, merge the PDFs, and offer a download button."""
    st.divider()
    st.subheader(folder_name)

    expected_lot = determine_expected_lot(folder_name)
    validation_results = validate_folder(zf, pdf_paths, expected_lot)

    pass_count, fail_count = display_validation_results(validation_results)

    st.write(f"Validation Summary: {pass_count} passed, {fail_count} failed")

    with st.spinner(f"Merging {folder_name}..."):
        merged_pdf = merge_pdfs(zf, pdf_paths)

    st.download_button(
        label=f"⬇ Download {folder_name}.pdf",
        data=merged_pdf,
        file_name=f"{folder_name}.pdf",
        mime="application/pdf",
        key=f"download_{folder_name}"
    )


def process_zip_upload(uploaded_file):
    """Top-level handler for an uploaded ZIP: open it, group PDFs by
    folder, and process each folder in turn."""
    st.success(f"Loaded: {uploaded_file.name}")

    with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
        groups = get_pdf_groups(zf)

        if not groups:
            st.error("No PDFs found inside ZIP.")
            return

        st.markdown(f"Found **{len(groups)}** folder(s)")

        for folder_name, pdf_paths in sorted(groups.items()):
            process_folder(zf, folder_name, pdf_paths)


# ============================================================
# MAIN
# ============================================================

def main():
    """Entry point: wires together page setup, upload, processing, and footer."""
    configure_page()
    render_instructions()

    uploaded_file = st.file_uploader("Upload ZIP File", type=["zip"])

    if uploaded_file is not None:
        process_zip_upload(uploaded_file)

    render_footer()


if __name__ == "__main__":
    main()
