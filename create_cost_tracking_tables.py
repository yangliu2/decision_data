#!/usr/bin/env python3
"""
Create DynamoDB tables for cost tracking.
This script creates the necessary tables for tracking API usage and user credits.
"""

import boto3
import os
import sys
from botocore.exceptions import ClientError

# Set up AWS credentials
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    print("[ERROR] AWS credentials not found in environment variables")
    sys.exit(1)

# Initialize DynamoDB client
dynamodb = boto3.client(
    "dynamodb",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

# Table definitions
TABLES = {
    "panzoto-usage-records": {
        "KeySchema": [
            {"AttributeName": "usage_id", "KeyType": "HASH"},  # Partition key
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
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        "Tags": [
            {"Key": "Environment", "Value": "production"},
            {"Key": "Service", "Value": "cost-tracking"},
        ],
    },
    "panzoto-user-credits": {
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},  # Partition key
        ],
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        "Tags": [
            {"Key": "Environment", "Value": "production"},
            {"Key": "Service", "Value": "cost-tracking"},
        ],
    },
    "panzoto-cost-summaries": {
        "KeySchema": [
            {"AttributeName": "user_id", "KeyType": "HASH"},  # Partition key
            {"AttributeName": "month", "KeyType": "RANGE"},  # Sort key
        ],
        "AttributeDefinitions": [
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "month", "AttributeType": "S"},
        ],
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        "Tags": [
            {"Key": "Environment", "Value": "production"},
            {"Key": "Service", "Value": "cost-tracking"},
        ],
    },
}


def table_exists(table_name):
    """Check if a DynamoDB table exists"""
    try:
        dynamodb.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def create_table(table_name, table_config):
    """Create a DynamoDB table with the given configuration"""
    try:
        print(f"[INFO] Creating table: {table_name}")

        params = {
            "TableName": table_name,
            "KeySchema": table_config["KeySchema"],
            "AttributeDefinitions": table_config["AttributeDefinitions"],
            "ProvisionedThroughput": table_config["ProvisionedThroughput"],
        }

        if "GlobalSecondaryIndexes" in table_config:
            params["GlobalSecondaryIndexes"] = table_config["GlobalSecondaryIndexes"]

        if "Tags" in table_config:
            params["Tags"] = table_config["Tags"]

        response = dynamodb.create_table(**params)

        print(f"[OK] Table {table_name} created successfully")
        print(f"     Table ARN: {response['TableDescription']['TableArn']}")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"[WARN] Table {table_name} already exists")
            return True
        else:
            print(f"[ERROR] Failed to create table {table_name}: {e}")
            return False


def wait_for_table_active(table_name, max_attempts=60):
    """Wait for a table to become active"""
    attempts = 0
    while attempts < max_attempts:
        try:
            response = dynamodb.describe_table(TableName=table_name)
            status = response["Table"]["TableStatus"]

            if status == "ACTIVE":
                print(f"[OK] Table {table_name} is now ACTIVE")
                return True
            else:
                print(f"[INFO] Table {table_name} is {status}, waiting...")
                import time

                time.sleep(2)
                attempts += 1
        except ClientError as e:
            print(f"[ERROR] Error checking table status: {e}")
            return False

    print(f"[ERROR] Table {table_name} did not become active within timeout period")
    return False


def print_table_summary():
    """Print a summary of all cost tracking tables"""
    print("\n[INFO] Cost Tracking Table Summary:")
    print("-" * 70)

    for table_name in TABLES.keys():
        try:
            response = dynamodb.describe_table(TableName=table_name)
            table_info = response["Table"]

            print(f"\nTable: {table_name}")
            print(f"  Status: {table_info['TableStatus']}")
            print(f"  Item Count: {table_info.get('ItemCount', 0)}")
            print(f"  Size (bytes): {table_info.get('TableSizeBytes', 0)}")
            if 'BillingModeSummary' in table_info:
                billing_mode = table_info['BillingModeSummary'].get('BillingMode', 'PROVISIONED')
                print(f"  Billing Mode: {billing_mode}")
            elif 'ProvisionedThroughput' in table_info:
                print(f"  Read Capacity: {table_info['ProvisionedThroughput']['ReadCapacityUnits']}")
                print(f"  Write Capacity: {table_info['ProvisionedThroughput']['WriteCapacityUnits']}")

            # Print key schema
            print("  Key Schema:")
            for key in table_info["KeySchema"]:
                attr_name = key["AttributeName"]
                key_type = key["KeyType"]
                print(f"    - {attr_name} ({key_type})")

            # Print GSIs if any
            if "GlobalSecondaryIndexes" in table_info:
                print("  Global Secondary Indexes:")
                for gsi in table_info["GlobalSecondaryIndexes"]:
                    print(f"    - {gsi['IndexName']} ({gsi['IndexStatus']})")

        except ClientError as e:
            print(f"\n  {table_name}: [ERROR] {e}")

    print("\n" + "-" * 70)


def main():
    """Main function to create all cost tracking tables"""
    print("[START] Creating DynamoDB tables for cost tracking...")
    print(f"[INFO] Region: {AWS_REGION}")
    print()

    all_success = True

    # Create each table
    for table_name, table_config in TABLES.items():
        if not table_exists(table_name):
            if not create_table(table_name, table_config):
                all_success = False
            else:
                # Wait for table to become active
                if not wait_for_table_active(table_name):
                    all_success = False
        else:
            print(f"[SKIP] Table {table_name} already exists")

    print()

    # Print summary
    print_table_summary()

    if all_success:
        print("\n[OK] All cost tracking tables created successfully!")
        print("\nNext steps:")
        print("1. Initialize user credit for new users: cost_service.initialize_user_credit(user_id, 1.00)")
        print("2. Record usage events: cost_service.record_whisper_usage(user_id, duration_minutes)")
        print("3. View cost summary: cost_service.get_current_month_usage(user_id)")
        return 0
    else:
        print("\n[ERROR] Some tables failed to create")
        return 1


if __name__ == "__main__":
    sys.exit(main())
