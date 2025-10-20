"""
Cleanup script to remove expired and stale jobs from DynamoDB.

Removes jobs that are:
1. Job age > 24 hours (stuck jobs)
2. Status = 'failed' (permanent failures)
3. Job type = 'daily_summary' (no longer manually requested, only automatic)

Usage:
    python decision_data/scripts/cleanup_expired_jobs.py [--dry-run] [--user-id UUID]
"""

import boto3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from decision_data.backend.config.config import backend_config


def get_jobs_table():
    """Get DynamoDB jobs table."""
    dynamodb = boto3.resource(
        'dynamodb',
        region_name=backend_config.REGION_NAME,
        aws_access_key_id=backend_config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=backend_config.AWS_SECRET_ACCESS_KEY
    )
    return dynamodb.Table('panzoto-processing-jobs')


def parse_iso_date(iso_str: str) -> datetime:
    """Parse ISO datetime string."""
    if isinstance(iso_str, str):
        if iso_str.endswith('Z'):
            iso_str = iso_str.replace('Z', '+00:00')
        return datetime.fromisoformat(iso_str)
    return iso_str


def should_delete_job(job: dict, now: datetime) -> tuple[bool, str]:
    """Check if a job should be deleted and return reason."""
    job_id = job['job_id']
    job_type = job.get('job_type')
    status = job.get('status')
    created_at_str = job.get('created_at')

    # Delete all daily_summary jobs (they're no longer manually requested)
    if job_type == 'daily_summary':
        return True, "daily_summary type (automatic only now)"

    # Delete failed jobs
    if status == 'failed':
        return True, "failed status (permanent failure)"

    # Delete jobs older than 24 hours
    if created_at_str:
        try:
            created_at = parse_iso_date(created_at_str)
            # Ensure timezone-aware comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)

            age_hours = (now - created_at).total_seconds() / 3600
            if age_hours > 24:
                return True, f"expired (age: {age_hours:.1f} hours)"
        except Exception as e:
            print(f"  Warning: Could not parse date for {job_id}: {e}")

    return False, ""


def cleanup_jobs(dry_run: bool = True, user_id: str = None):
    """Cleanup expired jobs from DynamoDB."""
    table = get_jobs_table()
    now = datetime.utcnow()

    print(f"\n{'='*70}")
    print(f"Cleanup Job Script - {'DRY RUN' if dry_run else 'EXECUTE'}")
    print(f"{'='*70}")
    print(f"Current UTC time: {now}")
    print(f"Criteria for deletion:")
    print(f"  - Job type = 'daily_summary' (automatic only)")
    print(f"  - Status = 'failed' (permanent failures)")
    print(f"  - Age > 24 hours (stuck jobs)")

    if user_id:
        print(f"\nFiltering by user: {user_id}")

    jobs_to_delete = []
    total_scanned = 0

    try:
        # Scan for jobs
        if user_id:
            # Query specific user's jobs
            response = table.query(
                IndexName='user-jobs-index',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
        else:
            # Scan all jobs
            response = table.scan()

        items = response.get('Items', [])
        total_scanned = len(items)

        print(f"\nScanned {total_scanned} jobs")

        for job in items:
            should_delete, reason = should_delete_job(job, now)
            if should_delete:
                job_id = job['job_id']
                job_type = job.get('job_type', 'unknown')
                status = job.get('status', 'unknown')
                jobs_to_delete.append({
                    'job_id': job_id,
                    'user_id': job.get('user_id'),
                    'type': job_type,
                    'status': status,
                    'created_at': job.get('created_at'),
                    'reason': reason
                })

        print(f"\nFound {len(jobs_to_delete)} jobs to delete:")
        print(f"{'-'*70}")

        deleted_count = 0
        for job in jobs_to_delete:
            print(f"  Job: {job['job_id']}")
            print(f"    Type: {job['type']}, Status: {job['status']}")
            print(f"    User: {job['user_id']}")
            print(f"    Created: {job['created_at']}")
            print(f"    Reason: {job['reason']}")

            if not dry_run:
                try:
                    table.delete_item(Key={'job_id': job['job_id']})
                    deleted_count += 1
                    print(f"    ✓ DELETED")
                except Exception as e:
                    print(f"    ✗ ERROR: {e}")
            else:
                print(f"    [DRY RUN - would delete]")
            print()

        print(f"{'-'*70}")
        print(f"\nSummary:")
        print(f"  Total scanned: {total_scanned}")
        print(f"  To delete: {len(jobs_to_delete)}")
        if not dry_run:
            print(f"  Deleted: {deleted_count}")
        else:
            print(f"  [DRY RUN - no deletions performed]")

        print(f"\nDone!")

    except Exception as e:
        print(f"Error during cleanup: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cleanup expired and stale jobs from DynamoDB"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Preview deletions without actually deleting (default: true)'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually delete jobs (default: false, use --dry-run for preview)'
    )
    parser.add_argument(
        '--user-id',
        type=str,
        default=None,
        help='Only cleanup jobs for specific user (optional)'
    )

    args = parser.parse_args()

    # If --execute flag is set, disable dry-run
    dry_run = not args.execute

    cleanup_jobs(dry_run=dry_run, user_id=args.user_id)
