#!/usr/bin/env python3
"""
Script to create DynamoDB tables for cost tracking
"""

import boto3
import sys

dynamodb = boto3.client("dynamodb", region_name="us-east-1")

tables_to_create = [
    {
        "TableName": "panzoto-usage-records",
        "KeySchema": [
            {"AttributeName": "usage_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "usage_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "month", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user-month-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "month", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            }
        ],
        "BillingMode": "PROVISIONED",
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        },
    },
    {
        "TableName": "panzoto-user-credits",
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "BillingMode": "PROVISIONED",
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        },
    },
    {
        "TableName": "panzoto-cost-summaries",
        "KeySchema": [
            {"AttributeName": "month", "KeyType": "HASH"},
            {"AttributeName": "user_id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "month", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "BillingMode": "PROVISIONED",
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5,
        },
    },
]


def create_tables():
    """Create all cost tracking tables"""
    for table_config in tables_to_create:
        table_name = table_config["TableName"]
        print(f"[INFO] Creating table: {table_name}...")

        try:
            # Check if table already exists
            try:
                dynamodb.describe_table(TableName=table_name)
                print(f"[OK] Table {table_name} already exists")
                continue
            except dynamodb.exceptions.ResourceNotFoundException:
                pass

            # Create table
            dynamodb.create_table(**table_config)
            print(f"[OK] Table {table_name} created successfully")

            # Wait for table to be active
            waiter = dynamodb.get_waiter("table_exists")
            waiter.wait(TableName=table_name)
            print(f"[OK] Table {table_name} is now active")

        except Exception as e:
            print(f"[ERROR] Failed to create table {table_name}: {e}")
            return False

    print("[OK] All cost tracking tables created successfully")
    return True


if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
