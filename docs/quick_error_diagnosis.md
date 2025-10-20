# Quick Error Diagnosis Guide

## When a Job Has "Exceeded maximum retries (3)"

### Step 1: SSH to Server
```bash
ssh root@206.189.185.129
```

### Step 2: Find the Job in Logs
Get the job_id from DynamoDB, then search:
```bash
grep "job_54fb3721" /var/log/api.log
```

### Step 3: Identify the Error Pattern

**If you see `[KEY ERROR]`:**
```
[KEY ERROR] Encryption key not found in Secrets Manager
```
→ **Problem:** User's encryption key is missing or corrupted
→ **Fix:** Check AWS Secrets Manager > panzoto/encryption-keys/{user_uuid}

**If you see `[DECRYPT ERROR]`:**
```
[DECRYPT ERROR] Decryption failed: MAC check failed
```
→ **Problem:** Wrong encryption key or corrupted file
→ **Fix:** Verify key in Secrets Manager matches what was used to encrypt

**If you see `[S3 ERROR]`:**
```
[S3 ERROR] Failed to download from S3: Access Denied
```
→ **Problem:** S3 permissions or file doesn't exist
→ **Fix:** Verify S3 bucket permissions and file exists in audio_upload/

**If you see `[DURATION]` error:**
```
[DURATION] Audio duration: 0.5s (valid range: 1-60s)
```
→ **Problem:** Audio file too short
→ **Fix:** This is expected for short recordings (not a real error)

**If you see no logs at all:**
```
→ **Problem:** Background processor not running
→ **Fix:** Check if uvicorn server is running: ps aux | grep uvicorn
```

## Quick Checks

### 1. Is Server Running?
```bash
ps aux | grep uvicorn
```
Should show the uvicorn process

### 2. Is ffmpeg Installed?
```bash
which ffmpeg
```
Should return: `/usr/bin/ffmpeg`

### 3. Is AWS Credentials Working?
```bash
aws s3 ls s3://panzoto
```
Should list S3 contents

### 4. Check Disk Space
```bash
df -h
```
Should have available space

### 5. Tail Recent Logs
```bash
tail -50 /var/log/api.log | grep ERROR
```

## Common Root Causes & Fixes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| All jobs fail same way | Server environment issue | Restart uvicorn |
| Specific user's jobs fail | Missing encryption key | Check Secrets Manager |
| Random jobs fail | API timeout | Check OpenAI status |
| Logs show permission error | AWS credentials issue | Verify AWS_ACCESS_KEY_ID |

## Get Help

1. **Check detailed logging docs:** `docs/detailed_error_logging.md`
2. **Check error handling guide:** `docs/JOB_ERROR_HANDLING.md`
3. **Run diagnostic script:** See next section

## Server Diagnostic Commands

```bash
# Check server status
ps aux | grep uvicorn

# View last 200 lines of API log
tail -200 /var/log/api.log

# Search for all errors in last 24 hours
grep "ERROR" /var/log/api.log | tail -50

# Check AWS S3 access
aws s3 ls s3://panzoto --recursive | head -20

# Check disk space
df -h /

# Check if ffmpeg works
ffmpeg -version
```

## When Nothing Works

Restart the server:
```bash
# Kill uvicorn process
pkill -9 -f uvicorn

# Wait 5 seconds
sleep 5

# Restart (replace path with actual path)
/root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn \
  decision_data.api.backend.api:app --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &
```

Then check logs again:
```bash
tail -100 /var/log/api.log
```
