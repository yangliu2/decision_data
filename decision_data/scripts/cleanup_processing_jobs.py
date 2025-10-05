"""
Cleanup script to delete all processing jobs from DynamoDB.
This is needed after the server-side encryption migration to start fresh.
"""

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def cleanup_processing_jobs():
    """Delete all items from panzoto-processing-jobs table."""

    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    jobs_table = dynamodb.Table('panzoto-processing-jobs')

    print("🔍 Scanning panzoto-processing-jobs table...")

    try:
        # Scan all items
        response = jobs_table.scan()
        items = response['Items']

        # Handle pagination if there are many items
        while 'LastEvaluatedKey' in response:
            response = jobs_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        print(f"📊 Found {len(items)} processing jobs")

        if len(items) == 0:
            print("✅ Table is already empty!")
            return

        # Show breakdown by status
        status_counts = {}
        for item in items:
            status = item.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        print("\n📈 Jobs by status:")
        for status, count in status_counts.items():
            print(f"   {status}: {count}")

        # Confirm deletion
        print(f"\n⚠️  About to DELETE {len(items)} processing jobs")
        confirm = input("Type 'DELETE' to confirm: ")

        if confirm != 'DELETE':
            print("❌ Cancelled - no changes made")
            return

        # Delete all items
        print("\n🗑️  Deleting items...")
        deleted_count = 0

        with jobs_table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'job_id': item['job_id']})
                deleted_count += 1
                if deleted_count % 10 == 0:
                    print(f"   Deleted {deleted_count}/{len(items)}...")

        print(f"\n✅ Successfully deleted {deleted_count} processing jobs!")

        # Verify deletion
        verify_response = jobs_table.scan()
        remaining = len(verify_response['Items'])

        if remaining == 0:
            print("✅ Verification: Table is now empty")
        else:
            print(f"⚠️  Warning: {remaining} items still remain")

    except ClientError as e:
        print(f"❌ Error: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


def cleanup_transcripts():
    """Optional: Delete all transcripts (ask user first)."""

    print("\n" + "="*60)
    print("TRANSCRIPT CLEANUP (OPTIONAL)")
    print("="*60)

    cleanup_transcripts_too = input("\nDo you also want to delete all transcripts? (yes/no): ")

    if cleanup_transcripts_too.lower() != 'yes':
        print("⏭️  Skipping transcript cleanup")
        return

    # Initialize DynamoDB
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=os.getenv('REGION_NAME'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    transcripts_table = dynamodb.Table('panzoto-transcripts')

    print("🔍 Scanning panzoto-transcripts table...")

    try:
        response = transcripts_table.scan()
        items = response['Items']

        while 'LastEvaluatedKey' in response:
            response = transcripts_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response['Items'])

        print(f"📊 Found {len(items)} transcripts")

        if len(items) == 0:
            print("✅ Transcripts table is already empty!")
            return

        print(f"\n⚠️  About to DELETE {len(items)} transcripts")
        confirm = input("Type 'DELETE' to confirm: ")

        if confirm != 'DELETE':
            print("❌ Cancelled - transcripts preserved")
            return

        print("\n🗑️  Deleting transcripts...")
        deleted_count = 0

        with transcripts_table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'transcript_id': item['transcript_id']})
                deleted_count += 1
                if deleted_count % 10 == 0:
                    print(f"   Deleted {deleted_count}/{len(items)}...")

        print(f"\n✅ Successfully deleted {deleted_count} transcripts!")

    except ClientError as e:
        print(f"❌ Error: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


if __name__ == "__main__":
    import sys

    print("="*60)
    print("PANZOTO PROCESSING JOBS CLEANUP")
    print("="*60)
    print("\nThis script will clean up processing jobs after the")
    print("server-side encryption migration (October 5, 2025)")
    print()

    # Check for --auto flag for non-interactive mode
    auto_confirm = '--auto' in sys.argv or '-y' in sys.argv

    if auto_confirm:
        print("🤖 Running in AUTO mode (no confirmations)")

    # Override input function if auto mode
    if auto_confirm:
        original_input = input
        def auto_input(prompt):
            print(prompt + "DELETE (auto-confirmed)")
            return "DELETE"
        globals()['input'] = auto_input

    cleanup_processing_jobs()

    # Restore original input
    if auto_confirm:
        globals()['input'] = original_input

    # Skip transcript cleanup in auto mode
    if not auto_confirm:
        cleanup_transcripts()

    print("\n" + "="*60)
    print("CLEANUP COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Re-login to your Android app to fetch encryption keys")
    print("2. Record new audio (will use server-managed encryption)")
    print("3. Check Processing screen after ~60 seconds for transcripts")
    print()
