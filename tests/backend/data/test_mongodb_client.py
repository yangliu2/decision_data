import pytest
from unittest.mock import patch
from datetime import datetime
from decision_data.backend.data.mongodb_client import MongoDBClient


@pytest.fixture
def mongodb_client():
    with patch(
        "decision_data.backend.data.mongodb_client.MongoClient"
    ) as MockMongoClient:
        mock_client = MockMongoClient()
        mock_db = mock_client.__getitem__.return_value
        mock_collection = mock_db.__getitem__.return_value
        client = MongoDBClient(
            "mongodb://localhost:27017/", "test_db", "test_collection"
        )
        yield client, mock_client, mock_db, mock_collection
        client.close()


def test_init(mongodb_client):
    client, mock_client, mock_db, mock_collection = mongodb_client
    assert client.client == mock_client
    assert client.db == mock_db
    assert client.collection == mock_collection


def test_insert_stories(mongodb_client):
    client, _, _, mock_collection = mongodb_client
    stories = [
        {"title": "Story 1", "content": "Content 1"},
        {"title": "Story 2", "content": "Content 2"},
    ]
    client.insert_stories(stories)
    mock_collection.insert_many.assert_called_once_with(
        stories,
        ordered=False,
    )


def test_get_records_between_dates(mongodb_client):
    client, _, _, mock_collection = mongodb_client
    # Mock data
    mock_data = [
        {"created_utc": datetime(2023, 1, 15, 12, 0, 0), "data": "record1"},
        {"created_utc": datetime(2023, 1, 20, 12, 0, 0), "data": "record2"},
    ]
    mock_collection.find.return_value.sort.return_value = mock_data

    start_date = "2023-01-01 00:00:00"
    end_date = "2023-01-31 23:59:59"
    result = client.get_records_between_dates(
        date_field="created_utc", start_date_str=start_date, end_date_str=end_date
    )

    mock_collection.find.assert_called_once_with(
        {
            "created_utc": {
                "$gte": "2023-01-01 00:00:00",
                "$lte": "2023-01-31 23:59:59",
            },
            "transcript": {"$regex": ".{4,}"},
        }
    )
    mock_collection.find.return_value.sort.assert_called_once_with("created_utc", 1)
    assert result == mock_data


def test_close(mongodb_client):
    client, mock_client, _, _ = mongodb_client
    client.close()
    mock_client.close.assert_called_once()
