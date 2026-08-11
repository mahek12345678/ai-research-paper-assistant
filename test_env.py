from dotenv import load_dotenv
import os

load_dotenv()
key = os.getenv("GROQ_API_KEY")
print("Key found:", key is not None)
print("First 8 chars:", key[:8] if key else "N/A")