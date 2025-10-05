#!/usr/bin/env python3
"""
Create new DynamoDB tables for user preferences and processing features.
"""

import boto3
from decision_data.backend.config.config import backend_config

def create_tables():
    """Create the new DynamoDB tables needed for the enhanced features."""

    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )

    # 1. User Preferences Table
    print("Creating panzoto-user-preferences table...")
    try:
        preferences_table = dynamodb.create_table(
            TableName='panzoto-user-preferences',
            KeySchema=[
                {
                    'AttributeName': 'user_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ panzoto-user-preferences table created successfully")
    except Exception as e:
        if 'already exists' in str(e).lower():
            print("⚠️  panzoto-user-preferences table already exists")
        else:
            print(f"❌ Error creating panzoto-user-preferences table: {e}")

    # 2. Processing Jobs Table
    print("Creating panzoto-processing-jobs table...")
    try:
        jobs_table = dynamodb.create_table(
            TableName='panzoto-processing-jobs',
            KeySchema=[
                {
                    'AttributeName': 'job_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'job_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'user-jobs-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'user_id',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ panzoto-processing-jobs table created successfully")
    except Exception as e:
        if 'already exists' in str(e).lower():
            print("⚠️  panzoto-processing-jobs table already exists")
        else:
            print(f"❌ Error creating panzoto-processing-jobs table: {e}")

    # 3. User Transcripts Table
    print("Creating panzoto-transcripts table...")
    try:
        transcripts_table = dynamodb.create_table(
            TableName='panzoto-transcripts',
            KeySchema=[
                {
                    'AttributeName': 'transcript_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'transcript_id',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'user_id',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'user-transcripts-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'user_id',
                            'KeyType': 'HASH'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    }
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        print("✅ panzoto-transcripts table created successfully")
    except Exception as e:
        if 'already exists' in str(e).lower():
            print("⚠️  panzoto-transcripts table already exists")
        else:
            print(f"❌ Error creating panzoto-transcripts table: {e}")

    print("\n🎯 DynamoDB table creation complete!")
    print("All tables are now ready for the new user preferences and processing features.")

if __name__ == "__main__":
    create_tables()