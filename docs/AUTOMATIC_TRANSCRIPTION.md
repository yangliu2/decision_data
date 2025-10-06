# Automatic Transcription - How It Works

**Status:** ✅ Enabled by Default (No Password Required)

---

## TL;DR

**You don't need to enter a password every time!** Just record audio and it's automatically transcribed in the background.

---

## How It Works

### 1. One-Time Setup (Login)
```
User → Opens app → Logs in with email/password
  ↓
Server returns:
  - JWT token (valid for 30 days)
  - User ID
  - Encryption key
  ↓
App stores in DataStore:
  - Token (for API calls)
  - Encryption key (for file encryption)
```

**Password is ONLY entered once during login.**

---

### 2. Recording Audio (No Password Needed)
```
User → Taps "Start Recording"
  ↓
App retrieves encryption key from DataStore (cached)
  ↓
Records audio → Encrypts with cached key → Uploads to S3
  ↓
Creates processing job → Server automatically processes
```

**No password or user interaction required!**

---

### 3. Automatic Background Processing
```
[Server Background Processor - Runs Every 30 Seconds]
  ↓
Scans for pending jobs
  ↓
Checks user preference: enable_transcription
  ↓
If enabled (DEFAULT): Process job automatically
  ↓
Decrypt → Convert format → Transcribe → Save
```

**User does nothing. Transcription happens automatically.**

---

## User Preference: `enable_transcription`

### Default Value
```python
enable_transcription: bool = True  # ✅ Enabled by default
```

### Where It's Checked
**Backend:** `audio_processor.py` line 184
```python
preferences = self.get_user_preferences(user_id)
if preferences and not preferences.get('enable_transcription', True):
    logger.info(f"User {user_id} has transcription disabled, skipping")
    self.mark_job_failed(job_id, "User has transcription disabled")
    return  # Skip transcription

# Otherwise, continue with automatic transcription
```

### Toggle in Android App
**Location:** Settings Screen → "Enable Audio Transcription"

**Options:**
- ✅ **ON** (Default) - Transcribe all recordings automatically
- ❌ **OFF** - Don't transcribe (jobs will be marked as failed)

---

## Current User Flow

### First Time User
```
Day 1:
  ↓
1. Register account (email + password)
2. Login (stores token + encryption key)
3. Record audio → Automatically transcribed ✅
4. View transcript in Processing screen

Day 2+:
  ↓
1. Open app (already logged in, token valid)
2. Record audio → Automatically transcribed ✅
3. No password needed!
```

### Token Expiration (After 30 Days)
```
After 30 days:
  ↓
App detects expired token
  ↓
User logs in again
  ↓
New token + encryption key stored
  ↓
Back to automatic transcription
```

---

## No Password Required Because...

### 1. JWT Token Authentication
- **Stored:** In Android DataStore (encrypted storage)
- **Valid for:** 30 days
- **Used for:** All API calls
- **No password needed:** Token is sent in Authorization header

### 2. Encryption Key Caching
- **Stored:** In Android DataStore
- **Fetched:** Once during login
- **Reused:** For all recordings
- **No password needed:** Key is already cached

### 3. Background Processing
- **Server-side:** Runs automatically
- **No user action:** Jobs processed in background
- **No password needed:** Server has encryption key in AWS Secrets Manager

---

## Settings Screen Configuration

### Current Implementation

**Android:** `SettingsScreen.kt`

**UI:**
```
┌─────────────────────────────────────┐
│  Settings                           │
├─────────────────────────────────────┤
│                                     │
│  Email Notifications                │
│  ├─ Enable Daily Summary    [ON ]  │
│  └─ Email: user@example.com        │
│                                     │
│  Transcription Settings             │
│  └─ Enable Audio Transcription      │
│     [✓] ON   [ ] OFF               │
│                                     │
│     When ON: All recordings are     │
│     automatically transcribed       │
│     (default)                       │
│                                     │
│  [Save Preferences]                 │
└─────────────────────────────────────┘
```

**Code:**
```kotlin
Row {
    Text("Enable Audio Transcription")
    Switch(
        checked = enableTranscription,
        onCheckedChange = { enableTranscription = it }
    )
}

if (enableTranscription) {
    Text(
        "✓ Automatic transcription enabled",
        color = Color.Green
    )
} else {
    Text(
        "⚠ Recordings will NOT be transcribed",
        color = Color.Orange
    )
}
```

---

## Default Preferences When User Registers

**Backend:** Create default preferences automatically

**File:** `api.py` - Registration endpoint

**Add this after user creation:**
```python
@app.post("/api/register")
async def register_user(user_data: UserCreate):
    # Create user account
    user_service = UserService()
    user = user_service.create_user(user_data)

    # ✅ CREATE DEFAULT PREFERENCES
    preferences_service = UserPreferencesService()
    default_prefs = UserPreferencesCreate(
        notification_email=user_data.email,
        enable_daily_summary=False,  # Off by default (user can enable)
        enable_transcription=True,   # ✅ ON by default (automatic)
        summary_time_utc="08:00"     # 8 AM UTC
    )
    preferences_service.create_preferences(user.user_id, default_prefs)

    return {"user_id": user.user_id, "token": token}
```

This ensures every new user starts with automatic transcription enabled.

---

## How to Disable Automatic Transcription

### Option 1: In Android App
1. Open app → Navigate to Settings
2. Toggle "Enable Audio Transcription" to **OFF**
3. Tap "Save Preferences"
4. Future recordings will NOT be transcribed

### Option 2: Via API
```bash
curl -X PUT http://206.189.185.129:8000/api/user/preferences \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_transcription": false
  }'
```

### Option 3: Directly in DynamoDB
1. Open AWS Console → DynamoDB → `panzoto-user-preferences`
2. Find user by `user_id`
3. Edit `enable_transcription` → Set to `false`

---

## Troubleshooting

### "Recordings aren't being transcribed"

**Check 1: Is transcription enabled?**
```
Settings → Enable Audio Transcription → Should be ON
```

**Check 2: Is background processor running?**
```bash
ssh root@206.189.185.129
ps aux | grep uvicorn
# Should see running process
```

**Check 3: Check job status**
```
Processing screen → View job → Check status
```

**Possible statuses:**
- `pending` - Waiting to be processed
- `processing` - Currently being transcribed
- `completed` - ✅ Transcription successful
- `failed` - ❌ Check error message

### "I keep getting asked for password"

**This shouldn't happen!** If it does:

**Cause 1:** Token expired (after 30 days)
- **Solution:** Normal - just log in again

**Cause 2:** App data cleared
- **Solution:** Log in again to restore token

**Cause 3:** Token storage broken
- **Solution:** Clear app data, reinstall app, log in

---

## Privacy & Security

### Your Password is NEVER Stored
- Password is hashed with Argon2 on server
- Only hash is stored in database
- Password cannot be recovered

### Encryption Key is NOT Your Password
- Encryption key is randomly generated (256-bit)
- Stored in AWS Secrets Manager
- Independent of your password

### What Happens When You Change Password?
- Encryption key remains the same
- Old recordings still accessible
- No re-encryption needed

---

## Cost Implications

### Automatic Transcription Costs
- **OpenAI Whisper:** $0.006 per minute
- **Example:** 100 x 30-second recordings = 50 minutes = $0.30/month

### If You Disable Automatic Transcription
- **Cost:** $0 (no transcription API calls)
- **Storage:** Files still stored in S3
- **Can enable later:** Turn ON anytime to resume

---

## Summary

✅ **Automatic transcription is ON by default**
✅ **No password required after login**
✅ **Token valid for 30 days**
✅ **Encryption key cached in app**
✅ **Background processor runs automatically**
✅ **User can toggle ON/OFF in Settings**

**You literally do nothing. Just record and it transcribes automatically.**

---

**Last Updated:** October 6, 2025
**Feature Status:** Production Ready
