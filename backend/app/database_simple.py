"""
Simplified Database Connection - Works without MongoDB
"""

from loguru import logger
from app.config import settings
from typing import Dict, List
import json
from datetime import datetime

# In-memory storage when MongoDB is not available
class InMemoryDatabase:
    def __init__(self):
        self.users = {}
        self.transactions = {}
        self.merchants = {}
        self.fingerprints = {}
        self.blockchain = []

    def get_collection(self, name):
        return getattr(self, name, {})

# Global database instances
database = InMemoryDatabase()
client = None

class MockCollection:
    def __init__(self, data_dict):
        self.data = data_dict
        
    async def find_one(self, query):
        """Find one document matching query"""
        for doc_id, doc in self.data.items():
            if self._matches_query(doc, query):
                return doc
        return None
    
    async def insert_one(self, document):
        """Insert a document"""
        doc_id = f"id_{len(self.data) + 1}"
        document["_id"] = doc_id
        if "created_at" not in document:
            document["created_at"] = datetime.utcnow()
        self.data[doc_id] = document
        return type('Result', (), {'inserted_id': doc_id})()
    
    async def update_one(self, query, update):
        """Update a document"""
        for doc_id, doc in self.data.items():
            if self._matches_query(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                if "$inc" in update:
                    for key, value in update["$inc"].items():
                        doc[key] = doc.get(key, 0) + value
                return type('Result', (), {'modified_count': 1})()
        return type('Result', (), {'modified_count': 0})()
    
    def find(self, query=None):
        """Find multiple documents"""
        results = []
        for doc in self.data.values():
            if query is None or self._matches_query(doc, query):
                results.append(doc)
        return MockCursor(results)
    
    async def aggregate(self, pipeline):
        """Simple aggregation"""
        results = list(self.data.values())
        return MockCursor([{"transactions": results, "total": [{"count": len(results)}]}])
    
    def _matches_query(self, doc, query):
        """Simple query matching"""
        if not query:
            return True
        
        for key, value in query.items():
            if key == "$or":
                # Handle $or queries
                for or_condition in value:
                    if self._matches_query(doc, or_condition):
                        return True
                return False
            elif key in doc:
                if doc[key] == value:
                    continue
                else:
                    return False
            else:
                return False
        return True

class MockCursor:
    def __init__(self, results):
        self.results = results
        
    def limit(self, count):
        self.results = self.results[:count]
        return self
        
    def sort(self, *args):
        return self
        
    async def to_list(self, length):
        return self.results[:length] if length else self.results
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.results:
            return self.results.pop(0)
        raise StopAsyncIteration

async def connect_to_database():
    """Initialize database connection"""
    try:
        logger.info("🔌 Initializing database...")
        logger.info("✅ Using in-memory database for development")
            
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        logger.info("✅ Continuing with in-memory database")

async def create_indexes():
    """Create database indexes"""
    try:
        logger.info("✅ Database indexes ready")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

async def close_database_connection():
    """Close database connection"""
    try:
        logger.info("📤 Database connection closed")
    except Exception as e:
        logger.warning(f"Database close warning: {e}")

def get_users_collection():
    """Get users collection"""
    return MockCollection(database.users)

def get_transactions_collection():
    """Get transactions collection"""
    return MockCollection(database.transactions)

def get_merchants_collection():
    """Get merchants collection"""
    return MockCollection(database.merchants)

def get_fingerprints_collection():
    """Get fingerprints collection"""
    return MockCollection(database.fingerprints)

def get_blockchain_collection():
    """Get blockchain collection"""
    return MockCollection(database.blockchain)
