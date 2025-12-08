import os
import google.generativeai as genai
from dotenv import load_dotenv

# Зареждаме ключа от .env файла
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ Грешка: Няма GOOGLE_API_KEY в .env файла!")
else:
    genai.configure(api_key=api_key)
    print("🔍 Търсене на налични модели...")
    try:
        count = 0
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ Наличен модел: {m.name}")
                count += 1
        if count == 0:
            print("⚠️ Няма намерени модели за генериране на текст. Провери правата на ключа.")
    except Exception as e:
        print(f"❌ Грешка при свързване: {e}")