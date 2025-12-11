import os
import time
import chromadb
from django.core.management.base import BaseCommand
from django.conf import settings
from django.urls import reverse
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from movies.models import Movie

# Define the directory for ChromaDB persistence
CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(settings.BASE_DIR, "chroma_db"))

def chunk_text(text, chunk_size=1000, overlap=100):
    """
    Splits text into smaller chunks with overlap for better embedding context.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    L = len(text)
    
    while start < L:
        end = min(start + chunk_size, L)
        chunks.append(text[start:end])
        start = end - overlap
        
        if start < 0:
            start = 0
        if end == L:
            break
            
    return chunks

class Command(BaseCommand):
    help = "Ingest movies into local Chroma vector store"

    def handle(self, *args, **options):
        # 1. Setup ChromaDB Client
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection_name = "movies_collection"
        
        # Reset collection to ensure fresh data
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
            
        collection = client.create_collection(
            name=collection_name, 
            metadata={"source": "movies"}
        )

        # 2. Setup Embedding Model
        embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

        docs, metadatas, ids = [], [], []
        movies = Movie.objects.all()

        print(f"🎬 Processing {movies.count()} movies...")

        # 3. Process Movies
        for m in movies:
            # Handle Poster URL safely
            try:
                if hasattr(m.poster, 'url'):
                    poster_path = m.poster.url
                else:
                    poster_path = str(m.poster)
            except Exception:
                poster_path = ""

            # Handle Detail Link safely
            try:
                # Assumes 'movies' namespace in urls.py
                detail_link = reverse('movies:movie_detail', args=[m.id])
            except Exception:
                detail_link = f"/movies/{m.id}/"

            # Prepare Text Content
            genre_names = ", ".join([g.name for g in m.genres.all()])
            doc_text = f"Title: {m.title}. Year: {m.year}. Genre: {genre_names}. Plot: {m.description or ''}"
            chunks = chunk_text(doc_text)
            
            # Prepare Data for Embedding
            for i, chunk in enumerate(chunks):
                ids.append(f"movie_{m.id}_chunk_{i}")
                docs.append(chunk)
                metadatas.append({
                    "movie_id": m.id,
                    "title": m.title,
                    "year": m.year,
                    "genre": genre_names,
                    "poster_url": poster_path, 
                    "detail_link": detail_link 
                })

        # 4. Batch Embed and Save to ChromaDB
        BATCH_SIZE = 5
        total_chunks = len(docs)
        
        print(f"📦 Embedding {total_chunks} text chunks...")

        for i in range(0, total_chunks, BATCH_SIZE):
            batch_docs = docs[i : i + BATCH_SIZE]
            print(f"   Processing batch {i} to {min(i + BATCH_SIZE, total_chunks)}...")
            
            try:
                batch_embeddings = embeddings_model.embed_documents(batch_docs)
                
                collection.add(
                    ids=ids[i : i + len(batch_docs)],
                    documents=batch_docs,
                    metadatas=metadatas[i : i + len(batch_docs)],
                    embeddings=batch_embeddings
                )
                
                # Small sleep to avoid hitting API rate limits
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Error in batch {i}: {e}")

        print("✅ Done! All movies ingested.")