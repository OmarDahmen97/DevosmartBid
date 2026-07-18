from pymongo import MongoClient
from datetime import datetime
import os
from pymongo import MongoClient
from dotenv import  load_dotenv
from rapidfuzz import fuzz
load_dotenv()
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['cv_platform']
candidates = db['candidates']
yasmine = candidates.find_one({'name': 'Yasmine Goubantini'},{'_id':0,'versions.raw_text': 0})
versions=yasmine["versions"]
print(len(versions))
import json
from langchain_text_splitters import RecursiveJsonSplitter
splitter=RecursiveJsonSplitter(max_chunk_size=10,min_chunk_size=5)
chunked=[]
for v in versions:
    yasmine_chunked=splitter.split_json(v)
    chunked.append(yasmine_chunked)
for chunk in chunked:
    for c in chunk:
        print(c)
        print('\n')
    print('\n\n')

print(len(yasmine_chunked))