"""
Azure Cosmos DB (MongoDB API) client for InteractorGate.
"""

from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database

_client: MongoClient | None = None


def get_mongo_client() -> MongoClient:
    global _client
    if _client is None:
        # Cosmos DB URI comes directly from .env — includes auth and host
        _client = MongoClient(settings.MONGODB["URI"])
    return _client


def get_mongo_db() -> Database:
    client = get_mongo_client()
    return client[settings.MONGODB["DB"]]


def interaction_logs_collection():
    return get_mongo_db()["interaction_logs"]


def training_history_collection():
    return get_mongo_db()["training_history"]