""" This use dynamo db as a key value pair storage """

import boto3
from loguru import logger
from mypy_boto3_dynamodb import DynamoDBClient
from decision_data.backend.config.config import backend_config
from decision_data.backend.utils.logger import setup_logger

setup_logger()


def get_dynamodb_client() -> DynamoDBClient:
    """Get a dynamodb client

    :return: s3 client seesion
    :rtype: Session
    """
    dynamodb_client = boto3.client(
        "dynamodb",
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY,
        region_name=backend_config.REGION_NAME,
    )
    return dynamodb_client


def query_items_from_dynamodb(
    key: str,
    partition_key: str = "key",
    table_name: str = "panzoto_services",
) -> str:
    """Load key value pairs from dynamo db

    :param key: value for key
    :type key: str
    :param partition_key: partition key or column header, defaults to "key"
    :type partition_key: str, optional
    :param table_name: db table name, defaults to "panzoto_services"
    :type table_name: str, optional
    :raises FileNotFoundError: If secret file wasn't found
    :return: value for the key
    :rtype: str
    """

    dynamodb = get_dynamodb_client()

    try:
        # 'S' indicate string type
        response = dynamodb.get_item(
            TableName=table_name,
            Key={
                partition_key: {"S": key},
            },
        )
        logger.debug(f"response: {response}")
        return response["Item"]["value"]["S"]
    except Exception as e:
        print(f"Error querying items: {e}")
        return ""


def main():
    value = query_items_from_dynamodb("aiy_voice_bucket_name")
    logger.info(f"value: {value} ")


if __name__ == "__main__":
    main()
