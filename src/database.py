from pydantic import BaseModel
from simplejsondb import Database

database = Database("app_data/database.json", default={
    "users": {},
    "universities": {},
    "rooms": {},
    "times": {},
})

def collection(collection: str):
    return database.data.get(collection) or {}

def fetch(collection_name: str, key: str):
    return collection(collection_name).get(key)

def find(collection_name: str, predicate):
    return next((item for item in collection(collection_name).values() if predicate(item)), None)

def insert(collection_name: str, key: str, value: BaseModel):
    if collection_name not in database.data:
        database.data[collection_name] = {}
    database.data[collection_name][key] = value.model_dump(mode='json')
    database.save()