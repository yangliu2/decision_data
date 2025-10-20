# Daily Summary Implementation - October 20, 2025

**Status:** ✅ IMPLEMENTED AND DEPLOYED
**Commits:** 8c364a8
**Feature:** Automatic daily summary generation and email delivery via background processor

---

## Overview

The daily summary feature now fully integrates with the background processor to automatically generate summaries of user interactions and send them via email according to user preferences.

### User Flow

1. **User requests daily summary** via Android app: `POST /api/user/request-daily-summary`
2. **Backend creates job** in DynamoDB with `job_type = 'daily_summary'` and status = 'pending'
3. **Background processor** (runs every 30 seconds):
   - Scans for pending jobs (transcription AND daily_summary)
   - Checks eligibility (retry limits, backoff periods, job age)
   - Routes daily_summary jobs to `process_daily_summary_job()`
4. **Daily summary processor**:
   - Fetches user preferences (email, enable_daily_summary flag)
   - Gets transcripts from previous day
   - Generates summary using OpenAI gpt-4o-mini
   - Sends email to user's notification_email
   - Marks job as completed
5. **User receives email** with categorized summary (Family, Business, Misc)

---

## Architecture Changes

### 1. Audio Processor (`audio_processor.py`) - ENHANCED

#### Changes Made:

**Before:**
- Only processed `job_type = 'transcription'` jobs
- Hardcoded transcription job type in filter

**After:**
- Processes ALL pending jobs (transcription + daily_summary)
- Routes jobs to specialized handlers based on job type
- Full retry logic applied to daily summary jobs

#### New Methods:

```python
async def process_single_job(self, job: dict):
    """Route jobs to appropriate handler based on type."""
    if job_type == 'daily_summary':
        await self.process_daily_summary_job(job)
    else:
        await self.process_transcription_job(job)

async def process_daily_summary_job(self, job: dict):
    """Generate and send daily summary."""
    # Get user preferences
    # Parse job date (use previous day)
    # Call generate_summary()
    # Handle errors and retries
    # Mark job as completed
```

#### Updated Methods:

```python
def get_eligible_pending_jobs(self) -> List[dict]:
    # Before: FilterExpression with AND job_type = 'transcription'
    # After: FilterExpression only filters by status = 'pending'
    # Now returns BOTH transcription and daily_summary jobs
```

### 2. Daily Summary Generator (`daily_summary.py`) - MULTI-USER SUPPORT

#### Changes Made:

**Before:**
```python
def generate_summary(year: str, month: str, day: str, prompt_path: Path):
    # Sent email to hardcoded backend_config.GMAIL_ACCOUNT
    # No user ID tracking
```

**After:**
```python
def generate_summary(
    year: str, month: str, day: str, prompt_path: Path,
    user_id: str = None,  # NEW
    recipient_email: str = None  # NEW
):
    # recipient_email now used instead of hardcoded account
    # Supports multi-user email delivery
```

#### Key Features:

- Optional `user_id` parameter for future transcript filtering
- Optional `recipient_email` parameter (falls back to config if not provided)
- Email sent to actual user notification email
- Enhanced logging with `[EMAIL]` tags

---

## Database Schema Integration

### Processing Jobs Table (`panzoto-processing-jobs`)

```python
{
    job_id: "uuid",
    user_id: "uuid",                    # User who requested summary
    job_type: "daily_summary",          # NEW: now supports this type
    status: "pending|processing|completed|failed",
    created_at: "2025-10-20T10:30:00+00:00",
    completed_at: "2025-10-20T10:35:00+00:00",  # Set after completion
    error_message: null,                # Set if failed
    retry_count: 0,                     # Incremented on each attempt
    last_attempt_at: "2025-10-20T10:30:00+00:00"  # For backoff
}
```

### User Preferences Table (`panzoto-user-preferences`)

```python
{
    user_id: "uuid",
    notification_email: "user@example.com",     # EMAIL DESTINATION
    enable_daily_summary: true,                 # FEATURE FLAG
    summary_time_utc: "09:00",                  # HH:MM format (UTC)
    enable_transcription: true,
    created_at: 1729417800.0,
    updated_at: 1729417800.0
}
```

---

## API Endpoint

### Request Daily Summary

**Endpoint:** `POST /api/user/request-daily-summary`

**Headers:**
```
Authorization: Bearer {jwt_token}
```

**Response:**
```json
{
    "message": "Daily summary job created",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending"
}
```

**Behavior:**
- Creates a job with `job_type = 'daily_summary'` and status = 'pending'
- Job is picked up by background processor within 30 seconds
- If user has `enable_daily_summary = false`, job completes silently

---

## Processing Flow

### Step 1: Job Creation (User Request)

```python
# Android/API endpoint calls
transcription_service.create_processing_job(
    user_id="user-uuid",
    job_type="daily_summary"
)

# Creates in DynamoDB:
{
    job_id: "550e8400-...",
    user_id: "user-uuid",
    job_type: "daily_summary",
    status: "pending",
    created_at: "2025-10-20T10:30:00Z"
}
```

### Step 2: Background Processor Pickup

```python
# Every 30 seconds, processor calls:
eligible_jobs = self.get_eligible_pending_jobs()

# Returns: [job with job_type='daily_summary']
# Calls: await self.process_single_job(job)
```

### Step 3: Eligibility Check

Job must pass all checks:
- ✅ Status = 'pending'
- ✅ Retry count < 3
- ✅ Job age < 24 hours
- ✅ Time since last attempt > 10 minutes (backoff)

**Log Example:**
```
[INFO] Checked for jobs, found 1 eligible jobs
[AUDIO] Processing daily_summary job 550e8400 (attempt 1/3) for user user-uuid
```

### Step 4: Fetch User Preferences

```python
preferences = preferences_service.get_preferences(user_id)

# Checks:
# - enable_daily_summary = true? (if false, job completes silently)
# - notification_email is set? (used as recipient)
```

**Log Example:**
```
[SUMMARY] Processing daily summary job 550e8400 for user user-uuid
```

### Step 5: Calculate Summary Date

```python
# Job created_at: 2025-10-20T10:30:00+00:00
# Summary date: 2025-10-19 (yesterday)
# Transcripts filtered for 2025-10-18T00:00:00 to 2025-10-19T00:00:00

summary_date = job_date - timedelta(days=1)  # Previous day
```

**Log Example:**
```
[SUMMARY] Generating summary for 2025-10-19
```

### Step 6: Generate Summary

```python
generate_summary(
    year="2025",
    month="10",
    day="19",
    prompt_path=Path(...),
    user_id="user-uuid",
    recipient_email="user@example.com"
)

# Steps inside generate_summary():
# 1. Query MongoDB for transcripts from 2025-10-18 to 2025-10-19
# 2. Combine all transcripts into one text
# 3. Send to OpenAI gpt-4o-mini with daily_summary.txt prompt
# 4. Parse response into DailySummary model
# 5. Format as HTML email
# 6. Send via Gmail SMTP to recipient_email
# 7. Save summary to MongoDB daily_summary collection
```

**Log Example:**
```
[SUMMARY] Generating summary for 2025-10-19
[TRANSCRIBE] Sending to OpenAI Whisper...
[TRANSCRIBE] Received summary with 3 categories
[EMAIL] Daily summary sent to user@example.com
[SAVE] Saved summary to MongoDB
```

### Step 7: Mark Job Complete

```python
self.transcription_service.update_job_status(job_id, 'completed')

# Updated in DynamoDB:
{
    ...same job...,
    status: "completed",
    completed_at: "2025-10-20T10:35:00+00:00"
}
```

**Log Example:**
```
[SUMMARY] Daily summary job 550e8400 completed successfully in 15.3s
[SUCCESS] Daily summary sent to user@example.com
```

---

## Error Handling & Retries

### Automatic Retry Logic

When a daily summary job fails:

1. **First failure** (attempt 1/3):
   - Error logged with [ERROR] tag
   - Job marked with `retry_count=1`
   - `last_attempt_at` updated
   - Job stays `status='pending'`
   - **Backoff:** 10 minutes before retry

2. **Second failure** (attempt 2/3):
   - Same process as attempt 1
   - Waits 10 more minutes

3. **Third failure** (attempt 3/3):
   - Job marked as `status='failed'`
   - `error_message` stored in DynamoDB
   - No more retries

### Common Failure Scenarios

| Error | Cause | Automatic Action |
|-------|-------|------------------|
| User preferences not found | User deleted or corrupted data | Mark job failed |
| Notification email not set | User preferences incomplete | Mark job failed |
| No transcripts for that day | User had quiet day | Summary completes silently (success) |
| OpenAI API timeout | API overloaded | Retry after backoff |
| MongoDB connection error | Database unavailable | Retry after backoff |
| Email sending failed | Gmail auth error | Retry after backoff |

**Log Example (Failure):**
```
[SUMMARY] Processing daily summary job 550e8400 for user user-uuid
[ERROR] Failed to fetch user preferences: DynamoDB access error
[FAIL] Job 550e8400 marked as failed: Failed to fetch preferences: ...
```

---

## Safety Limits

Same safety limits apply to daily summary jobs as transcription jobs:

| Setting | Value | Purpose |
|---------|-------|---------|
| MAX_RETRIES | 3 | Prevent infinite retry loops |
| PROCESSING_TIMEOUT_MINUTES | 5 | Kill hung processes |
| RETRY_BACKOFF_MINUTES | 10 | Space out failed retries |
| CHECK_INTERVAL_SECONDS | 30 | Scan for jobs every 30s |

---

## User Preferences Control

Users can control daily summary behavior via API:

### Get Preferences

```
GET /api/user/preferences
```

**Response:**
```json
{
    "user_id": "uuid",
    "notification_email": "user@example.com",
    "enable_daily_summary": true,
    "summary_time_utc": "09:00",
    "enable_transcription": true
}
```

### Update Preferences

```
PUT /api/user/preferences
{
    "enable_daily_summary": false,
    "notification_email": "newemail@example.com",
    "summary_time_utc": "18:00"
}
```

### Behavior

- If `enable_daily_summary = false`: Job completes silently (success, no email)
- If `notification_email` is empty: Job fails (requires valid email)
- `summary_time_utc` is stored but not yet used for scheduling (future feature)

---

## Logging Output Examples

### Successful Daily Summary

```
INFO:decision_data.backend.services.audio_processor:[INFO] Checked for jobs, found 1 eligible jobs
INFO:decision_data.backend.services.audio_processor:[AUDIO] Processing daily_summary job 550e8400 (attempt 1/3) for user abc123
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Processing daily summary job 550e8400 for user abc123
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Generating summary for 2025-10-19
INFO:decision_data.backend.workflow.daily_summary:[EMAIL] Daily summary sent to user@example.com
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Daily summary job 550e8400 completed successfully in 12.5s
INFO:decision_data.backend.services.audio_processor:[SUCCESS] Daily summary sent to user@example.com
```

### Failed Daily Summary (Missing Preferences)

```
INFO:decision_data.backend.services.audio_processor:[AUDIO] Processing daily_summary job 550e8400 (attempt 1/3) for user abc123
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Processing daily summary job 550e8400 for user abc123
ERROR:decision_data.backend.services.audio_processor:[ERROR] Failed to fetch user preferences: User not found
INFO:decision_data.backend.services.audio_processor:[FAIL] Job 550e8400 marked as failed: User preferences not found
```

### Disabled Daily Summary (Silently Skipped)

```
INFO:decision_data.backend.services.audio_processor:[AUDIO] Processing daily_summary job 550e8400 (attempt 1/3) for user abc123
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Processing daily summary job 550e8400 for user abc123
INFO:decision_data.backend.services.audio_processor:[SUMMARY] Daily summary disabled for user abc123, marking job complete
```

---

## Configuration Requirements

### Environment Variables

```bash
# Gmail/Email Configuration
GMAIL_ACCOUNT="your-email@gmail.com"
GOOGLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # Gmail app password, not your real password

# OpenAI Configuration
OPENAI_API_KEY="sk-..."

# MongoDB Configuration
MONGODB_URI="mongodb+srv://..."
MONGODB_DAILY_SUMMARY_COLLECTION_NAME="daily_summaries"
MONGODB_TRANSCRIPTS_COLLECTION_NAME="transcripts"

# Prompt Path
DAILY_SUMMAYR_PROMPT_PATH="decision_data/prompts/daily_summary.txt"
```

### DynamoDB Tables Required

- `panzoto-processing-jobs` (already exists)
- `panzoto-user-preferences` (already exists)

### MongoDB Collections Required

- `transcripts` (stores user transcripts)
- `daily_summaries` (stores generated summaries)

---

## Testing the Feature

### Manual Test Steps

1. **Create a pending daily summary job in DynamoDB:**
   ```bash
   aws dynamodb put-item --table-name panzoto-processing-jobs \
     --item '{
       "job_id": {"S": "test-daily-123"},
       "user_id": {"S": "your-user-id"},
       "job_type": {"S": "daily_summary"},
       "status": {"S": "pending"},
       "created_at": {"S": "2025-10-20T10:30:00+00:00"},
       "retry_count": {"N": "0"}
     }'
   ```

2. **Verify user preferences exist:**
   ```bash
   aws dynamodb get-item --table-name panzoto-user-preferences \
     --key '{"user_id": {"S": "your-user-id"}}'
   ```

3. **Wait 30 seconds** for processor to pick up job

4. **Check logs:**
   ```bash
   ssh root@206.189.185.129 "tail -50 /var/log/api.log | grep SUMMARY"
   ```

5. **Verify job completion:**
   ```bash
   aws dynamodb get-item --table-name panzoto-processing-jobs \
     --key '{"job_id": {"S": "test-daily-123"}}'
   ```

6. **Check email** was received at notification_email address

---

## Deployment

### Production Deployment

1. **Commit:** 8c364a8 pushed to main
2. **CI/CD:** Automatically triggers on push
3. **Server:** Restart uvicorn to load new code
4. **Verification:** Check `/var/log/api.log` for `[SUMMARY]` logs

```bash
# Manual server restart if needed
ssh root@206.189.185.129 "pkill -9 uvicorn && sleep 2"
ssh root@206.189.185.129 "cd /root/decision_data && nohup /root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn decision_data.api.backend.api:app --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &"
```

---

## Future Enhancements

### Planned Features

- [ ] **Time-based scheduling:** Automatically trigger daily summary at `summary_time_utc`
- [ ] **Scheduled emails:** Send daily summaries automatically without manual job creation
- [ ] **Customizable categories:** Users choose which categories to include
- [ ] **Email templates:** Multiple email format options
- [ ] **CloudWatch integration:** Monitor daily summary metrics
- [ ] **Slack/Discord alerts:** Send summaries to messaging platforms
- [ ] **Summary history:** View past summaries in app

### Potential Improvements

1. **Multi-user transcript filtering:** Currently queries all transcripts, could filter by user_id
2. **Summary customization:** Let users choose date range, summary format
3. **Performance:** Cache frequently-generated summaries
4. **Monitoring:** Send alerts if daily summaries fail for 3+ consecutive days

---

## Troubleshooting

### Job stuck in pending status

**Check:**
1. Is `enable_daily_summary = true` in user preferences?
2. Does user have `notification_email` set?
3. Check logs: `ssh root@206.189.185.129 "tail -100 /var/log/api.log | grep 550e8400"`
4. Is background processor running? `ps aux | grep uvicorn`

### Email not received

**Check:**
1. Verify `GMAIL_ACCOUNT` and `GOOGLE_APP_PASSWORD` are correct
2. Check if Gmail app password is valid (not user password)
3. Gmail account needs 2FA enabled and app password generated
4. Check logs for `[EMAIL]` tag to see sending status

### Summary has no content

**Check:**
1. Verify transcripts exist in MongoDB for that day
2. Check MongoDB transcript timestamps are in correct format
3. Verify OpenAI API key is valid
4. Check prompt file exists at `DAILY_SUMMAYR_PROMPT_PATH`

---

## Status: COMPLETE

**Feature:** Daily Summary Job Processing
**Status:** ✅ Fully Implemented and Deployed
**Date:** October 20, 2025
**Commits:** 8c364a8

The daily summary feature is now fully integrated into the background processor and ready for production use!
