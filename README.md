# PDF Split & OCR - MVP

## How to Run

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Start the server:
   ```
   uvicorn backend.main:app --reload
   ```

3. Open `frontend/index.html` in a browser and upload a multi-page scanned PDF.

The app will:
- Split the PDF
- Perform OCR on each page
- Rename files based on content
- Return a zip file of renamed PDFs
