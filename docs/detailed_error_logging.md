# Detailed Error Logging for Job Processing

**Version:** 1.0
**Status:** ✅ Implemented October 19, 2025

## Overview

All job processing errors now include detailed logging at every step. Instead of just "job failed", you'll see exactly where it failed with full context.

## Log Entry Points

### 1. Job Processing Start
```
[AUDIO] Processing job {job_id} (attempt {count}/{max}) for user {user_id}
```
Shows which attempt this is (e.g., attempt 1/3)

### 2. Database Queries
```
[FETCH] Retrieving audio file metadata
```
If this fails with an error, you'll see:
```
[ERROR] Failed to fetch audio file {audio_file_id}: {detailed_error}
```

### 3. S3 Download
```
[S3] Downloading encrypted file from S3: {s3_key}
[S3] Downloaded {bytes} bytes from S3
```
If S3 fails:
```
[S3 ERROR] Failed to download from S3: {detailed_error}
```

### 4. Encryption Key Retrieval
```
[KEY] Fetching encryption key from Secrets Manager for user {user_id}
[KEY] Encryption key found (length: {length} chars)
```
If key is missing:
```
[KEY ERROR] Encryption key not found in Secrets Manager for user {user_id}
```

### 5. Decryption
```
[DECRYPT] Decrypting {bytes} bytes with AES-256-GCM
[DECRYPT] Successfully decrypted to {bytes} bytes
```
If decryption fails:
```
[DECRYPT ERROR] Decryption failed: {detailed_error}
```

### 6. Duration Check
```
[DURATION] Checking audio duration
[DURATION] Audio duration: {duration}s (valid range: {min}-{max}s)
```

### 7. Transcription
```
[TRANSCRIBE] Sending to OpenAI Whisper...
[TRANSCRIBE] Received transcript ({chars} chars)
```
If too short:
```
[SKIP] Audio too short or empty transcription - silently completing job
```

### 8. Database Save
```
[SAVE] Saving transcript to database
[SAVE] Saved transcript {transcript_id}
```

### 9. Success
```
[SUCCESS] Job {job_id} completed with transcript {transcript_id}
```

## Reading Server Logs

### Get Recent Logs
```bash
ssh root@206.189.185.129 "tail -500 /var/log/api.log"
```

### Search for Errors
```bash
ssh root@206.189.185.129 "grep '\[ERROR\]' /var/log/api.log"
```

### Search for Specific Job
```bash
ssh root@206.189.185.129 "grep 'job_id_here' /var/log/api.log"
```

### Get Full Job Trace
```bash
ssh root@206.189.185.129 "grep 'job_12345' /var/log/api.log | tail -30"
```

## Example Log Sequence (Successful)

```
[AUDIO] Processing job abc123 (attempt 1/3) for user user-uuid
[FETCH] Retrieving audio file metadata
[S3] Downloading encrypted file from S3: audio_upload/...
[S3] Downloaded 8512 bytes from S3
[KEY] Fetching encryption key from Secrets Manager for user user-uuid
[KEY] Encryption key found (length: 88 chars)
[DECRYPT] Decrypting 8512 bytes with AES-256-GCM
[DECRYPT] Successfully decrypted to 7489 bytes
[TEMP] Saved decrypted file to /path/to/temp
[DURATION] Checking audio duration
[DURATION] Audio duration: 15.3s (valid range: 1-60s)
[TRANSCRIBE] Sending to OpenAI Whisper...
[TRANSCRIBE] Received transcript (245 chars)
[SAVE] Saving transcript to database
[SAVE] Saved transcript transcript-uuid
[SUCCESS] Job abc123 completed with transcript transcript-uuid
```

## Example Log Sequence (Failed - Encryption Key Missing)

```
[AUDIO] Processing job abc123 (attempt 1/3) for user user-uuid
[FETCH] Retrieving audio file metadata
[S3] Downloading encrypted file from S3: audio_upload/...
[S3] Downloaded 8512 bytes from S3
[KEY] Fetching encryption key from Secrets Manager for user user-uuid
[KEY ERROR] Encryption key not found in Secrets Manager for user user-uuid
[ERROR] Job abc123 processing failed (attempt 1/3): Encryption key not found...
```

## Example Log Sequence (Failed - Decryption Error)

```
[AUDIO] Processing job abc123 (attempt 1/3) for user user-uuid
[FETCH] Retrieving audio file metadata
[S3] Downloading encrypted file from S3: audio_upload/...
[S3] Downloaded 8512 bytes from S3
[KEY] Fetching encryption key from Secrets Manager for user user-uuid
[KEY] Encryption key found (length: 88 chars)
[DECRYPT] Decrypting 8512 bytes with AES-256-GCM
[DECRYPT ERROR] Decryption failed: MAC check failed at byte 8496
[ERROR] Job abc123 processing failed (attempt 1/3): MAC check failed...
```

## Troubleshooting Guide

### Look for these patterns:

| Error Pattern | Meaning | Action |
|---------------|---------|--------|
| `[KEY ERROR]` | Encryption key missing/corrupt | Check AWS Secrets Manager |
| `[DECRYPT ERROR]` | MAC check failed | File corrupted or wrong key |
| `[S3 ERROR]` | Can't access S3 bucket | Check AWS credentials & permissions |
| `[DURATION]` + error | Audio outside time range | Check min/max duration config |
| `[TRANSCRIBE]` + no response | Whisper API timeout | Check OpenAI API status |
| No logs | Job never started | Check background processor running |

## Configuration for Enhanced Logging

All enhanced logging is **enabled by default**. No configuration needed.

Logs are written to:
- **Local development:** Console output + logging framework
- **Production:** `/var/log/api.log` (configured in deployment)

## Future Log Enhancements

- [ ] Add structured JSON logging for easier parsing
- [ ] Add CloudWatch integration for real-time monitoring
- [ ] Add Slack alerts for specific error patterns
- [ ] Add performance metrics (time per step)
- [ ] Add retry tracking in logs
