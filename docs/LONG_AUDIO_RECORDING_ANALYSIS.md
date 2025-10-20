# Long Audio Recording Analysis - Current Implementation vs. Chunking Strategy

**Date:** October 20, 2025
**Status:** Analysis Complete
**Topic:** How the app currently handles long conversations and proposed chunking improvements

---

## Executive Summary

**Current Implementation:** The app records audio in **chunks** (60 seconds max) and automatically splits recordings when:
- Max duration (60 seconds) is reached
- Silence is detected (3 seconds of quiet)
- User manually stops

**Key Issue:** There is **NO gap prevention mechanism** between chunks. When one chunk ends and the next starts, there could be overlap or silence gaps, causing potential data loss or discontinuities.

---

## Current Recording Architecture

### 1. Recording Flow

**User starts recording:**
```
Start Recording
  ↓
Monitor audio amplitude every 200ms
  ↓
Check two stop conditions:
  ├─ Silence detected (3s of quiet) → Split recording
  └─ Max duration reached (60s) → Split recording
  ↓
Stop recording
  ↓
Encrypt file
  ↓
Upload to S3
  ↓
Create transcript job
  ↓
Auto-restart recording
```

### 2. Configuration (AppConfig.kt)

```kotlin
object Audio {
    const val SILENCE_THRESHOLD = 500          // Amplitude threshold for silence
    const val SILENCE_DURATION_MILLIS = 3000L  // 3 seconds of quiet triggers split
    const val MAX_CHUNK_DURATION_MILLIS = 60000L  // 60 seconds max per chunk
    const val MIN_FILE_SIZE_BYTES = 2000L      // Reject tiny files
    const val MIN_RECORDING_DURATION_MILLIS = 1000L  // At least 1 second
}

object UI {
    const val AUDIO_MONITORING_INTERVAL_MILLIS = 200L  // Check amplitude every 200ms
    const val UPLOAD_DELAY_MILLIS = 200L  // Wait before uploading
}
```

### 3. Recording Control in MainActivity.kt

**Key Variables:**
- `startTimeMillis` - When recording started
- `silenceStartMillis` - When silence began
- `monitoringHandler` - Periodic amplitude checks
- `hasVoiceDetected` - Flag for voice presence

**Split Logic (Lines 152-192):**

```kotlin
private fun forceSplit() {
    // Stop current recording and auto-restart
    stopRecording(userSession!!, authViewModel, autoRestart = true)
}

private val monitoringRunnable = object : Runnable {
    override fun run() {
        val currentTime = System.currentTimeMillis()
        val elapsedTime = currentTime - startTimeMillis
        val amplitude = mediaRecorder?.maxAmplitude ?: 0

        // Check for silence
        if (amplitude < silenceThreshold) {
            if (silenceStartMillis == null) {
                silenceStartMillis = currentTime
            } else if (currentTime - silenceStartMillis!! >= silenceDurationMillis) {
                Log.d("Split", "Silence detected, splitting recording.")
                forceSplit()
                return
            }
        } else {
            hasVoiceDetected = true  // ✅ Real sound detected
            silenceStartMillis = null
        }

        // Check for max duration
        if (elapsedTime >= maxChunkDurationMillis) {
            Log.d("Split", "Max duration reached, splitting recording.")
            forceSplit()
            return
        }

        // Re-check after 200ms
        monitoringHandler?.postDelayed(this, AppConfig.UI.AUDIO_MONITORING_INTERVAL_MILLIS)
    }
}
```

**Stop & Auto-Restart (Lines 228-321):**

```kotlin
private fun stopRecording(userSession: UserSession, authViewModel: AuthViewModel,
                          autoRestart: Boolean = false) {
    // Stop current recording
    // Validate file (minimum size, voice detection)
    // Encrypt
    // Upload to S3
    // Create transcript job

    if (autoRestart) {
        startRecording()  // ← Start new chunk immediately
    }
}
```

---

## Long Audio Recording Challenge: The Gap Problem

### Scenario: Recording a 10-minute conversation

```
Minute 0-1:   Chunk 1 (60 seconds)     →  Split triggered
             (small gap)
Minute 1-2:   Chunk 2 (60 seconds)     →  Split triggered
             (small gap)
Minute 2-3:   Chunk 3 (60 seconds)     →  Split triggered
             ...
Minute 9-10:  Chunk 10 (60 seconds)    →  User stops
```

### The Gap Problem

**When** `stopRecording()` is called with `autoRestart = true`:

1. **Record stop** → MediaRecorder stops (typically takes 1-5ms)
2. **File write** → OS flushes to disk (1-10ms)
3. **Encrypt** → AES-256-GCM encryption (5-50ms on mobile)
4. **Upload init** → Network request starts (50-200ms)
5. **New record start** → MediaRecorder starts fresh

**Total gap:** ~60-250ms ✅ **Usually acceptable**

**But there's a risk:** If the encryption/upload takes longer, audio IS BEING LOST because the new recording hasn't started yet.

### Actual Code Flow Issues

**Issue 1: Race Condition**

```kotlin
// Line 318-320
if (autoRestart) {
    startRecording()  // Starts IMMEDIATELY after file validation
}
```

If encryption hasn't finished yet, the gap expands. The new `startRecording()` happens in the main thread, but encryption happens in a coroutine (`Dispatchers.IO`).

**Issue 2: Handler Delay**

```kotlin
// Line 312-316
Handler(Looper.getMainLooper()).postDelayed({
    requestPresignedUrlAndUpload(encryptedFile, presignedKey)
}, AppConfig.UI.UPLOAD_DELAY_MILLIS)  // ← Additional 200ms delay before upload starts
```

The 200ms upload delay is added AFTER file validation but BEFORE new recording starts. This isn't the right timing.

---

## Current Limitations

| Aspect | Current | Issue |
|--------|---------|-------|
| **Max chunk** | 60 seconds | Works for short conversations, but 10-minute meeting = 10 chunks |
| **Silence detection** | 3 seconds | May split in middle of speaker pauses |
| **Gap handling** | None | No overlap/gap prevention |
| **Concatenation** | Manual (user) | Transcripts are separate, need manual stitching |
| **Timestamp tracking** | Per chunk | When did speaker pause? Which chunk? |

---

## Proposed Improvements for Long Conversations

### Option 1: Overlap-Based Chunking (Recommended)

**Idea:** Each new chunk starts 500ms BEFORE the previous chunk ends to capture transition points.

```
Chunk 1: 0s ━━━━━━━━━━ 60s
               ↓ overlap window (last 500ms)
Chunk 2:           59.5s ━━━━━━━━━━ 119.5s
                        ↓ overlap window (last 500ms)
Chunk 3:                119s ━━━━━━━━━━ 179s
```

**Advantages:**
- ✅ No audio loss between chunks
- ✅ Can detect speaker boundaries
- ✅ Easy to remove duplicates during processing
- ✅ Handles network delays gracefully

**Implementation:**
```kotlin
// Track overlap buffer
private var overlapBuffer: ByteArray? = null
const val OVERLAP_DURATION_MS = 500L

// When splitting:
// 1. Save last 500ms of audio to overlapBuffer
// 2. Stop current recording
// 3. Start new recording
// 4. Feed overlapBuffer to new recording (or backend)
```

### Option 2: Continuous Recording with Server-Side Chunking

**Idea:** Record continuously on device, send raw stream to backend, let server split intelligently.

**Advantages:**
- ✅ No gaps at all
- ✅ Server can chunk by sentence/pause
- ✅ Simpler app logic
- ✅ Better transcription context

**Challenges:**
- Requires streaming upload (more complex)
- Network must be reliable
- Battery drain (constant upload)

### Option 3: Longer Chunks with Smart Split

**Idea:** Increase chunk duration to 5-10 minutes, but only split on silence.

**Current:** `MAX_CHUNK_DURATION_MILLIS = 60000L` (60 seconds)
**Proposed:** `MAX_CHUNK_DURATION_MILLIS = 300000L` (5 minutes) OR `600000L` (10 minutes)

```kotlin
// Modified logic
if (elapsedTime >= maxChunkDurationMillis) {
    // Wait for next silence before splitting
    if (amplitudeIsSilent && silenceDurationExceeds(500ms)) {
        forceSplit()  // Split at natural pause
    }
}
```

**Advantages:**
- ✅ Fewer chunks = fewer gaps
- ✅ More context for transcription
- ✅ Less overhead

**Trade-offs:**
- ⚠️ Longer wait times (can't stop until 5min + silence)
- ⚠️ Larger file sizes
- ⚠️ More memory usage

---

## Recommendation: Hybrid Approach

### Phase 1: Immediate (Quick Win)

**Fix the timing issue:**

```kotlin
// Current problematic flow:
private fun continueUploadProcess(encryptedFile: File, userSession: UserSession, autoRestart: Boolean) {
    Handler(Looper.getMainLooper()).postDelayed({
        requestPresignedUrlAndUpload(encryptedFile, presignedKey)
    }, AppConfig.UI.UPLOAD_DELAY_MILLIS)  // ← Gap happens here

    if (autoRestart) {
        startRecording()  // ← Starts during upload, acceptable
    }
}

// Better flow:
private fun continueUploadProcess(encryptedFile: File, userSession: UserSession, autoRestart: Boolean) {
    if (autoRestart) {
        startRecording()  // ← Start new chunk FIRST
    }

    Handler(Looper.getMainLooper()).postDelayed({
        requestPresignedUrlAndUpload(encryptedFile, presignedKey)
    }, AppConfig.UI.UPLOAD_DELAY_MILLIS)  // ← Upload happens while new chunk records
}
```

**Impact:** Reduces effective gap from ~250ms to ~50ms

### Phase 2: Medium-term (Overlap Chunking)

Implement Option 1 with 500ms overlap buffer:
- Capture transition points
- Remove duplicates server-side
- Better transcription quality

### Phase 3: Long-term (Streaming)

Implement continuous streaming if needed for very long conversations (1+ hours).

---

## Testing Scenarios

### Test 1: 10-minute conversation (current chunking)

```
Expected: 10 chunks of ~60 seconds each
Check:
  - No audio loss between chunks
  - All 10 chunks upload successfully
  - Total duration matches actual recording
  - Timestamps are sequential
```

### Test 2: Rapid speech (no silence)

```
Expected: Split on 60-second timer
Check:
  - Chunk ends mid-sentence
  - Next chunk continues seamlessly
  - No overlap/gap
```

### Test 3: Long silence (conversation pause)

```
Expected: Split on 3-second silence
Check:
  - Stops during pause
  - Captures speaker boundaries
  - Reduced chunk sizes
```

### Test 4: Network delay (simulated)

```
Expected: Gap prevention
Check:
  - Even if upload stalls, new chunk captures audio
  - No loss during network issues
```

---

## Backend Transcript Concatenation

Currently, each chunk creates a separate transcript. For long conversations, we need:

### Transcript Stitching Logic (Backend)

```python
def get_full_transcript(user_id: str, recording_session_id: str):
    """
    Get all transcript chunks for a recording session and stitch them together.

    Handles:
    - Removing overlap duplicates
    - Preserving timestamps
    - Detecting speaker changes
    """
    chunks = get_transcript_chunks(user_id, recording_session_id)

    # Remove overlaps (last 500ms of chunk N vs first 500ms of chunk N+1)
    stitched = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            stitched.append(chunk)
        else:
            # Remove duplicate overlap region
            overlap_chars = estimate_chars_for_duration(500)
            deduplicated = chunk.transcript[overlap_chars:]
            stitched.append(deduplicated)

    return {
        'full_transcript': '\n'.join(stitched),
        'chunks': len(chunks),
        'total_duration': sum(c.duration for c in chunks),
        'recording_session_id': recording_session_id
    }
```

---

## Current State: What Works

✅ **Automatic chunking** - Records in ~60 second chunks
✅ **Silence detection** - Stops on pauses
✅ **Auto-restart** - Immediately starts new chunk
✅ **Voice detection** - Rejects silent files
✅ **Encryption** - Each chunk encrypted securely
✅ **Upload** - All chunks upload successfully
✅ **Transcript creation** - Each chunk transcribed

---

## Current State: What Needs Work

⚠️ **Gap prevention** - Small gaps exist between chunks
⚠️ **Transcript joining** - No automatic stitching
⚠️ **Session tracking** - Chunks not linked to recording session
⚠️ **Timestamp accuracy** - Chunk boundaries not marked
⚠️ **Long recordings** - Many small chunks, hard to manage

---

## Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| **HIGH** | Fix timing issue (start new chunk before upload) | 1 hour | ✅ Reduce gaps |
| **HIGH** | Add recording session tracking | 2 hours | ✅ Link chunks together |
| **MEDIUM** | Implement overlap-based chunking | 4 hours | ✅ Eliminate gaps |
| **MEDIUM** | Add transcript concatenation backend | 2 hours | ✅ Full conversation text |
| **LOW** | Longer chunk duration (5-10min) | 1 hour | ✅ Fewer chunks |
| **LOW** | Streaming upload | 8 hours | ✅ No gaps ever |

---

## Conclusion

**Current app CAN record long conversations** through automatic chunking (60 seconds per chunk). For a 10-minute conversation, you get 10 chunks that are automatically recorded, encrypted, and uploaded.

**Main limitation:** Small gaps between chunks (50-250ms) due to recording stop/restart timing.

**Solution:** Small code changes can reduce gaps to negligible levels, and server-side transcript stitching can reassemble chunks into complete conversations.

**Recommendation:** Implement quick fix immediately (reorder operations), then plan overlap-based chunking for Phase 2.

---

**Last Updated:** October 20, 2025
