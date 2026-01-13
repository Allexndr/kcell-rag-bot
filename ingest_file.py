import chromadb
from chromadb.utils import embedding_functions
import config
import os
import sys
from ingest import extract_text_from_xlsx, chunk_text, extract_text_from_pdf, extract_text_from_docx

def ingest_file(file_path):
    print(f"Ingesting {file_path}...")
    
    # Setup
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=config.EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=config.DB_DIR)
    collection = client.get_collection(name=config.COLLECTION_NAME, embedding_function=embedding_fn)

    # Extract based on extension
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    if ext == '.xlsx':
        text = extract_text_from_xlsx(file_path)
    elif ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext == '.docx':
        text = extract_text_from_docx(file_path)
    elif ext == '.txt':
        with open(file_path, 'r') as f:
            text = f.read()
    else:
        print(f"Unsupported file type: {ext}")
        return

    if not text:
        print("No text extracted.")
        return

    print(f"Extracted {len(text)} chars")

    # Chunk
    chunks = chunk_text(text)
    print(f"Created {len(chunks)} chunks")

    # Add to DB
    filename = os.path.basename(file_path)
    ids = [f"{filename}_{i}" for i in range(len(chunks))]
    metadatas = [{'source': filename, 'year': 2025} for _ in chunks] # Default year for new files

    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )

    print("✅ Successfully added to database.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_file.py <path_to_file>")
        sys.exit(1)
    
    ingest_file(sys.argv[1])
