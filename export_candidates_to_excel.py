import os
from dotenv import load_dotenv
from pymongo import MongoClient
from openpyxl import Workbook

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["cv_platform"]
candidates = db["candidates"]

wb = Workbook()
ws = wb.active
ws.title = "Candidats"
ws.append(["Nom"])

for candidate in candidates.find({}, {"name": 1, "_id": 0}):
    name = candidate.get("name", "")
    if name:
        ws.append([name])

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candidats.xlsx")
wb.save(output_path)
print(f"Fichier Excel enregistré : {output_path}")
print(f"Nombre de candidats exportés : {ws.max_row - 1}")