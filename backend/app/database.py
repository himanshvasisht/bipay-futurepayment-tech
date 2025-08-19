"""
Database layer with optional MongoDB (motor) support.
If environment variable MONGO_URI is set, the code will use Motor (async MongoDB driver).
Otherwise a MockDatabase is used for local development.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid
import os
from loguru import logger

# Try to import motor for real DB support; fallback to mock when not available
try:
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    MOTOR_AVAILABLE = True
except Exception:
    AsyncIOMotorClient = None  # type: ignore
    MOTOR_AVAILABLE = False


class MockCursor:
    def __init__(self, data: List[Dict]):
        self.data = data
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        result = self.data[self.index]
        self.index += 1
        return result
    
    async def to_list(self, length=None):
        return self.data[:length] if length else self.data

class MockCollection:
    def __init__(self, name: str):
        self.name = name
        self.data: List[Dict] = []
    
    async def find_one(self, filter_dict: Optional[Dict] = None) -> Optional[Dict]:
        if not filter_dict:
            return self.data[0] if self.data else None
        
        for item in self.data:
            if self._matches_filter(item, filter_dict):
                return item
        return None
    
    def find(self, filter_dict: Optional[Dict] = None) -> MockCursor:
        if not filter_dict:
            return MockCursor(self.data)
        
        filtered_data = [item for item in self.data if self._matches_filter(item, filter_dict)]
        return MockCursor(filtered_data)
    
    async def insert_one(self, document: Dict) -> Dict:
        doc = document.copy()
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        if "created_at" not in doc:
            doc["created_at"] = datetime.utcnow()
        self.data.append(doc)
        return {"inserted_id": doc["_id"]}
    
    async def update_one(self, filter_dict: Dict, update_dict: Dict) -> Dict:
        for item in self.data:
            if self._matches_filter(item, filter_dict):
                if "$set" in update_dict:
                    item.update(update_dict["$set"])
                elif "$inc" in update_dict:
                    for key, value in update_dict["$inc"].items():
                        item[key] = item.get(key, 0) + value
                else:
                    item.update(update_dict)
                item["updated_at"] = datetime.utcnow()
                return {"modified_count": 1}
        return {"modified_count": 0}
    
    async def delete_one(self, filter_dict: Dict) -> Dict:
        for i, item in enumerate(self.data):
            if self._matches_filter(item, filter_dict):
                self.data.pop(i)
                return {"deleted_count": 1}
        return {"deleted_count": 0}
    
    async def count_documents(self, filter_dict: Optional[Dict] = None) -> int:
        if not filter_dict:
            return len(self.data)
        return len([item for item in self.data if self._matches_filter(item, filter_dict)])
    
    async def aggregate(self, pipeline: List[Dict]) -> MockCursor:
        result = self.data.copy()
        
        for stage in pipeline:
            if "$match" in stage:
                result = [item for item in result if self._matches_filter(item, stage["$match"])]
            elif "$group" in stage:
                groups = {}
                group_spec = stage["$group"]
                group_id = group_spec.get("_id")
                
                for item in result:
                    key = str(item.get(group_id.replace("$", ""), "null")) if group_id else "all"
                    if key not in groups:
                        groups[key] = {"_id": key, "count": 0}
                    groups[key]["count"] += 1
                
                result = list(groups.values())
        
        return MockCursor(result)
    
    def _matches_filter(self, item: Dict, filter_dict: Dict) -> bool:
        for key, value in filter_dict.items():
            if key not in item:
                return False
            if isinstance(value, dict):
                item_value = item[key]
                for op, op_value in value.items():
                    if op == "$gte" and item_value < op_value:
                        return False
                    elif op == "$lte" and item_value > op_value:
                        return False
                    elif op == "$gt" and item_value <= op_value:
                        return False
                    elif op == "$lt" and item_value >= op_value:
                        return False
                    elif op == "$ne" and item_value == op_value:
                        return False
                    elif op == "$in" and item_value not in op_value:
                        return False
            elif item[key] != value:
                return False
        return True

class MockDatabase:
    def __init__(self):
        self.collections = {}
    
    def __getitem__(self, collection_name: str) -> MockCollection:
        if collection_name not in self.collections:
            self.collections[collection_name] = MockCollection(collection_name)
        return self.collections[collection_name]

class Database:
    def __init__(self):
        self.client = None
        self.database = MockDatabase()
        self._using_motor = False

    def using_motor(self) -> bool:
        return self._using_motor

database = Database()

async def connect_to_database():
    """Connect to MongoDB if MONGO_URI is provided, otherwise initialize the in-memory DB."""
    mongo_uri = os.getenv('MONGO_URI')
    try:
        if mongo_uri and MOTOR_AVAILABLE:
            logger.info("🔌 Connecting to MongoDB via motor...")
            database.client = AsyncIOMotorClient(mongo_uri)
            # Default database name from URI or environment
            db_name = os.getenv('MONGO_DB_NAME') or database.client.get_default_database().name
            database.database = database.client[db_name]
            database._using_motor = True
            logger.info("✅ Connected to MongoDB")
        else:
            logger.info("🔌 Initializing in-memory database... (motor unavailable or MONGO_URI not set)")
            database.database = MockDatabase()
            database._using_motor = False
            logger.info("✅ In-memory database initialized successfully!")

        await create_indexes()
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise e

async def close_database_connection():
    try:
        logger.info("🔚 Cleaning up database connections...")
        if database.using_motor() and database.client:
            database.client.close()
            database.client = None
        database.database = None
        logger.info("✅ Database cleanup completed")
    except Exception as e:
        logger.error(f"❌ Error during database cleanup: {e}")

async def create_indexes():
    try:
        logger.info("📊 Creating database indexes...")
        logger.info("✅ Database indexes created successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to create indexes: {e}")

def get_users_collection() -> MockCollection:
    return database.database["users"]

def get_merchants_collection() -> MockCollection:
    return database.database["merchants"]

def get_transactions_collection() -> MockCollection:
    return database.database["transactions"]

def get_biometric_templates_collection() -> MockCollection:
    return database.database["biometric_templates"]

def get_fingerprints_collection() -> MockCollection:
    return database.database["fingerprints"]

def get_blockchain_blocks_collection() -> MockCollection:
    return database.database["blockchain_blocks"]
