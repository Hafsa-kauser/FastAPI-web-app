from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from opensearchpy import OpenSearch
import shutil
import os
import datetime

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
    upload_date = datetime.datetime.now().isoformat()

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Check if file already exists in OpenSearch
        search_query = {"query": {"match": {"filename": file.filename}}}
        existing_docs = client.search(index=INDEX_NAME, body=search_query)

        if existing_docs["hits"]["hits"]:
            print(f"File '{file.filename}' already exists in OpenSearch. Skipping indexing.")
        else:
            document = {
                "filename": file.filename,
                "path": file_path,
                "size": file.size,
                "content_type": file.content_type,
                "upload_date": upload_date,
            }
            client.index(index=INDEX_NAME, body=document)

        uploaded_files.append({"filename": file.filename, "status": "success"})

    return {"uploaded_files": uploaded_files}

# ✅ List all uploaded files
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

# ✅ Improved Search API with keyword and metadata search
@app.get("/search/")
def search_files(
    query: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    content_type: str = Query(None),
):
    search_filters = {"bool": {"must": []}}

    if query:
        search_filters["bool"]["must"].append({
            "multi_match": {
                "query": query,
                "fields": ["filename", "content_type", "path"],  # Add all searchable fields
                "type": "best_fields"
            }
        })

    if start_date and end_date:
        search_filters["bool"]["must"].append({
            "range": {"upload_date": {"gte": start_date, "lte": end_date}}
        })

    if content_type:
        search_filters["bool"]["must"].append({"match": {"content_type": content_type}})

    search_query = {"query": search_filters}
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
    delete_query = {"query": {"match": {"filename": filename}}}
    client.delete_by_query(index=INDEX_NAME, body=delete_query)
    
    return {"message": f"File '{filename}' has been deleted"}
