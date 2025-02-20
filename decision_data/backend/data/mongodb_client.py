# decision_data/backend/data/mongodb_client.py

from pymongo import MongoClient
from loguru import logger
import pymongo
from typing import List, Dict, Any
from decision_data.backend.utils.logger import setup_logger

setup_logger()


class MongoDBClient:
    """
    A client for interacting with a MongoDB database to store stories.

    This class handles the connection to the MongoDB server, provides methods
    to insert stories into a specified collection, and manages the closure
    of the database connection.
    """

    def __init__(
        self,
        uri: str,
        db: str,
        collection: str,
    ):
        """
        Initialize the MongoDBClient instance by establishing a connection.

        Connects to the MongoDB server using the URI provided in the backend
        configuration. It selects the specified database and collection for
        storing stories.

        Attributes:
            client (MongoClient): The MongoDB client instance.
            db (Database): The MongoDB database instance.
            collection (Collection): The MongoDB collection for storing
            stories.
        """
        self.client: MongoClient = MongoClient(uri)
        self.db = self.client[db]
        self.collection = self.db[collection]

    def insert_stories(self, stories: List[Dict[str, Any]]) -> None:
        """
        Insert multiple stories into the MongoDB collection.

        This method attempts to insert a list of story documents into the
        MongoDB collection. It handles bulk write errors, such as duplicate
        entries, and logs appropriate messages based on the outcome.

        Args:
            stories (List[Dict[str, Any]]): A list of story dictionaries to
                be inserted into the database.

        Raises:
            pymongo.errors.BulkWriteError: If some stories fail to insert
                due to duplicates or other bulk write issues.
            Exception: If any other unexpected error occurs during insertion.

        Example:
            ```python
            stories = [
                {
                    "id": "abc123",
                    "title": "Sample Story",
                    "content": "This is a sample story.",
                    "url": "http://example.com/story/abc123",
                    "score": 100,
                    "comments": 20,
                    "created_utc": 1615158000,
                    "author": "sample_author"
                },
                # More stories...
            ]
            mongo_client.insert_stories(stories)
            ```
        """
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

    def insert_transcripts(self, transcripts_data: List[Dict[str, Any]]) -> None:

        if transcripts_data:
            try:
                self.collection.insert_many(transcripts_data, ordered=False)
                logger.info(
                    f"Inserted {len(transcripts_data)} transcripts into MongoDB."
                )
            except Exception as e:
                logger.error(f"Error inserting stories into MongoDB: {e}")
        else:
            logger.info("No stories to insert.")

    def get_records_between_dates(
        self,
        date_field: str,
        start_date_str: str,
        end_date_str: str,
        min_transcript_length: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve records from the collection where 'created_utc' is between
        start_date_str and end_date_str.

        :param start_date_str: Start date string in the format 'YYYY-MM-DDTHH:MM:SSZ'
        :param end_date_str: End date string in the format 'YYYY-MM-DDTHH:MM:SSZ'
        :return: List of records
        """

        logger.debug(f"Filtering data between {start_date_str} and {end_date_str}")

        query = {
            "created_utc": {
                "$gte": start_date_str,
                "$lte": end_date_str,
            },
            "transcript": {"$regex": f".{{{min_transcript_length},}}"},
        }
        result = list(self.collection.find(query).sort(date_field, 1))
        return result

    def close(self) -> None:
        """
        Close the MongoDB client connection.

        This method gracefully closes the connection to the MongoDB server,
        releasing any resources held by the client.

        Example:
            ```python
            mongo_client.close()
            ```
        """
        self.client.close()

    def insert_daily_summary(self, summary_data: List[Dict[str, Any]]) -> None:
        """insert daily summary into mongo collection

        :param summary_data: summary data in dictionary format
        :type summary_data: List[Dict[str, Any]]
        """

        if summary_data:
            try:
                self.collection.insert_many(summary_data, ordered=False)
                logger.info(f"Inserted {len(summary_data)} transcripts into MongoDB.")
            except Exception as e:
                logger.error(f"Error inserting stories into MongoDB: {e}")
        else:
            logger.info("No stories to insert.")
