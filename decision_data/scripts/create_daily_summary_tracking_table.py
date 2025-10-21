"""
Migration script to create DynamoDB table for daily summary tracking.

This table tracks which users have had their daily summary scheduled for each day,
ensuring summaries don't get sent multiple times and survive server restarts.

Table: panzoto-daily-summary-tracking
Partition Key: user_id
Sort Key: date (YYYYMMDD format)
"""

import boto3
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from decision_data.backend.config.config import backend_config


def create_table():
    """Create the daily summary tracking table in DynamoDB."""

    dynamodb = boto3.client(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    table_name = 'panzoto-daily-summary-tracking'

    print(f"\n{'='*80}")
    print(f"Creating DynamoDB table: {table_name}")
    print(f"{'='*80}\n")

    try:
        # Check if table already exists
        try:
            response = dynamodb.describe_table(TableName=table_name)
            print(f"✅ Table '{table_name}' already exists")
            print(f"   Status: {response['Table']['TableStatus']}")
            return
        except dynamodb.exceptions.ResourceNotFoundException:
            pass  # Table doesn't exist, proceed to create

        # Create the table
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'date',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'  # String
                },
                {
                    'AttributeName': 'date',
                    'AttributeType': 'S'  # String (YYYYMMDD)
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )

        print(f"✅ Table created successfully!")
        print(f"   Table Name: {response['TableDescription']['TableName']}")
        print(f"   Status: {response['TableDescription']['TableStatus']}")
        print(f"   ARN: {response['TableDescription']['TableArn']}")

        # Add TTL for automatic cleanup after 30 days
        print(f"\n📝 Setting up TTL (30 days)...")
        try:
            dynamodb.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )
            print(f"✅ TTL enabled on 'ttl' attribute (30 days)")
        except Exception as e:
            print(f"⚠️  Could not set TTL: {e}")

        print(f"\n{'='*80}")
        print(f"Table Schema:")
        print(f"{'='*80}")
        print(f"""
Partition Key: user_id (String)
Sort Key: date (String, format: YYYYMMDD)
TTL: ttl (Unix timestamp, auto-expires after 30 days)

Example Item:
{{
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "date": "20251021",
    "job_id": "12345678-1234-1234-1234-123456789012",
    "status": "scheduled",
    "created_at": "2025-10-21T17:05:32Z",
    "ttl": 1729540800
}}

Index: GSI on status for querying by status
""")

    except Exception as e:
        print(f"❌ Error creating table: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_table()
    print("\n✅ Migration complete!\n")
