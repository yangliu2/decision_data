# decision_data/backend/data/mongodb_client.py

from pymongo import MongoClient
from decision_data.backend.config.config import backend_config
from loguru import logger
import pymongo


class MongoDBClient:
    def __init__(self):
        self.client: MongoClient = MongoClient(backend_config.MONGODB_URI)
        self.db = self.client[backend_config.MONGODB_DB_NAME]
        self.collection = self.db[backend_config.MONGODB_COLLECTION_NAME]

    def insert_stories(self, stories):
        if stories:
            try:
                self.collection.insert_many(stories, ordered=False)
                logger.info(f"Inserted {len(stories)} stories into MongoDB.")
            except pymongo.errors.BulkWriteError as e:
                logger.warning(
                    f"Some stories were not inserted due to duplicates or "
                    f"errors: {e.details}"
                )
            except Exception as e:
                logger.error(f"Error inserting stories into MongoDB: {e}")
        else:
            logger.info("No stories to insert.")

    def close(self):
        self.client.close()
