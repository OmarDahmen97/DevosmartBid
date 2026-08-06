from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=10000)
try:
    client.admin.command("ping")
    print("Connexion OK")
except Exception as e:
    print(f"Erreur: {e}")