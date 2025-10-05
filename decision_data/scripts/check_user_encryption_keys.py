"""
Check if users have encryption keys in AWS Secrets Manager.

Usage:
    python decision_data/scripts/check_user_encryption_keys.py
"""

import boto3
from dotenv import load_dotenv
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from decision_data.backend.services.user_service import UserService
from decision_data.backend.utils.secrets_manager import secrets_manager

load_dotenv()

def check_encryption_keys():
    """Check encryption key status for all users."""

    print("="*60)
    print("USER ENCRYPTION KEY CHECKER")
    print("="*60)
    print()

    # Get all users
    user_service = UserService()

    try:
        response = user_service.users_table.scan()
        users = response['Items']

        print(f"📊 Found {len(users)} users in DynamoDB")
        print()

        users_without_keys = []

        for user in users:
            user_id = user['user_id']
            email = user['email']

            # Check if encryption key exists
            encryption_key = secrets_manager.get_user_encryption_key(user_id)

            if encryption_key:
                print(f"✅ {email}")
                print(f"   User ID: {user_id}")
                print(f"   Key: {encryption_key[:20]}... (exists)")
            else:
                print(f"❌ {email}")
                print(f"   User ID: {user_id}")
                print(f"   Key: MISSING")
                users_without_keys.append((user_id, email))

            print()

        # Summary
        print("="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total users: {len(users)}")
        print(f"Users with keys: {len(users) - len(users_without_keys)}")
        print(f"Users without keys: {len(users_without_keys)}")
        print()

        # Offer to create missing keys
        if users_without_keys:
            print("⚠️  The following users are MISSING encryption keys:")
            for user_id, email in users_without_keys:
                print(f"   - {email} ({user_id})")
            print()

            create_keys = input("Do you want to create missing keys? (yes/no): ")

            if create_keys.lower() == 'yes':
                print("\n🔑 Creating encryption keys...")
                for user_id, email in users_without_keys:
                    try:
                        secrets_manager.store_user_encryption_key(user_id)
                        print(f"   ✅ Created key for {email}")
                    except Exception as e:
                        print(f"   ❌ Failed for {email}: {e}")

                print("\n✅ Key creation complete!")
                print("\n📱 Users must now:")
                print("   1. Logout of Android app")
                print("   2. Login again to fetch new encryption keys")
        else:
            print("✅ All users have encryption keys!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_encryption_keys()
