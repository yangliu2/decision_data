""" This use dynamo db as a key value pair storage """

import boto3
from loguru import logger
from decision_data.backend.config.config import backend_config


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

    dynamodb = boto3.client(
        "dynamodb",
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY,
        region_name=backend_config.REGION_NAME,
    )

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
