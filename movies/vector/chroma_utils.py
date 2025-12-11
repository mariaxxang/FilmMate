import os
import json
import chromadb
from django.conf import settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(settings.BASE_DIR, "chroma_db"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_recommendation(user_query):
    """
    Функция за чатбота: приема въпрос от потребителя,
    намира контекст от базата и връща отговор + препоръки чрез LLM.
    """
    if not GOOGLE_API_KEY: 
        return {"text_response": "API Key Error", "recommendations": []}

    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_or_create_collection("movies_collection")
        
        embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=GOOGLE_API_KEY
        )
        
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

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            google_api_key=GOOGLE_API_KEY, 
            temperature=0.7
        )
        
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
        print(f"Error in chatbot recommendation: {e}")
        return {"text_response": "I'm having trouble accessing my movie database right now.", "recommendations": []}


def find_similar_movies_by_content(movie_text, current_movie_id, top_k=4):
    """
    Търси подобни филми на база векторно съвпадение (semantically similar).
    
    Args:
        movie_text (str): Комбинация от заглавие + жанр + описание на текущия филм.
        current_movie_id (int): ID на текущия филм, за да го изключим от резултатите.
        top_k (int): Колко филма да върнем (по подразбиране 4).
    
    Returns:
        list: Списък с речници {'id', 'title', 'year', 'poster'}.
    """
    if not GOOGLE_API_KEY: 
        print("Google API Key is missing.")
        return []

    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection("movies_collection")
        
        embeddings_model = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004", 
            google_api_key=GOOGLE_API_KEY
        )

        query_vector = embeddings_model.embed_query(movie_text)

        results = collection.query(
            query_embeddings=[query_vector], 
            n_results=20 
        )

        similar_movies = []
        seen_ids = set()
        
        seen_ids.add(str(current_movie_id))
        seen_ids.add(int(current_movie_id))

        if results['metadatas'] and results['metadatas'][0]:
            for meta in results['metadatas'][0]:
                m_id = meta.get('movie_id')
                
                if m_id in seen_ids:
                    continue
                
                seen_ids.add(m_id)
                
                similar_movies.append({
                    'id': m_id,
                    'title': meta.get('title'),
                    'year': meta.get('year'),
                    'poster': meta.get('poster_url'),
                })

                if len(similar_movies) >= top_k:
                    break
        
        return similar_movies

    except Exception as e:
        print(f"Error in finding similar movies: {e}")
        return []