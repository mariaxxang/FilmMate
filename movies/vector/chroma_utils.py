import os
import json
import chromadb
from django.conf import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(settings.BASE_DIR, "chroma_db"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_recommendation(user_query):
    if not GOOGLE_API_KEY: return {"text_response": "API Key Error", "recommendations": []}

    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_or_create_collection("movies_collection")
        
        embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=GOOGLE_API_KEY)
        query_vector = embeddings_model.embed_query(user_query)
        results = collection.query(query_embeddings=[query_vector], n_results=10)

        context_text = ""
        if results['documents'] and results['documents'][0]:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                context_text += f"""
                Title: {meta.get('title')} (Year: {meta.get('year')})
                Genre: {meta.get('genre')}
                Poster: {meta.get('poster_url')}
                Link: {meta.get('detail_link')}
                Plot: {doc}
                \n---\n
                """

        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY, temperature=0.7)
        
        template = """
        You are 'FilmMate', a helpful movie assistant.
        User Input: {question}
        
        Relevant Movie Data (Use this if helpful):
        {context}

        Instructions:
        1. Analyze the User Input.
        2. If the user is asking for **recommendations** (e.g., "suggest a movie", "scary films"), return a list of 1-3 movies in the 'recommendations' list AND a short friendly intro in 'text_response'.
        3. If the user is asking a **specific question** (e.g., "tell me more about that", "who acted in it?", "what is the plot?"), answer their question in 'text_response' and leave 'recommendations' EMPTY [].
        4. Return STRICT JSON. No markdown.

        JSON Structure:
        {{
            "text_response": "Your conversational answer here (use emojis!)",
            "recommendations": [
                {{
                    "title": "Movie Title",
                    "year": 2020,
                    "genre": "Genre",
                    "reason": "Why you picked it",
                    "poster_url": "/media/...",
                    "detail_link": "/movies/1/"
                }}
            ]
        }}
        """
        
        prompt = PromptTemplate.from_template(template)
        chain = prompt | llm
        response = chain.invoke({"question": user_query, "context": context_text})
        
        content = response.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        
        return json.loads(content)

    except Exception as e:
        print(f"Error: {e}")
        return {"text_response": "I'm having trouble accessing my movie database right now.", "recommendations": []}