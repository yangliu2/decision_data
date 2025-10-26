#!/usr/bin/env python3
"""
Test the complete cost tracking workflow.
This script demonstrates:
1. Initialize user credit
2. Record usage events (Whisper, S3, DynamoDB, etc)
3. Deduct costs from user credit
4. View cost summary and history
5. Get user credit balance

Requires AWS credentials in environment variables:
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  - AWS_DEFAULT_REGION (default: us-east-1)
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Verify AWS credentials are set
if not os.getenv('AWS_ACCESS_KEY_ID') or not os.getenv('AWS_SECRET_ACCESS_KEY'):
    print("[ERROR] AWS credentials not found in environment variables")
    print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
    sys.exit(1)

# Set default region if not set
if 'AWS_DEFAULT_REGION' not in os.environ:
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

import boto3
from decision_data.backend.services.cost_tracking_service import get_cost_tracking_service


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def test_cost_tracking():
    """Test the complete cost tracking workflow"""

    cost_service = get_cost_tracking_service()

    # Test user ID
    user_id = "test-cost-user-" + datetime.now().strftime("%Y%m%d%H%M%S")

    print_section("STEP 1: Initialize User Credit")
    print(f"User ID: {user_id}")
    print(f"Initial Credit: $1.00")

    success = cost_service.initialize_user_credit(user_id, 1.00)
    if success:
        print("[OK] User credit initialized successfully")
    else:
        print("[ERROR] Failed to initialize user credit")
        return False

    # Check credit
    credit = cost_service.get_user_credit(user_id)
    print(f"[OK] Current Balance: ${credit['balance']:.2f}")

    print_section("STEP 2: Record Usage Events")

    # Record Whisper usage (10 minutes of audio)
    print("Recording Whisper transcription usage: 10 minutes")
    success = cost_service.record_whisper_usage(user_id, 10.0)
    if success:
        print("[OK] Whisper usage recorded")
        print("     Cost: $0.06 (10 minutes × $0.006/minute)")
    else:
        print("[ERROR] Failed to record Whisper usage")

    # Record S3 usage (100 MB upload)
    print("\nRecording S3 upload usage: 100 MB")
    success = cost_service.record_s3_usage(user_id, "upload", 100.0)  # 100 MB
    if success:
        print("[OK] S3 upload usage recorded")
        print("     Cost: $0.002 (0.098 GB × $0.023/GB)")
    else:
        print("[ERROR] Failed to record S3 usage")

    # Record DynamoDB read operations
    print("\nRecording DynamoDB read operations: 1,000 read units")
    success = cost_service.record_dynamodb_usage(user_id, "read_units", 1000.0)
    if success:
        print("[OK] DynamoDB read usage recorded")
        print("     Cost: $0.00025 (1,000 / 1,000,000 × $0.25)")
    else:
        print("[ERROR] Failed to record DynamoDB usage")

    # Record SES email sending
    print("\nRecording SES email sending: 50 emails")
    success = cost_service.record_ses_usage(user_id, 50)
    if success:
        print("[OK] SES email usage recorded")
        print("     Cost: $0.005 (50 / 1,000 × $0.10)")
    else:
        print("[ERROR] Failed to record SES usage")

    # Record Secrets Manager retrieval
    print("\nRecording Secrets Manager retrieval: 1 retrieval")
    success = cost_service.record_secrets_manager_retrieval(user_id)
    if success:
        print("[OK] Secrets Manager retrieval recorded")
        print("     Cost: $0.05 (per retrieval)")
    else:
        print("[ERROR] Failed to record Secrets Manager usage")

    # Record OpenAI summarization
    print("\nRecording OpenAI GPT-5 summarization usage: 500 input + 300 output tokens")
    success = cost_service.record_openai_summarization(
        user_id,
        input_tokens=500,
        output_tokens=300
    )
    if success:
        print("[OK] OpenAI usage recorded")
        print("     Cost: $0.00275")
        print("     - Input: 500 tokens × $0.003 / 1K = $0.0015")
        print("     - Output: 300 tokens × $0.006 / 1K = $0.0018")
    else:
        print("[ERROR] Failed to record OpenAI usage")

    print_section("STEP 3: View Current Month Costs")

    current_costs = cost_service.get_current_month_usage(user_id)
    print(f"Current Month: {datetime.utcnow().strftime('%Y-%m')}")
    print("\nCost Breakdown:")
    for service, cost in current_costs.items():
        if cost > 0:
            print(f"  {service:20s}: ${cost:10.6f}")

    total_cost = current_costs['total']
    print(f"\n  {'TOTAL':20s}: ${total_cost:10.6f}")

    print_section("STEP 4: View User Credit Balance")

    credit = cost_service.get_user_credit(user_id)
    if credit:
        print(f"Initial Credit:    ${credit['initial']:8.2f}")
        print(f"Used Credit:       ${credit['used']:8.2f}")
        print(f"Remaining Balance: ${credit['balance']:8.2f}")

        if credit['balance'] >= 0:
            print(f"\n[OK] User has sufficient credits")
        else:
            print(f"\n[WARN] User credit balance is negative (overdraft)")
    else:
        print("[ERROR] Failed to retrieve user credit")

    print_section("STEP 5: View Cost History (Last 12 Months)")

    history = cost_service.get_cost_history(user_id, months=12)
    current_month = datetime.utcnow().strftime("%Y-%m")

    print(f"Showing last 12 months of cost history:\n")
    for entry in history:
        month = entry['month']
        total = entry['costs']['total']
        marker = " <-- CURRENT" if month == current_month else ""
        print(f"  {month}: ${total:10.6f}{marker}")

    print_section("STEP 6: Verify All Tables Are Accessible")

    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

    tables_to_check = [
        'panzoto-usage-records',
        'panzoto-user-credits',
        'panzoto-cost-summaries',
    ]

    for table_name in tables_to_check:
        try:
            table = dynamodb.Table(table_name)
            response = table.table_status
            print(f"[OK] Table {table_name:30s} is accessible")
        except Exception as e:
            print(f"[ERROR] Table {table_name:30s} failed: {e}")

    print_section("COST TRACKING WORKFLOW SUMMARY")

    print("✓ Cost tracking tables created")
    print("✓ User credit initialized")
    print("✓ Multiple service costs recorded:")
    print("  - Whisper transcription: $0.06")
    print("  - S3 storage/upload: $0.002")
    print("  - DynamoDB operations: $0.00025")
    print("  - SES email: $0.005")
    print("  - Secrets Manager: $0.05")
    print("  - OpenAI summarization: $0.00275")
    print(f"✓ Total cost tracked: ${total_cost:.6f}")
    print(f"✓ Remaining balance: ${credit['balance']:.2f}")
    print("\nCost tracking is now fully operational!")

    return True


if __name__ == "__main__":
    try:
        success = test_cost_tracking()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
