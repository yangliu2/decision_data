# CLAUDE.md - Consolidated Guidance

**Decision Data** - Audio transcription system with automatic speech-to-text via OpenAI Whisper. Three components: Android app (Panzoto), FastAPI backend, AWS infrastructure (S3, DynamoDB).

---

## Quick Commands

### Development
```bash
poetry install
uvicorn decision_data.api.backend.api:app --reload
pytest
```

### Server Management
```bash
# Check health
curl http://206.189.185.129:8000/api/health

# View logs
ssh root@206.189.185.129 "tail -f /var/log/api.log"

# Restart server
ssh root@206.189.185.129 "pkill -9 -f uvicorn && cd /root/decision_data && \
/root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn \
decision_data.api.backend.api:app --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &"
```

---

## Architecture Summary

```
Android App (Panzoto) → FastAPI Backend (DigitalOcean) → AWS (S3, DynamoDB, Secrets Manager)
  ↓                          ↓                                ↓
- Audio recording        - JWT auth                      - Encrypted storage
- AES-256 encryption     - Presigned URLs                - User isolation
- S3 upload              - Job processing                - OpenAI Whisper API
```

**Key Flow:** Record → Encrypt → Upload to S3 → Create DynamoDB job → Background processor transcribes → Save to DynamoDB → User sees transcript

---

## Project Structure

```
decision_data/
├── api/backend/api.py              # FastAPI endpoints + background processor
├── backend/services/               # Core logic (user, audio, transcription, preferences)
├── backend/transcribe/whisper.py   # OpenAI Whisper + 3gp→mp3 conversion
├── backend/config/config.py        # Environment variables
├── data_structure/models.py        # All Pydantic models
└── tests/                          # Integration tests

Panzoto/ (Android)
├── MainActivity.kt                 # Audio recording, encryption, upload
├── FileEncryptor.kt                # AES-256-GCM encryption
├── service/AuthService.kt          # API calls
└── config/AppConfig.kt             # Backend URL configuration
```

---

## DynamoDB Tables

| Table | Key | Purpose |
|-------|-----|---------|
| panzoto-users | user_id | User accounts |
| panzoto-audio-files | file_id | Audio metadata |
| panzoto-transcripts | transcript_id | Transcribed text |
| panzoto-processing-jobs | job_id | Job queue (pending/completed/failed) |
| panzoto-user-preferences | user_id | User settings |

---

## API Endpoints (Essential)

- `POST /api/register`, `POST /api/login` - Authentication
- `GET /api/user/encryption-key` - Fetch encryption key for client
- `GET /api/presigned-url?key=...` - Generate S3 upload URL
- `POST /api/audio-file` - Create audio record (triggers transcription job)
- `GET /api/user/transcripts?limit=50` - Get transcripts
- `GET /api/user/processing-jobs?limit=20` - Get job status
- `GET /api/health` - Server health

---

## Code Style

- **No emojis in code** - Use `[OK]`, `[ERROR]`, `[WARN]`, `[INFO]`
- **Python:** Decimal for DynamoDB, proper logging
- **Kotlin:** Use `Dispatchers.IO` for network calls
- **Android config:** Backend URL in `strings.xml` (not hardcoded)

---

## One-Time Scripts (decision_data/scripts/)

Before creating new scripts, check `decision_data/scripts/` for existing patterns and reuse them.

**Key scripts:**
- `migrate_encrypt_transcripts.py` - Encrypt existing plaintext transcripts (16 transcripts → encrypted)
- `migrate_recorded_at.py` - Add recording timestamps to old audio files
- `migrate_job_timestamps.py` - Update job timestamps to match recording times
- `cleanup_failed_jobs.py` - Remove failed jobs from DynamoDB
- `check_audio_status.py` - Diagnostic: audit audio pipeline status

**Pattern:**
All one-time scripts should:
1. Support `--dry-run` flag for testing
2. Provide clear summary reports
3. Handle errors gracefully (skip individual items, report at end)
4. Live in `decision_data/scripts/` directory

---

## What's Been Done (Summary)

### October 22, 2025 ✅
- **Fixed:** Missing `/api/presigned-url` endpoint (critical blocker)
- **Fixed:** Android app was hardcoded to broken AWS Lambda endpoint
- **Fixed:** Completed MongoDB removal from daily_summary.py
- **Cleaned:** Removed 3 failed jobs from DynamoDB
- **Implemented:** Transcript encryption in DynamoDB
  - Created reusable `AESEncryption` utility class (`backend/utils/aes_encryption.py`)
  - Updated `transcription_service.py` to encrypt transcripts before storing
  - Transcripts encrypted with user's AES-256-GCM key (same as audio)
  - Only plaintext returned to users (decrypted on read)
  - Encrypted 16 existing plaintext transcripts via migration script
  - Service provider cannot see plaintext transcripts in database
- **Status:** Audio pipeline 100% operational, transcripts encrypted at rest

### October 19, 2025 ✅
- Added timestamp tracking (`recorded_at` vs `uploaded_at`)
- Cleaned up 39 legacy failed jobs from DynamoDB

### October 6, 2025 ✅
- Fixed encryption IV length (12→16 bytes)
- Added automatic 3gp→mp3 conversion
- Implemented automatic background transcription

### Earlier ✅
- Complete AES-256-GCM encryption pipeline
- Multi-user isolation with per-user encryption keys
- JWT authentication (30-day tokens)
- Automatic daily summary generation (DynamoDB only)
- Android UI improvements (Material3, color scheme)

---

## What's Next (Priority Order)

### 1. Background Recording Feature (6-7 days effort)
**Current:** Recording stops when app backgrounded
**Goal:** Enable continuous background recording with optional stop time

**Phases:**
1. Backend: Add preferences for `enable_background_recording` + `recording_stop_time_utc`
2. Android: Implement Foreground Service + WorkManager for background recording
3. UI: Settings screen toggles + time picker
4. Testing: Verify recording continues when screen off/app backgrounded

**Reference:** `docs/BACKGROUND_RECORDING_IMPLEMENTATION.md`

### 2. User Decision Profile System (Future)
- Extract decisions from transcripts
- Build decision profiles
- Track patterns over time
- Visualize trends

### 3. Additional Features (Lower Priority)
- Batch transcript export
- Search/filter transcripts
- Transcript editing
- Push notifications

---

## Diagnostic Tools

```bash
# Check audio pipeline health
python check_audio_status.py

# Test backend connectivity
python test_backend_connectivity.py

# Clean up failed jobs
python cleanup_failed_jobs.py
```

---

## Common Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Encryption MAC failure | IV length mismatch or key mismatch | Rebuild Android app, clear data, re-login |
| Audio not uploading | Missing presigned URL endpoint | Use `/api/presigned-url` endpoint (fixed Oct 22) |
| Jobs stuck in processing | Server crashed | Check logs for "[START] Starting processor..." |
| Float types not supported | DynamoDB rejects floats | Use `Decimal(str(value))` in Python |
| Android network errors | Running on main thread | Use `Dispatchers.IO` for network calls |

---

## Critical Configuration

**Backend (.env):**
- AWS credentials (S3, DynamoDB, Secrets Manager)
- OpenAI API key
- JWT secret

**Android (strings.xml):**
```xml
<string name="backend_base_url">http://206.189.185.129:8000/api</string>
```

**Encryption:**
- IV: 16 bytes (MUST match between Android and backend)
- Algorithm: AES-256-GCM
- Tag length: 128 bits
- Key storage: AWS Secrets Manager (`panzoto/encryption-keys/{user_id}`)

---

## Testing

```bash
pytest tests/test_audio_workflow.py -v           # Specific test
pytest --cov=decision_data tests/                # With coverage
tox                                              # All checks (lint, type, test)
```

**Validates:** User registration, encryption, audio upload, API endpoints, job creation

---

## Deployment

- Push to `main` → Auto-deploys via GitHub Actions
- Server: DigitalOcean droplet (206.189.185.129)
- Uvicorn handles FastAPI
- Background processor runs on startup
- ffmpeg required for audio format conversion

---

## Documentation Files (For Reference)

- `docs/PRESIGNED_URL_FIX.md` - Audio upload pipeline details
- `docs/BACKGROUND_RECORDING_IMPLEMENTATION.md` - Next feature spec
- `docs/MONGODB_REMOVAL_DATA_PRIVACY.md` - Completed MongoDB migration
- `docs/AUTOMATIC_TRANSCRIPTION.md` - How background processing works

---

## Current Status

**Production Ready** ✅
- Audio pipeline: 100% operational
- Data privacy: MongoDB completely removed
- Background processing: Working smoothly
- Transcription: 30-second average turnaround
- Zero critical errors in logs

**Last Updated:** October 22, 2025
**System Version:** 1.0.0 (DynamoDB-only, MongoDB removed)
