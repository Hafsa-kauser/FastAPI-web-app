from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from opensearchpy import OpenSearch
import shutil
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (change for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Create uploads directory if not exists

# OpenSearch Configuration
OPENSEARCH_HOST = "localhost"
OPENSEARCH_PORT = 9200

client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    use_ssl=False,
)

INDEX_NAME = "documents"
if not client.indices.exists(INDEX_NAME):
    client.indices.create(index=INDEX_NAME)

# ✅ Home route
@app.get("/")
def home():
    return {"message": "Welcome to the FastAPI File Upload API"}

# ✅ Upload files and index metadata
@app.post("/upload/")
async def upload_files(files: list[UploadFile] = File(...)):
    uploaded_files = []

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document = {
            "filename": file.filename,
            "path": file_path,
            "size": file.size,
            "content_type": file.content_type,
        }
        client.index(index=INDEX_NAME, body=document)

        uploaded_files.append({"filename": file.filename, "status": "success"})

    return {"uploaded_files": uploaded_files}

# ✅ View all uploaded files
@app.get("/files/")
def list_files():
    files = os.listdir(UPLOAD_DIR)
    return {"files": files}

# ✅ Download a specific file
@app.get("/files/{filename}")
def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

# ✅ Improved Search API using wildcard search
@app.get("/search/")
def search_files(query: str):
    search_query = {
        "query": {
            "wildcard": {
                "filename": f"*{query}*"
            }
        }
    }
    response = client.search(index=INDEX_NAME, body=search_query)
    
    results = [{"filename": hit["_source"]["filename"]} for hit in response["hits"]["hits"]]

    return {"results": results}

# ✅ Delete a specific file and remove from OpenSearch
@app.delete("/files/{filename}")
def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    os.remove(file_path)
    delete_query = {
        "query": {
            "match": {
                "filename": filename
            }
        }
    }
    client.delete_by_query(index=INDEX_NAME, body=delete_query)
    
    return {"message": f"File '{filename}' has been deleted"}
