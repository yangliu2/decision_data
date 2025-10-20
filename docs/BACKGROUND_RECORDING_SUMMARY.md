# Background Recording - Quick Summary

**Date:** October 20, 2025
**Status:** Design Complete
**Question Answered:** What happens when phone screen is off? How to enable background recording?

---

## Current Behavior ❌

When phone screen turns off or app goes to background:
- **Recording STOPS** immediately
- Activity is paused/destroyed by system
- MediaRecorder stops
- User must keep screen on to continue recording

---

## What You Want ✅

```
User starts recording
    ↓
Screen turns off (or navigates away)
    ↓
Recording CONTINUES in background
    ↓
Either:
  - User manually stops recording, OR
  - Scheduled stop time reached (e.g., 6 PM)
    ↓
Recording stops → File encrypts → Uploads in background
    ↓
User sees transcript in app (app can be closed)
```

---

## Solution: Three Components

### 1. Foreground Service (Keeps Recording Alive)

**What it is:** Background service that can't be killed by Android

**Why needed:**
- Recording continues even when app backgrounded or screen off
- Persistent notification shows user "Recording in background"
- System cannot kill it (unlike regular background service)

**How it works:**
```
RecordingService (Foreground)
├─ MediaRecorder instance (survives Activity destruction)
├─ Monitoring thread (independent of Activity lifecycle)
└─ Persistent notification (user sees at all times)
```

### 2. WorkManager (Resilient Uploads)

**What it is:** Android background job scheduler

**Why needed:**
- Upload continues even if app terminates
- Survives phone reboot
- Automatic retry if network fails

**How it works:**
```
When recording stops:
  → File encrypts
  → WorkManager schedules upload job
  → Upload happens in background
  → Survives app closure/reboot
```

### 3. Time-Based Stop Preference

**What it is:** New user preference setting

**Why needed:**
- User can set optional stop time (e.g., "Stop at 6 PM")
- If no stop time set, records until user manually stops

**How it works:**
```
User sets in Settings:
  ✓ Background Recording: ON
  ✓ Stop at (UTC): 18:00  (optional)
  ✓ Time Zone: America/New_York

Then recording auto-stops at 6 PM local time
```

---

## What Gets Added

### Backend Changes

**New preference fields:**
```python
enable_background_recording: bool      # Toggle on/off
recording_stop_time_utc: str           # "18:00" or null
recording_time_zone: str               # "UTC" or "America/New_York"
```

**New API endpoints:** (modified existing endpoints)
- `GET /api/user/preferences` - Returns new fields
- `POST/PUT /api/user/preferences` - Accepts new fields

### Android Changes

**New service:** `RecordingService.kt` (400 lines)
- Handles foreground service lifecycle
- Recording logic when app is backgrounded
- Time-based stop checking

**New worker:** `AudioUploadWorker.kt` (300 lines)
- Handles encryption and upload via WorkManager
- Automatic retry on network failure

**Updated UI:** SettingsScreen improvements (50 lines)
- Toggle for background recording
- Input for stop time and timezone

**Updated manifest:** New permissions
- `FOREGROUND_SERVICE` - Required for background recording
- `FOREGROUND_SERVICE_MICROPHONE` - Microphone access
- `WAKE_LOCK` - Keep CPU awake

---

## How It Works (Step by Step)

### User Journey

**Setup (One-time):**
1. Go to Settings
2. Enable "Background Recording"
3. Set "Stop at (UTC)" to "18:00" (optional)
4. Save

**Daily Use:**
1. Open app, tap "Start Recording"
2. Notification appears: "Recording in background"
3. Close app, turn off screen
4. Phone records continuously
5. At 6 PM (if set), recording stops automatically
6. File uploads in background
7. User sees transcript next time app opens

**Manual Stop:**
1. Open app notification → Tap "Stop Recording"
2. Or open app and manually stop
3. File uploads in background

---

## Technical Details

### Permissions Needed

```xml
<!-- New permissions to add -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
<uses-permission android:name="android.permission.WAKE_LOCK"/>

<!-- Already have -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>
```

### Notification Example

User sees at all times while recording in background:
```
┌─────────────────────────┐
│ Panzoto                 │
│ Recording Audio         │
│ Tap to open Panzoto    │
│ [Stop Recording]        │
└─────────────────────────┘
```

### Battery Impact

- Continuous microphone: ~10-15 mA
- Screen off: ~5-10 mA additional
- **Total:** ~15-30 mA
- **Duration on 5000 mAh battery:** 5-8 hours

---

## Implementation Effort

| Phase | Task | Time |
|-------|------|------|
| 1 | Backend preferences | 1 day |
| 2 | Foreground Service + WorkManager | 2-3 days |
| 3 | UI updates | 1 day |
| 4 | Testing | 2 days |
| **TOTAL** | | **6-7 days** |

---

## Key Features

✅ **Recording continues when screen off**
✅ **Recording continues when app backgrounded**
✅ **Automatic stop at scheduled time (optional)**
✅ **Manual stop anytime**
✅ **Uploads happen automatically in background**
✅ **Survives app closure and phone reboot**
✅ **Automatic retry on network failure**
✅ **Persistent notification (transparency)**

---

## Start Point

### Simplest Approach (Recommended)

1. **Week 1:** Implement backend preferences + Foreground Service
2. **Week 2:** Add WorkManager for uploads
3. **Week 3:** UI and testing

### Alternative: Gradual Rollout

- **Phase 1:** Backend only (no UI changes)
- **Phase 2:** Foreground Service basic version (manual stop only, no time-based)
- **Phase 3:** Time-based stop feature
- **Phase 4:** WorkManager resilience

---

## Full Documentation

See: `BACKGROUND_RECORDING_IMPLEMENTATION.md`

For complete technical specifications including:
- Code samples for RecordingService
- AudioUploadWorker implementation
- UI changes with full code
- Database migration script
- Testing procedures
- Troubleshooting guide

---

**Status:** Ready to implement
**Next Step:** Start with backend preferences migration

---

**Last Updated:** October 20, 2025
