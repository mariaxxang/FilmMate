import os
import time
import chromadb
from django.conf import settings
from django.urls import reverse
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from movies.models import Movie

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(settings.BASE_DIR, "chroma_db"))

def chunk_text(text, chunk_size=1000, overlap=100):
    if not text: 
        return []
    chunks = []
    start = 0
    L = len(text)
    while start < L:
        end = min(start + chunk_size, L)
        chunks.append(text[start:end])
        start = end - overlap
        if end == L:
            break
    return chunks


def ingest_all_movies():
    print("🔄 Rebuilding Chroma database...")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection_name = "movies_collection"

    try:
        client.delete_collection(collection_name)
    except:
        pass

    collection = client.create_collection(name=collection_name)

    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )

    docs, metadatas, ids = [], [], []
    movies = Movie.objects.all()

    print(f"🎬 Ingesting {movies.count()} movies...")

    for m in movies:
        try:
            poster_url = m.poster.url
        except:
            poster_url = ""

        try:
            detail_link = reverse('movies:movie_detail', args=[m.id])
        except:
            detail_link = f"/movies/{m.id}/"

        genre_names = ", ".join([g.name for g in m.genres.all()])
        text = f"Title: {m.title}. Year: {m.year}. Genre: {genre_names}. Plot: {m.description}"

        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            ids.append(f"movie_{m.id}_chunk_{i}")
            docs.append(chunk)
            metadatas.append({
                "movie_id": m.id,
                "title": m.title,
                "year": m.year,
                "genre": genre_names,
                "poster_url": poster_url,
                "detail_link": detail_link
            })

    BATCH = 5
    for i in range(0, len(docs), BATCH):
        batch_docs = docs[i:i+BATCH]
        print(f"📦 Embedding batch {i}...")

        try:
            batch_embeddings = embeddings_model.embed_documents(batch_docs)
            collection.add(
                ids=ids[i:i+len(batch_docs)],
                documents=batch_docs,
                metadatas=metadatas[i:i+len(batch_docs)],
                embeddings=batch_embeddings
            )
        except Exception as e:
            print("❌ Embedding error:", e)

        time.sleep(1)

    print("✅ Chroma ingest complete.")
