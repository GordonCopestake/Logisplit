import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import os
import re
import shutil
import json
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_patterns():
    config_path = os.path.join(os.path.dirname(__file__), "patterns.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r") as f:
        return json.load(f)

def process_page(doc_path, page_number, output_dir, patterns, dpi=200):
    doc = fitz.open(doc_path)
    page = doc.load_page(page_number)
    pix = page.get_pixmap(dpi=dpi)
    img_path = os.path.join(output_dir, f"page_{page_number+1}.png")
    pix.save(img_path)

    # Crop to top third of the image
    img = Image.open(img_path)
    width, height = img.size
    top_third = img.crop((0, 0, width, height // 3))

    text = pytesseract.image_to_string(top_third)

    identifier = None
    for pattern in patterns:
        match = re.search(pattern["regex"], text)
        if match:
            identifier = pattern["rename"].format(*match.groups())
            break

    if not identifier:
        identifier = f"page_{page_number+1}"

    pdf_out = os.path.join(output_dir, f"{identifier}.pdf")
    single_doc = fitz.open()
    single_doc.insert_pdf(doc, from_page=page_number, to_page=page_number)
    single_doc.save(pdf_out)
    single_doc.close()
    doc.close()
    img.close()
    os.remove(img_path)
    return page_number

def process_pdf(pdf_path, work_dir, progress_callback=None):
    temp_doc = fitz.open(pdf_path)
    total_pages = len(temp_doc)
    temp_doc.close()

    output_dir = os.path.join(work_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    patterns = load_patterns()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(process_page, pdf_path, i, output_dir, patterns): i
            for i in range(total_pages)
        }
        for future in as_completed(futures):
            page_number = future.result()
            if progress_callback:
                progress_callback(page_number)

    zip_path = os.path.join(work_dir, "processed.zip")
    with ZipFile(zip_path, 'w') as zipf:
        for filename in os.listdir(output_dir):
            zipf.write(os.path.join(output_dir, filename), filename)

    shutil.rmtree(output_dir)
    os.remove(pdf_path)

    return zip_path
