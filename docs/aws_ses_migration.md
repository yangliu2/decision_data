# AWS SES Migration Guide

## Overview

The daily summary email system has been migrated from Gmail SMTP to **AWS SES (Simple Email Service)** for better reliability, higher throughput, and lower costs.

## What Changed

### Before (Gmail SMTP)
- Emails sent via `smtp.gmail.com:587`
- Server firewall blocked outbound SMTP connections
- No emails actually delivered
- Limited to 1,500 emails per day

### After (AWS SES)
- Emails sent via AWS SES API using boto3
- Uses existing AWS credentials (no new credentials needed)
- Reliable delivery with guaranteed email queuing
- 62,000 free emails per month
- Scales to millions with reasonable costs

## Pricing

### AWS SES Pricing (as of 2025)
```
First 62,000 emails/month:  FREE
Additional emails:          $0.10 per 1,000 emails

Example costs:
- 25 users × 30 days = 750 emails/month    → FREE (< 62K)
- 100 users × 30 days = 3,000 emails/month → FREE (< 62K)
- 200 users × 30 days = 6,000 emails/month → FREE (< 62K)
```

**Result: Most deployments pay $0/month for email**

## Configuration

### Required Environment Variables

Add these to your `.env` file:

```bash
# Email Provider Configuration
EMAIL_PROVIDER=aws_ses
EMAIL_SENDER=support@panzoto.com

# AWS Credentials (already used for DynamoDB/S3)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
REGION_NAME=us-east-1
```

### Optional Configuration

To fall back to Gmail SMTP (legacy):

```bash
EMAIL_PROVIDER=gmail
GMAIL_ACCOUNT=your_email@gmail.com
GOOGLE_APP_PASSWORD=your_app_password
```

## Implementation Details

### Email Service Architecture

```python
# decision_data/ui/email/email.py

def send_email(recipient_email, subject, message_body):
    """
    Sends email using configured provider (aws_ses or gmail).

    - Automatically selects provider based on EMAIL_PROVIDER config
    - Uses AWS SES client with existing AWS credentials
    - Falls back to Gmail SMTP if configured
    """
    provider = backend_config.EMAIL_PROVIDER.lower()

    if provider == "aws_ses":
        return send_email_aws_ses(recipient_email, subject, message_body)
    elif provider == "gmail":
        return send_email_gmail(recipient_email, subject, message_body)
```

### Daily Summary Changes

```python
# decision_data/backend/workflow/daily_summary.py

# NOW: Sends email even when no transcripts found
if not filtered_data:
    logger.info("No transcripts found, sending empty summary email")

    # Email sent with message: "No conversations recorded for this day"
    send_email(
        subject="PANZOTO: Daily Summary",
        message_body=formatted_message,
        recipient_email=final_recipient_email,
    )
    return  # Exit gracefully after sending
```

## Setup Steps

### Step 1: Verify Sender Email in AWS SES

AWS SES requires you to verify sender email addresses before production use.

```bash
# Via AWS Console
1. Go to: AWS SES → Verified Identities
2. Click: Create Identity
3. Select: Email address
4. Enter: support@panzoto.com
5. Check email inbox for verification link
6. Click verification link
```

Or via AWS CLI:

```bash
aws ses verify-email-identity \
    --email-address support@panzoto.com \
    --region us-east-1
```

### Step 2: Check SES Sending Limits

New AWS SES accounts start in **Sandbox Mode** (limited to 1 email/sec, 200 recipients/day).

```bash
# Check current limits
aws ses get-account-sending-enabled --region us-east-1

# Request production access (if needed)
# Go to: AWS SES → Account Dashboard → Request Production Access
```

### Step 3: Update Environment Variables

On your production server (DigitalOcean):

```bash
# SSH into server
ssh root@206.189.185.129

# Edit .env file
nano /root/decision_data/.env

# Add/update these lines:
EMAIL_PROVIDER=aws_ses
EMAIL_SENDER=support@panzoto.com
```

### Step 4: Restart Backend Server

```bash
# Stop old server
pkill -9 -f uvicorn

# Start new server with updated config
cd /root/decision_data
/root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn \
  decision_data.api.backend.api:app \
  --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &
```

## Verification

### Test Email Sending

```bash
# On production server
python3 << 'EOF'
import boto3
import os

os.environ['AWS_ACCESS_KEY_ID'] = 'your_key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'your_secret'

client = boto3.client('ses', region_name='us-east-1')

response = client.send_email(
    Source='support@panzoto.com',
    Destination={'ToAddresses': ['test@example.com']},
    Message={
        'Subject': {'Data': 'Test Email'},
        'Body': {'Html': {'Data': '<h1>Success!</h1>'}},
    },
)

print(f"Email sent! Message ID: {response['MessageId']}")
EOF
```

### Check Server Logs

```bash
# Watch for successful email sends
tail -f /var/log/api.log | grep "AWS SES"

# Expected output:
# [AWS SES] Email sent successfully. Message ID: 0000...
```

### Monitor AWS SES Sending

```bash
# Get today's send statistics
aws ses get-account-sending-enabled --region us-east-1

# Get bounce/complaint statistics
aws ses get-send-statistics --region us-east-1
```

## Troubleshooting

### Error: "Email address not verified in SES"

**Cause:** Sender email not verified in AWS SES
**Solution:** Verify the email in AWS SES console (see Step 1 above)

### Error: "Account is in Sandbox Mode"

**Cause:** AWS SES account still in sandbox (limited to verified recipients)
**Solution:** Request production access in AWS SES console → Account Dashboard

### Error: "Invalid credentials"

**Cause:** AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY incorrect
**Solution:** Verify credentials match those used for S3/DynamoDB

### No email received but server logs show success

**Cause:** Email went to spam folder or recipient's mail server rejected it
**Solution:**
1. Check spam/junk folder
2. Verify recipient email format
3. Check AWS SES bounce notifications
4. Ensure sender is verified in SES

## Rollback to Gmail SMTP

If you need to temporarily revert to Gmail:

```bash
# Update .env
EMAIL_PROVIDER=gmail
GMAIL_ACCOUNT=your_email@gmail.com
GOOGLE_APP_PASSWORD=your_app_password

# Restart server
pkill -9 -f uvicorn
# ... restart command above ...
```

## Code Changes Summary

### Files Modified
1. `decision_data/backend/config/config.py`
   - Added `EMAIL_PROVIDER` (default: "aws_ses")
   - Added `EMAIL_SENDER` (default: "support@panzoto.com")

2. `decision_data/ui/email/email.py`
   - Added `send_email_aws_ses()` function
   - Kept `send_email_gmail()` for backward compatibility
   - Updated `send_email()` to dispatch based on EMAIL_PROVIDER

3. `decision_data/backend/workflow/daily_summary.py`
   - Fixed silent failure: now sends email when no transcripts found
   - Email contains: "No conversations recorded for this day"
   - Dynamically fetches recipient email from user preferences

## Per-User Email Preferences

The system automatically respects each user's email settings:

```python
# Each user has preferences in DynamoDB:
{
  "user_id": "2dd93da1-8f94-494e-8248-ad66e2921932",
  "notification_email": "yangliu3456@gmail.com",
  "enable_daily_summary": true,
  "summary_time_utc": "12:00"
}

# Email is fetched at job processing time:
preferences = preferences_service.get_preferences(user_id)
recipient_email = preferences.notification_email

# So each user can have different email addresses without code changes
```

## Benefits

✅ **Reliability**: AWS SES handles retries and delivery guarantees
✅ **Firewall-Proof**: Uses HTTPS API instead of SMTP
✅ **Cost**: 62K free emails/month (covers most deployments)
✅ **Flexibility**: Easy to switch EMAIL_SENDER to any verified domain
✅ **Scalability**: Handles millions of emails with same AWS account
✅ **Integration**: Uses existing AWS credentials (no new secrets)
✅ **Complete Coverage**: Sends daily email even on quiet days

## Next Steps

1. Verify sender email in AWS SES console
2. Update `.env` with `EMAIL_PROVIDER=aws_ses`
3. Restart backend server
4. Monitor `/var/log/api.log` for successful sends
5. Check daily summary emails arrive at scheduled time

## References

- [AWS SES Documentation](https://docs.aws.amazon.com/ses/)
- [AWS SES Pricing](https://aws.amazon.com/ses/pricing/)
- [Boto3 SES Client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html)
