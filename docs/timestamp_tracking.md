# Recording Timestamp Tracking

**Version:** 1.0
**Status:** ✅ Production Ready
**Updated:** October 19, 2025

## Overview

The system now captures and preserves the **actual recording start time** from the Android app, separate from when the file reached the server.

### Key Fields

| Field | Source | Purpose |
|-------|--------|---------|
| `recorded_at` | Android app | Exact time user started recording |
| `uploaded_at` | Backend server | When file upload API was called |
| `job.created_at` | Backend | Set to `recorded_at` for accuracy |

## Data Flow

```
Android App
├─ User taps record: startTimeMillis = System.currentTimeMillis()
├─ Convert to ISO 8601: "2024-10-18T15:30:00.000000Z"
└─ Send to backend: { s3_key, file_size, recorded_at }
    ↓
Backend API
├─ Receive audio file upload
├─ Parse recorded_at from request
├─ Store both recorded_at and uploaded_at in DynamoDB
└─ Create transcription job with created_at = recorded_at
```

## Example Timeline

```
15:30:00.000 - User starts recording (recorded_at)
15:30:20.500 - User stops, file encrypted
15:30:21.100 - File reaches backend server (uploaded_at)
15:30:21.100 - Transcription job created (created_at = recorded_at)
15:30:45.000 - Job processing completes
```

## DynamoDB Schema

**panzoto-audio-files:**
```
recorded_at: 1729350000 (unix timestamp)
recorded_at_iso: "2024-10-18T15:30:00.000000"
uploaded_at: 1729350021 (unix timestamp)
uploaded_at_iso: "2024-10-18T15:30:21.100000"
```

**panzoto-processing-jobs:**
```
created_at: "2024-10-18T15:30:00.000000" (matches audio file's recorded_at)
completed_at: "2024-10-18T15:30:45.000000"
```

## Code Changes

- **Android:** Added `recorded_at: String` to `AudioFileRecord` model
- **Android:** Capture `startTimeMillis` and convert to ISO 8601 in `MainActivity.kt`
- **Backend:** Added `recorded_at` parameter to `AudioFileCreate` model
- **Backend:** Parse and store `recorded_at` in `audio_service.py`
- **Backend:** Pass `audio_file.recorded_at` when creating transcription jobs

## Backward Compatibility

- Old audio files without `recorded_at`: Falls back to `uploaded_at`
- Old app versions: Send only `s3_key` and `file_size` (backend handles gracefully)
- No breaking changes to existing queries or APIs

## API Changes

**POST /api/audio-file - New Request:**
```json
{
  "s3_key": "audio_upload/uuid/filename.3gp",
  "file_size": 12345,
  "recorded_at": "2024-10-18T15:30:00.000000Z"
}
```

**Response includes:**
```json
{
  "recorded_at": "2024-10-18T15:30:00.000000",
  "uploaded_at": "2024-10-18T15:30:21.100000"
}
```

## Benefits

✅ Accurate job creation timestamps (recording start, not upload time)
✅ Audit trail showing upload delays and network issues
✅ Better performance analysis (total latency from recording to completion)
✅ Reconciliation with mobile app logs
