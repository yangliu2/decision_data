# Processing Job Error Handling Strategy

**Last Updated:** October 19, 2025
**Status:** Production

---

## Overview

The `panzoto-processing-jobs` table in DynamoDB tracks background transcription jobs. Over time, failed jobs accumulate due to various error conditions. This guide explains how to detect, categorize, and clean up job errors systematically.

## Error Categories

### 1. LEGACY_ENCRYPTION (Most Common)

**Error Message:**
```
Automatic decryption not yet implemented - requires manual trigger
```

**Root Cause:**
- Audio files encrypted with OLD client-side encryption scheme
- Created before October 6, 2025 migration
- Background processor cannot decrypt these automatically

**Timeline:** October 9, 2025 - Present
**Count:** ~34 failed jobs (Oct 19)

**Solution:**
```bash
# Option A: Clean up jobs AND associated audio files from S3
python -m decision_data.scripts.smart_cleanup_jobs

# Option B: Clean up just the jobs (keep audio files)
python -m decision_data.scripts.cleanup_processing_jobs -y
```

**Prevention:**
- Don't import old audio files after migration
- Ensure all new recordings use server-managed encryption
- Verify encryption key is fetched from `/api/user/encryption-key` on each login

---

### 2. MAX_RETRIES

**Error Message:**
```
Exceeded maximum retries (3)
```

**Root Cause:**
- Job failed 3 times consecutively
- Each retry failed for same underlying reason
- Job was auto-failed to prevent infinite loops

**Timeline:** October 9 - Present
**Count:** ~10 failed jobs (Oct 19)

**Common Underlying Issues:**
- Decryption failure (wrong key, corrupted file)
- Transcription API timeout
- Audio format not supported
- File size exceeds limits

**Diagnosis:**
1. Check server logs for detailed error messages:
   ```bash
   ssh root@206.189.185.129 "tail -f /var/log/api.log | grep ERROR"
   ```

2. Run enhanced check script:
   ```bash
   python -m decision_data.scripts.check_jobs -v
   ```

**Solution:**
- Manually review logs to find root cause
- Fix the underlying issue
- Clean up failed job and retry from client

**Prevention:**
- Monitor logs continuously
- Alert on repeated job failures
- Implement circuit breaker for failing audio files

---

### 3. TRANSCRIPTION_FAILED

**Error Message:**
```
Transcription failed or too short
```

**Root Cause:**
- Audio duration < 1 second
- OpenAI Whisper API error
- Empty/silent audio

**Timeline:** October 9 - Present
**Count:** ~5 failed jobs (Oct 19)

**Solution:**
1. Check audio duration in DynamoDB `panzoto-audio-files` table
2. If too short: Safe to delete
3. If API error: Retry job or check OpenAI status

**Prevention:**
- Enforce minimum 3-second recording on client
- Validate audio before transcription
- Add exponential backoff for API retries

---

### 4. DECRYPTION_ERROR

**Error Message:**
```
MAC check failed
```

**Root Cause:**
- AES-256-GCM authentication tag verification failed
- Possible causes:
  - Wrong encryption key
  - Corrupted encrypted file
  - IV length mismatch

**Solution:**
- Delete the job and associated audio file
- User re-records audio

**Prevention:**
- Ensure consistent IV length (16 bytes)
- Validate encryption key on client before upload
- Add file integrity checks

---

### 5. FORMAT_ERROR

**Error Message:**
```
File does not start with RIFF id
```

**Root Cause:**
- ffmpeg conversion failed (3gp → mp3)
- Invalid audio file format

**Solution:**
```bash
# Verify ffmpeg installed on server
ssh root@206.189.185.129 "which ffmpeg"

# Reinstall if needed
ssh root@206.189.185.129 "apt-get install -y ffmpeg"
```

**Prevention:**
- Validate audio format on client before upload
- Add format detection on server
- Test ffmpeg during deployment

---

### 6. TIMEOUT

**Error Message:**
```
Transcription processing timeout
```

**Root Cause:**
- Job processing took > 5 minutes
- OpenAI Whisper API slow
- Network latency

**Solution:**
- Retry job (may succeed if temporary issue)
- Increase timeout limit if legitimate

**Prevention:**
- Implement longer timeout for large files
- Use OpenAI Whisper API v2 if available
- Monitor API performance

---

## Tools & Commands

### 1. Check Job Status (Enhanced)

```bash
# Quick summary with error categories
python -m decision_data.scripts.check_jobs

# Detailed view with individual job IDs
python -m decision_data.scripts.check_jobs -v
```

**Output:**
```
[SUMMARY] Status Breakdown:
  ✅ completed: 9
  ❌ failed:    49
  ⏳ pending:   2

[ERROR CATEGORIES]
  legacy_encryption: 34
  max_retries: 10
  transcription_failed: 5

[DETAILED ERROR BREAKDOWN]
  LEGACY_ENCRYPTION (34 jobs):
    → SOLUTION: Delete these audio files from S3

  MAX_RETRIES (10 jobs):
    → SOLUTION: Check logs, fix root cause, retry

  TRANSCRIPTION_FAILED (5 jobs):
    → SOLUTION: May need manual review
```

---

### 2. Smart Cleanup (Selective)

```bash
python -m decision_data.scripts.smart_cleanup_jobs
```

**Interactive Menu:**
```
[MENU] Select cleanup options:
  1. Legacy encryption jobs
  2. Max retries jobs
  3. Transcription failed jobs
  4. All failed jobs
  5. Skip cleanup
```

**Features:**
- Select which error categories to clean
- Shows count before deletion
- Optionally delete associated S3 files
- Progress tracking

---

### 3. Bulk Cleanup (All Jobs)

```bash
# Delete ALL jobs (asks for confirmation)
python -m decision_data.scripts.cleanup_processing_jobs

# Delete ALL jobs WITHOUT asking (auto-confirm)
python -m decision_data.scripts.cleanup_processing_jobs -y

# Additionally delete all transcripts
cleanup_processing_jobs -y  # Then answer "yes" to transcript cleanup
```

---

## Cleanup Procedures

### Procedure 1: Clean Up Only Old Legacy Jobs

```bash
# Step 1: Check what's there
python -m decision_data.scripts.check_jobs

# Step 2: Run smart cleanup
python -m decision_data.scripts.smart_cleanup_jobs

# Step 3: Select option "1" (Legacy encryption)
# Step 4: Confirm with "DELETE"
# Step 5: Choose to also delete S3 files
```

---

### Procedure 2: Clean Up After Development/Testing

```bash
# Wipe everything
python -m decision_data.scripts.cleanup_processing_jobs -y

# Step 1: Asks to delete all processing jobs → auto-confirms
# Step 2: Asks to delete all transcripts
#   - Type "yes" to also delete transcripts
#   - Type "no" to keep transcripts
```

---

### Procedure 3: Manual Query & Cleanup

```python
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
jobs_table = dynamodb.Table('panzoto-processing-jobs')

# Query specific user's failed jobs
response = jobs_table.query(
    IndexName='user-jobs-index',
    KeyConditionExpression='user_id = :uid',
    ExpressionAttributeValues={':uid': 'user-uuid-here'}
)

# Delete specific job
jobs_table.delete_item(Key={'job_id': 'job-uuid-here'})
```

---

## Prevention & Monitoring

### 1. Prevent Legacy Encryption Jobs

**On Android App:**
```kotlin
// Ensure encryption key is fetched at login
val encryptionKey = authService.getEncryptionKey()

// Verify it's not null/empty before recording
if (encryptionKey.isEmpty()) {
    showError("Encryption key not initialized. Please login again.")
    return
}
```

**On Backend:**
- Only accept files encrypted with server-managed keys
- Reject files encrypted with old client-side scheme
- Log rejected uploads for monitoring

### 2. Monitor for Repeated Failures

**Add CloudWatch Alert:**
```bash
# Alert if > 5 failed jobs in 24 hours
aws cloudwatch put-metric-alarm \
    --alarm-name panzoto-job-failures \
    --metric-name FailedJobCount \
    --namespace Panzoto \
    --statistic Sum \
    --period 86400 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold
```

### 3. Implement Job Monitoring Script

```python
# Run every hour via cron
python -m decision_data.scripts.check_jobs > /var/log/job_status.log

# Parse log and alert if:
# - failed jobs > 20
# - legacy_encryption jobs > 10
# - pending jobs stuck > 1 hour
```

### 4. Server Deployment Checklist

Before deployment, verify:
- [ ] ffmpeg installed (`apt-get install ffmpeg`)
- [ ] OpenAI API key valid
- [ ] AWS Secrets Manager has encryption keys
- [ ] S3 bucket permissions correct
- [ ] DynamoDB tables exist and accessible
- [ ] Python dependencies installed (`poetry install`)
- [ ] Background processor started successfully

---

## Error Response Times

| Error Type | Detection Time | Impact | Fix Time |
|-----------|---------------|--------|----------|
| Legacy Encryption | Immediate (retry loop) | User sees failed job | Manual cleanup required |
| Max Retries | ~10-15 minutes | User waits, job eventually fails | Check logs, 5-10 min debugging |
| Transcription Failed | Immediate | User gets failed status | User re-records or skips |
| Decryption Error | Immediate | User can't recover | Delete and re-upload |
| Format Error | Immediate | All audio fails | Fix ffmpeg, 5 min |
| Timeout | 5 minutes | User waits longer | Automatic retry or manual |

---

## Current Status (October 19, 2025)

### Jobs Summary
```
Total: 60 jobs
  ✅ Completed: 9 (15%)
  ❌ Failed: 49 (82%)
  ⏳ Pending: 2 (3%)
```

### Failed Jobs Breakdown
```
LEGACY_ENCRYPTION: 34 jobs
  → Created: Oct 9 (10 days old)
  → Status: Safe to delete
  → Action: Run smart_cleanup_jobs

MAX_RETRIES: 10 jobs
  → Created: Oct 9
  → Status: Needs investigation
  → Action: Check server logs

TRANSCRIPTION_FAILED: 5 jobs
  → Created: Oct 9 + Oct 6
  → Status: Mixed (old + new)
  → Action: Manual review
```

### Recommended Action
1. Run `python -m decision_data.scripts.check_jobs` to verify status
2. Run `python -m decision_data.scripts.smart_cleanup_jobs` and select "1"
3. Delete legacy_encryption jobs + S3 files
4. Keep max_retries and transcription_failed for investigation

---

## Future Improvements

- [ ] Auto-delete jobs older than 7 days if failed
- [ ] Add Slack/email alerts for job failures
- [ ] Implement exponential backoff for retries
- [ ] Add job metrics dashboard (success rate, avg processing time)
- [ ] Implement circuit breaker for repeatedly failing files
- [ ] Add health check endpoint for job processor
- [ ] Support job cancellation from client app
- [ ] Add job priority levels (urgent vs background)

---

## Related Documentation

- `docs/TRANSCRIPTION_FIX_COMPLETE.md` - Technical details on encryption fix
- `docs/AUTOMATIC_TRANSCRIPTION.md` - How background processor works
- `CLAUDE.md` - Project overview and configuration
- `docs/api_endpoints.md` - API documentation

---

**Questions?** Check the project README or review the latest server logs.
