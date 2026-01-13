import uvicorn
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import shutil
import os
import uuid
from src.compare.engine import DocumentComparator

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Storage for uploads
UPLOAD_DIR = "uploads/compare_temp"
os.makedirs(UPLOAD_DIR, exist_ok=True)

comparator = DocumentComparator()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/compare/{comparison_id}", response_class=HTMLResponse)
async def get_compare_view(comparison_id: str):
    # For now, we serve a static HTML that will verify the ID via JS or just serve the app
    # In a real app, we might check if ID exists in some DB/cache.
    # Here we just serve the static page, and the page will fetch data via API?
    # Or we can just render the template.
    # Let's serve the HTML file.
    with open("static/compare.html", "r") as f:
        return f.read()

import json

@app.get("/api/results/{session_id}")
async def get_compare_result(session_id: str):
    result_path = os.path.join(UPLOAD_DIR, session_id, "result.json")
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Comparison not found")
    with open(result_path, "r", encoding='utf-8') as f:
        return json.load(f)

@app.post("/api/compare")
async def compare_documents(file1: UploadFile = File(...), file2: UploadFile = File(...)):
    try:
        # Create unique session ID
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(UPLOAD_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Save files
        path1 = os.path.join(session_dir, "original_" + file1.filename)
        path2 = os.path.join(session_dir, "modified_" + file2.filename)
        
        with open(path1, "wb") as buffer:
            shutil.copyfileobj(file1.file, buffer)
        with open(path2, "wb") as buffer:
            shutil.copyfileobj(file2.file, buffer)
            
        # Perform comparison
        result = comparator.compare_files(path1, path2)
        
        # Add metadata
        result['session_id'] = session_id
        result['filenames'] = {
            'original': file1.filename,
            'modified': file2.filename
        }
        
        # Save result for persistence
        with open(os.path.join(session_dir, "result.json"), "w", encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
        
        return {"session_id": session_id, "url": f"/compare/{session_id}"}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
