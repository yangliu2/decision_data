# Background Recording Implementation Guide

**Date:** October 20, 2025
**Status:** Design Complete - Ready for Implementation
**Topic:** Screen-off recording with time-based stop preferences

---

## Executive Summary

**Current Issue:** Recording stops when screen turns off (or when user navigates away from app)

**Desired Behavior:**
- App records in background (screen can be off)
- Recording continues until:
  - User manually stops it, OR
  - Scheduled stop time reached (user preference)
- Uploads happen in background without user intervention
- User can close app, phone can lock - recording continues

**Solution:** Use Android Foreground Service + WorkManager

---

## Current Problem Analysis

### How Screen Off Affects Recording

When screen turns off with current implementation:

```
Current Architecture:
├─ MainActivity (UI Activity)
│  ├─ MediaRecorder instance
│  ├─ Monitoring Handler (main thread)
│  └─ Lifecycle tied to Activity lifecycle
```

**Issues:**

1. **Activity Destroyed on Screen Off**
   - MainActivity gets paused/stopped when screen off
   - Monitoring handler loses Main thread reference
   - MediaRecorder may stop (system resource optimization)

2. **App Backgrounded**
   - If user navigates away, Activity destroyed
   - Recording stops immediately
   - Monitoring threads can be killed by system

3. **System Power Optimization**
   - Android 6+ (Doze mode) kills background tasks
   - MediaRecorder requires active components
   - Monitoring threads suspended

**Current State:**
```
User records → Screen turns off → Activity paused → Recording STOPS ❌
User records → Navigates away → Activity destroyed → Recording STOPS ❌
User records → Screen locked → Doze mode → Recording STOPS ❌
```

### What You Need

```
User records → Screen turns off → Activity paused → Recording CONTINUES ✅
User records → Navigates away → Activity destroyed → Recording CONTINUES ✅
User records → Screen locked → Doze mode → Recording CONTINUES ✅
User stops manually → Recording stops + Upload begins ✅
Stop time reached → Recording stops + Upload begins ✅
```

---

## Solution Architecture

### Components Needed

#### 1. Foreground Service (Keeps App Alive)

**Purpose:** Keep recording running even when app backgrounded

```
Foreground Service
├─ Persistent notification (user sees "Recording in background")
├─ MediaRecorder instance
├─ Monitoring thread (independent of Activity lifecycle)
└─ Upload worker thread
```

**Why Foreground Service?**
- Visible to user (persistent notification)
- Cannot be killed by system
- Survives Activity destruction
- Works even with Doze mode

#### 2. WorkManager (Resilient Background Jobs)

**Purpose:** Handle uploads that survive app termination

```
WorkManager
├─ Audio encryption worker
├─ S3 upload worker
├─ Scheduled job cleanup
└─ Network retry logic (built-in)
```

**Why WorkManager?**
- Survives app crash/termination
- Automatic retry with backoff
- Respects Doze mode
- Schedules around network availability

#### 3. Preferences (Stop Time)

**New Preference Fields:**
```kotlin
data class UserPreferences {
    // Existing fields...
    val enable_daily_summary: Boolean
    val summary_time_utc: String

    // NEW FIELDS:
    val enable_background_recording: Boolean  // Toggle feature on/off
    val recording_stop_time_utc: String?      // Optional: "18:00" to stop at 6 PM
    val recording_time_zone: String?          // Optional: "America/New_York"
}
```

---

## Implementation Plan

### Phase 1: Preferences Backend (1 day)

#### 1.1 Update DynamoDB Schema

**Table: panzoto-user-preferences**

Add three fields:
```python
{
    'user_id': str,  # PK
    'notification_email': str,
    'enable_daily_summary': bool,
    'summary_time_utc': str,

    # NEW FIELDS:
    'enable_background_recording': bool,  # Default: False
    'recording_stop_time_utc': str,      # Format: "HH:MM" or null
    'recording_time_zone': str,          # Format: "UTC" or "America/New_York"

    'created_at': str,
    'updated_at': str
}
```

#### 1.2 Migration Script

Create migration to add new fields to existing preferences:

```python
# decision_data/scripts/migrate_background_recording_prefs.py

def migrate():
    """Add background recording preferences to all users"""
    table = dynamodb.Table('panzoto-user-preferences')

    response = table.scan()
    for item in response['Items']:
        table.update_item(
            Key={'user_id': item['user_id']},
            UpdateExpression='SET enable_background_recording = :ebr, ' +
                           'recording_stop_time_utc = :rst, ' +
                           'recording_time_zone = :rtz',
            ExpressionAttributeValues={
                ':ebr': False,  # Default OFF
                ':rst': None,   # No stop time
                ':rtz': 'UTC'   # Default UTC
            }
        )
```

#### 1.3 Update Backend Models

```python
# decision_data/data_structure/models.py

class UserPreferencesCreate(BaseModel):
    notification_email: str
    enable_daily_summary: bool = True
    enable_transcription: bool = True
    summary_time_utc: str = "09:00"

    # NEW FIELDS:
    enable_background_recording: bool = False
    recording_stop_time_utc: Optional[str] = None  # "18:00"
    recording_time_zone: str = "UTC"
```

#### 1.4 Update API Endpoints

Modify existing endpoints to handle new fields:
- `POST /api/user/preferences` - Create with new fields
- `PUT /api/user/preferences` - Update with new fields
- `GET /api/user/preferences` - Return new fields

**Effort:** ~3 hours

---

### Phase 2: Android Foreground Service (2-3 days)

#### 2.1 Create RecordingService

**File: RecordingService.kt** (~400 lines)

```kotlin
package com.example.panzoto.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.media.MediaRecorder
import android.os.Binder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.panzoto.MainActivity
import com.example.panzoto.R
import com.example.panzoto.config.AppConfig
import java.io.File
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

class RecordingService : Service() {

    private var mediaRecorder: MediaRecorder? = null
    private var outputFilePath: String = ""
    private var startTimeMillis: Long = 0
    private var silenceStartMillis: Long? = null
    private var monitoringHandler: Handler? = null
    private var hasVoiceDetected = false

    // User preferences
    private var stopTimeUtc: String? = null  // "18:00"
    private var timeZone: String = "UTC"
    private var backgroundRecordingEnabled = false

    // Notification ID
    companion object {
        const val NOTIFICATION_ID = 1
        const val CHANNEL_ID = "audio_recording"
    }

    // Binder for communication
    private val binder = RecordingBinder()

    inner class RecordingBinder : Binder() {
        fun getService(): RecordingService = this@RecordingService
    }

    override fun onCreate() {
        super.onCreate()
        Log.d("RecordingService", "Service created")
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d("RecordingService", "Service started")

        // Get preferences from intent
        stopTimeUtc = intent?.getStringExtra("stop_time_utc")
        timeZone = intent?.getStringExtra("time_zone") ?: "UTC"
        backgroundRecordingEnabled = intent?.getBooleanExtra("background_recording_enabled", false) ?: false

        // Show persistent notification
        val notification = createNotification()
        startForeground(NOTIFICATION_ID, notification)

        // Start recording if enabled
        if (backgroundRecordingEnabled) {
            startRecording()
        }

        return START_STICKY  // Restart if killed by system
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Audio Recording",
                NotificationManager.IMPORTANCE_LOW
            )
            channel.description = "Recording audio in background"

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager?.createNotificationChannel(channel)
        }
    }

    private fun createNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Recording Audio")
            .setContentText("Tap to open Panzoto")
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentIntent(
                android.app.PendingIntent.getActivity(
                    this,
                    0,
                    Intent(this, MainActivity::class.java),
                    android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE
                )
            )
            .addAction(
                R.drawable.ic_launcher_foreground,
                "Stop Recording",
                android.app.PendingIntent.getService(
                    this,
                    0,
                    Intent(this, RecordingService::class.java).apply {
                        action = "STOP_RECORDING"
                    },
                    android.app.PendingIntent.FLAG_UPDATE_CURRENT or android.app.PendingIntent.FLAG_IMMUTABLE
                )
            )
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .build()
    }

    private fun startRecording() {
        // Same as MainActivity.startRecording()
        val fileName = "audio_bg_${System.currentTimeMillis()}.3gp"
        outputFilePath = "${externalCacheDir?.absolutePath}/$fileName"

        mediaRecorder = MediaRecorder().apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP)
            setOutputFile(outputFilePath)
            setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB)
            prepare()
            start()
        }

        startTimeMillis = System.currentTimeMillis()
        startMonitoring()
        Log.d("RecordingService", "Recording started")
    }

    private fun startMonitoring() {
        hasVoiceDetected = false
        silenceStartMillis = null
        monitoringHandler = Handler(android.os.Looper.getMainLooper())
        monitoringHandler?.post(monitoringRunnable)
    }

    private val monitoringRunnable = object : Runnable {
        override fun run() {
            val currentTime = System.currentTimeMillis()
            val elapsedTime = currentTime - startTimeMillis
            val amplitude = mediaRecorder?.maxAmplitude ?: 0

            // Check for silence
            if (amplitude < AppConfig.Audio.SILENCE_THRESHOLD) {
                if (silenceStartMillis == null) {
                    silenceStartMillis = currentTime
                } else if (currentTime - silenceStartMillis!! >= AppConfig.Audio.SILENCE_DURATION_MILLIS) {
                    Log.d("RecordingService", "Silence detected, splitting recording")
                    forceSplit()
                    return
                }
            } else {
                hasVoiceDetected = true
                silenceStartMillis = null
            }

            // Check for max duration
            if (elapsedTime >= AppConfig.Audio.MAX_CHUNK_DURATION_MILLIS) {
                Log.d("RecordingService", "Max duration reached, splitting recording")
                forceSplit()
                return
            }

            // Check for stop time
            if (shouldStopByTime()) {
                Log.d("RecordingService", "Stop time reached, stopping recording")
                stopRecording()
                return
            }

            monitoringHandler?.postDelayed(this, AppConfig.UI.AUDIO_MONITORING_INTERVAL_MILLIS)
        }
    }

    private fun shouldStopByTime(): Boolean {
        if (stopTimeUtc == null) return false

        try {
            val currentTime = ZonedDateTime.now(ZoneId.of(timeZone))
            val currentTimeStr = String.format("%02d:%02d", currentTime.hour, currentTime.minute)

            // If current time >= stop time, stop recording
            return currentTimeStr >= stopTimeUtc!!
        } catch (e: Exception) {
            Log.e("RecordingService", "Error checking stop time: ${e.message}")
            return false
        }
    }

    private fun forceSplit() {
        stopRecording()
        // Continue recording (auto-restart)
        Handler(android.os.Looper.getMainLooper()).postDelayed({
            startRecording()
        }, 500)
    }

    private fun stopRecording() {
        monitoringHandler?.removeCallbacks(monitoringRunnable)
        monitoringHandler = null

        val duration = System.currentTimeMillis() - startTimeMillis
        if (duration < AppConfig.Audio.MIN_RECORDING_DURATION_MILLIS) {
            Log.w("RecordingService", "Recording too short, skipping")
            startRecording()  // Auto-restart
            return
        }

        try {
            mediaRecorder?.apply {
                stop()
                release()
            }
        } catch (e: Exception) {
            Log.e("RecordingService", "Stop failed: ${e.message}")
            return
        }

        mediaRecorder = null

        val inputFile = File(outputFilePath)
        if (!inputFile.exists() || inputFile.length() < AppConfig.Audio.MIN_FILE_SIZE_BYTES) {
            Log.d("RecordingService", "File too small, skipping")
            return
        }

        if (!hasVoiceDetected) {
            Log.d("RecordingService", "No voice detected, skipping")
            inputFile.delete()
            return
        }

        // Schedule upload via WorkManager
        scheduleUpload(inputFile)
    }

    private fun scheduleUpload(audioFile: File) {
        // Use WorkManager to handle upload (resilient, survives app termination)
        val uploadRequest = androidx.work.OneTimeWorkRequestBuilder<AudioUploadWorker>()
            .setInputData(
                androidx.work.workDataOf(
                    "file_path" to audioFile.absolutePath
                )
            )
            .build()

        androidx.work.WorkManager.getInstance(this)
            .enqueueUniqueWork(
                "audio_upload_${System.currentTimeMillis()}",
                androidx.work.ExistingWorkPolicy.KEEP,
                uploadRequest
            )

        Log.d("RecordingService", "Upload scheduled via WorkManager")
    }

    override fun onDestroy() {
        Log.d("RecordingService", "Service destroyed")
        monitoringHandler?.removeCallbacks(monitoringRunnable)
        mediaRecorder?.release()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }
}
```

#### 2.2 Create AudioUploadWorker

**File: AudioUploadWorker.kt** (~300 lines)

```kotlin
package com.example.panzoto.service

import android.content.Context
import android.util.Log
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.example.panzoto.data.UserSession
import com.example.panzoto.viewmodel.AuthViewModel
import kotlinx.coroutines.runBlocking
import java.io.File

class AudioUploadWorker(context: Context, params: WorkerParameters) : Worker(context, params) {

    override fun doWork(): Result {
        return try {
            val filePath = inputData.getString("file_path") ?: return Result.failure()
            val audioFile = File(filePath)

            if (!audioFile.exists()) {
                Log.w("AudioUploadWorker", "File not found: $filePath")
                return Result.failure()
            }

            // Get authentication context
            val authViewModel = AuthViewModel(applicationContext)

            runBlocking {
                // Get user session
                val userSession = authViewModel.userSession.value
                if (userSession == null) {
                    Log.e("AudioUploadWorker", "No user session available")
                    return@runBlocking Result.retry()
                }

                // Perform encryption and upload
                // (Same logic as MainActivity.stopRecording)
                val encryptionKey = authViewModel.getEncryptionKey()
                if (encryptionKey == null) {
                    Log.e("AudioUploadWorker", "No encryption key available")
                    return@runBlocking Result.retry()
                }

                // Encrypt, upload, create audio file record...
                // (Reuse existing logic from MainActivity)
            }

            Result.success()
        } catch (e: Exception) {
            Log.e("AudioUploadWorker", "Upload failed: ${e.message}", e)
            Result.retry()  // Will retry with exponential backoff
        }
    }
}
```

#### 2.3 Update MainActivity

Modify MainActivity to start/stop service:

```kotlin
// In MainActivity.kt

private fun startBackgroundRecording() {
    val intent = Intent(this, RecordingService::class.java).apply {
        action = "START_RECORDING"
        putExtra("stop_time_utc", userPreferences?.recording_stop_time_utc)
        putExtra("time_zone", userPreferences?.recording_time_zone ?: "UTC")
        putExtra("background_recording_enabled", userPreferences?.enable_background_recording ?: false)
    }

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        startForegroundService(intent)
    } else {
        startService(intent)
    }
}

private fun stopBackgroundRecording() {
    val intent = Intent(this, RecordingService::class.java)
    stopService(intent)
}
```

#### 2.4 Update AndroidManifest.xml

Add service and permissions:

```xml
<manifest>
    <!-- Existing permissions -->
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.INTERNET"/>

    <!-- NEW PERMISSIONS FOR BACKGROUND RECORDING -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
    <uses-permission android:name="android.permission.WAKE_LOCK"/>

    <application>
        <!-- Existing activities -->
        <activity android:name=".MainActivity" />

        <!-- NEW SERVICE -->
        <service
            android:name=".service.RecordingService"
            android:foregroundServiceType="microphone"
            android:exported="false"/>
    </application>
</manifest>
```

**Effort:** 2-3 days

---

### Phase 3: Android UI Updates (1 day)

#### 3.1 Update SettingsScreen

Add background recording preferences:

```kotlin
// In SettingsScreen.kt

// Add state variables
var enableBackgroundRecording by remember { mutableStateOf(false) }
var recordingStopTimeUtc by remember { mutableStateOf("") }
var recordingTimeZone by remember { mutableStateOf("UTC") }

// Add to preferences card
Card {
    Column(modifier = Modifier.padding(16.dp)) {
        Text("Background Recording")

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Enable Background Recording")
            Switch(
                checked = enableBackgroundRecording,
                onCheckedChange = { enableBackgroundRecording = it }
            )
        }

        if (enableBackgroundRecording) {
            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = recordingStopTimeUtc,
                onValueChange = { recordingStopTimeUtc = it },
                label = { Text("Stop Recording At (UTC)") },
                placeholder = { Text("HH:MM (e.g., 18:00) - leave blank for manual stop") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            OutlinedTextField(
                value = recordingTimeZone,
                onValueChange = { recordingTimeZone = it },
                label = { Text("Time Zone") },
                placeholder = { Text("UTC or America/New_York") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
        }
    }
}
```

#### 3.2 Update MainAppScreen

Show background recording status:

```kotlin
// In MainAppScreen composable

if (enableBackgroundRecording) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Text(
            text = "Background Recording: ACTIVE\nTap 'Start Recording' to stop",
            modifier = Modifier.padding(16.dp)
        )
    }
}
```

**Effort:** 1 day

---

### Phase 4: Testing (2 days)

#### Test Scenarios

1. **Screen Off Recording**
   - Start recording → Turn screen off → Recording continues ✓
   - Stop recording manually → Upload happens ✓

2. **App Backgrounding**
   - Start recording → Open another app → Recording continues ✓
   - Return to app → Can stop recording ✓

3. **Stop Time Trigger**
   - Set stop time to now + 1 minute
   - Start recording → Wait 1 minute → Recording stops automatically ✓

4. **Device Reboot**
   - Start recording → Reboot phone → Recording resumes ✓

5. **Upload After Stop**
   - Stop recording → File encrypts and uploads via WorkManager ✓
   - Verify file appears in Processing list ✓

6. **Network Issues**
   - Start recording → Kill network → Stop recording
   - Network restored → Upload retries automatically ✓

**Effort:** 2 days

---

## Database Schema Changes

### DynamoDB Migration

```python
# Add to panzoto-user-preferences table

{
    'user_id': {
        'S': 'uuid'
    },
    'enable_background_recording': {
        'BOOL': False  # Default OFF for backward compatibility
    },
    'recording_stop_time_utc': {
        'NULL': True  # Can be null if manual stop only
        # or 'S': '18:00' if set
    },
    'recording_time_zone': {
        'S': 'UTC'  # Default timezone
    }
}
```

### Backward Compatibility

- New fields are optional (default to OFF)
- Existing users unaffected until they enable feature
- No breaking changes to API

---

## Android Permissions Explained

### Required Permissions

```xml
<!-- Already required -->
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>

<!-- NEW for background recording -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<!-- Foreground service permission -->

<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE"/>
<!-- Microphone access in foreground service (Android 14+) -->

<uses-permission android:name="android.permission.WAKE_LOCK"/>
<!-- Keep CPU awake during uploads -->
```

### User Prompts

When user enables background recording:
1. Existing "Allow access to microphone?" → Already granted
2. NEW: System may ask about notification permission (Android 13+)

---

## Implementation Effort Summary

| Phase | Task | Effort | Complexity |
|-------|------|--------|------------|
| 1 | Backend Preferences | 1 day | Low |
| 2 | Foreground Service | 2-3 days | High |
| 3 | UI Updates | 1 day | Low |
| 4 | Testing | 2 days | Medium |
| **TOTAL** | | **6-7 days** | **Medium** |

---

## Timeline

**Week 1:**
- Day 1: Backend preferences (migration, models, API)
- Days 2-4: Foreground Service implementation
- Day 5: UI updates

**Week 2:**
- Days 1-2: Testing and bug fixes
- Day 3: Documentation and deployment

---

## Key Design Decisions

### 1. Foreground Service (Not Background Service)

**Why?**
- Foreground services cannot be killed by system
- Background services can be killed at any time (defeats purpose)
- User sees persistent notification (transparency)
- Android 12+ requires foreground service anyway

### 2. WorkManager for Uploads

**Why?**
- Survives app termination
- Automatic retry with exponential backoff
- Respects Doze mode and network constraints
- Built-in scheduling

### 3. Optional Stop Time

**Why?**
- Some users may want manual stop only
- Some users may want automatic stop (e.g., 6 PM)
- Flexible to different use cases

### 4. Time Zone Support

**Why?**
- Stop time should be in user's local time, not UTC
- 9 AM Pacific ≠ 9 AM Eastern
- Store as string for simplicity

---

## Battery & Privacy Considerations

### Battery Impact

- **Microphone sampling**: ~10-15 mA (always running)
- **Screen off**: ~5-10 mA (reduced processor load)
- **WiFi connected**: +5 mA
- **Total**: ~15-30 mA continuous
- **On typical 5000 mAh battery**: 5-8 hours of continuous recording

**User Warning:** Add battery warning in settings if background recording enabled

### Privacy Impact

- Persistent notification shows user app is recording
- Clear permission in settings menu
- Can be disabled anytime
- No audio data stored locally (encrypted upload only)

---

## Future Enhancements

### Phase 2 (Later)

- [ ] Battery indicator in notification
- [ ] Pause/resume from notification button
- [ ] Recording time display
- [ ] Pause when low battery (<15%)
- [ ] Pause on Wi-Fi disconnection (optional)

### Phase 3 (Much Later)

- [ ] Real-time upload progress
- [ ] Pause on specific apps (e.g., phone call)
- [ ] Scheduled recording windows
- [ ] Recording duration analytics

---

## Troubleshooting Guide

### "Recording stops when app backgrounded"

**Check:**
1. Is background recording enabled in settings?
2. Is Foreground Service notification showing?
3. Check logcat: `adb logcat | grep RecordingService`

### "Uploads not happening"

**Check:**
1. Is there network connection?
2. Check WorkManager: Android Studio Device Explorer → Data → WorkManager
3. Check permissions: Settings → Panzoto → Permissions

### "Stop time not working"

**Check:**
1. Is time in correct format? (HH:MM in 24-hour)
2. Is time zone correct? (UTC vs America/New_York)
3. Check server time matches phone time

---

## Conclusion

Background recording with time-based stopping is feasible using Android Foreground Services + WorkManager.

**Estimated effort:** 6-7 days
**Complexity:** Medium (threading, service lifecycle, WorkManager)
**User benefit:** Significant (hands-off recording, works with screen off)

Ready to implement? Start with Phase 1 (backend preferences).

---

**Last Updated:** October 20, 2025
