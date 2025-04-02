
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import json
from .processor import process_pdf
from threading import Thread
latest_zip_path = None
import queue

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

progress_queue = queue.Queue()

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    input_path = os.path.join(temp_dir, file.filename)

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    zip_path = process_pdf(input_path, temp_dir)
    return FileResponse(zip_path, filename="processed.zip", media_type='application/zip')



@app.post("/upload/stream")
async def upload_stream(file: UploadFile = File(...)):
    global latest_zip_path
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    input_path = os.path.join(temp_dir, file.filename)

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    def run_processing():
        nonlocal input_path, temp_dir
        zip_path = process_pdf(input_path, temp_dir, progress_callback=lambda i: progress_queue.put(i))
        globals()['latest_zip_path'] = zip_path
        progress_queue.put("done")

    Thread(target=run_processing).start()
    return JSONResponse({"status": "processing started"})



@app.get("/progress")
async def progress():
    def event_stream():
        while True:
            update = progress_queue.get()
            yield f"data: {update}\n\n"
            if update == "done":
                break
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/patterns.json")
async def get_patterns():
    with open(os.path.join(os.path.dirname(__file__), "patterns.json"), "r") as f:
        return json.load(f)

@app.get("/download")
def download():
    if latest_zip_path and os.path.exists(latest_zip_path):
        return FileResponse(latest_zip_path, filename="processed.zip", media_type="application/zip")
    return JSONResponse({"error": "No file available"}, status_code=404)
