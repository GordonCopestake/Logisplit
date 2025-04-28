import io
import json
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF
from PIL import Image
from zipfile import ZipFile

# --------------------------------------------------------------------------- #
# Configuration (override via env vars)
# --------------------------------------------------------------------------- #
TESSDATA_PATH = os.getenv("TESSDATA_PREFIX", "/usr/share/tesseract-ocr/4.00/tessdata_fast")
TESS_LANG = os.getenv("TESS_LANG", "eng")
TESS_OEM = int(os.getenv("TESS_OEM", "1"))  # LSTM only
TESS_PSM = int(os.getenv("TESS_PSM", "6"))  # single uniform block
DPI = int(os.getenv("LOGISPLIT_DPI", "200"))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _load_patterns() -> List[dict]:
    patterns_file = Path(__file__).with_name("patterns.json")
    with open(patterns_file, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _init_worker(tessdata_path: str, lang: str, psm: int, oem: int) -> None:
    """
    Runs once in **each** worker process. Creates a global, reusable Tesseract
    engine so subsequent calls avoid costly startup.
    """
    global API
    from tesserocr import PyTessBaseAPI, PSM  # import inside fork
    API = PyTessBaseAPI(path=tessdata_path, lang=lang, oem=oem)
    API.SetPageSegMode(PSM(psm))


def _ocr_and_extract(args) -> Tuple[str, bytes]:
    """
    Worker function executed in a separate process.

    Returns:
        filename, data (PDF bytes)
    """
    page_no, pdf_path, dpi, patterns = args
    # --- render page ------------------------------------------------------------------
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_no)
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # --- OCR --------------------------------------------------------------------------
    API.SetImage(img)
    text = API.GetUTF8Text()

    # --- determine target name --------------------------------------------------------
    filename = f"page_{page_no+1}.pdf"
    for rule in patterns:
        match = re.search(rule["regex"], text)
        if match:
            filename = rule["rename"].format(*match.groups()) + ".pdf"
            break

    # --- export single?page PDF -------------------------------------------------------
    buf = io.BytesIO()
    ndoc = fitz.open()
    ndoc.insert_pdf(doc, from_page=page_no, to_page=page_no)
    ndoc.save(buf)
    return filename, buf.getvalue()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def process_pdf(pdf_path: str, out_zip: str, dpi: int = DPI) -> None:
    """
    Split *pdf_path* into single?page PDFs, OCR each page, rename via patterns
    and store everything into *out_zip*.

    Designed to be called by the FastAPI endpoint.
    """
    patterns = _load_patterns()

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count

    with ProcessPoolExecutor(
        max_workers=os.cpu_count(),
        initializer=_init_worker,
        initargs=(TESSDATA_PATH, TESS_LANG, TESS_PSM, TESS_OEM),
    ) as pool, ZipFile(out_zip, mode="w") as zf:

        futures = {
            pool.submit(_ocr_and_extract, (i, pdf_path, dpi, patterns)): i
            for i in range(page_count)
        }

        used_names = set()
        for fut in as_completed(futures):
            name, data = fut.result()
            # ensure unique names inside zip
            original = name
            suffix = 1
            while name in used_names:
                stem, ext = os.path.splitext(original)
                name = f"{stem}_{suffix}{ext}"
                suffix += 1
            used_names.add(name)

            zf.writestr(name, data)


# --------------------------------------------------------------------------- #
# CLI (optional)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Optimised processor for Logisplit.")
    parser.add_argument("pdf", help="Input PDF file")
    parser.add_argument("-o", "--output", default="output.zip", help="Destination zip")
    parser.add_argument("--dpi", type=int, default=DPI, help="Render DPI (default 200)")
    args = parser.parse_args()

    process_pdf(args.pdf, args.output, dpi=args.dpi)
    print(f"Wrote {args.output}")