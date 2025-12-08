HOW TO SETUP THE PROJECT

Install Requirements
Open your terminal in this folder and run:
pip install -r requirements.txt

(If that fails on Windows, try: python -m pip install -r requirements.txt)

Create .env file
Create a file named ".env" in this same folder (where manage.py is).
Open it and paste these lines:

GOOGLE_API_KEY="AIzaSy.....(PASTE_YOUR_GOOGLE_KEY_HERE)"
CHROMA_PERSIST_DIR="./chroma_db"

Initialize the AI Database (IMPORTANT!)
The chatbot needs to "read" the movies first. Run this command:

python manage.py ingest_chroma

(Wait until you see "✅ Success!")

Run the Server
python manage.py runserver

Go to https://www.google.com/search?q=http://127.0.0.1:8000/ and enjoy!