# Timezone Comparison Fix - October 20, 2025

**Status:** ✅ FIXED AND DEPLOYED
**Commits:** ff7aeb4, 59ccec8
**Issue:** Pending jobs stuck in processing queue, background processor unable to identify eligible jobs

---

## Problem Summary

Background jobs were stuck in pending status and the processor was unable to advance them. The error was subtle but critical:

```
[INFO] Checked for jobs, found 0 eligible jobs
```

Despite there being pending jobs in DynamoDB, the processor reported finding zero eligible jobs for processing.

---

## Root Cause Analysis

### The Bug

In `decision_data/backend/services/audio_processor.py`, the `is_job_eligible()` method was comparing two datetime objects with mismatched timezone information:

```python
now = datetime.utcnow()  # timezone-naive datetime
created_at = datetime.fromisoformat(job['created_at'])  # timezone-aware datetime
age_hours = (now - created_at).total_seconds() / 3600  # ERROR!
```

**Error:**
```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

### Why This Happened

1. **Backend timestamp change:** Earlier fix added 'Z' suffix to ISO datetime strings from DynamoDB (for Java compatibility in Android app)
2. **Timezone-aware DynamoDB data:** Timestamps now come back as timezone-aware (e.g., `"2025-10-20T00:22:18.597000+00:00"`)
3. **Timezone-naive comparison:** The `is_job_eligible()` method used `datetime.utcnow()` which returns a timezone-naive datetime
4. **Incompatible comparison:** Python refuses to subtract datetimes with different timezone awareness

This caused the entire `get_eligible_pending_jobs()` method to fail silently, returning an empty list.

---

## The Solution

### Timezone Normalization

Added explicit timezone handling to ensure both datetimes are timezone-aware before comparison:

```python
from datetime import datetime, timedelta, timezone

# In is_job_eligible() method:
now = datetime.utcnow()

# Parse created_at and handle both timezone-aware and naive datetimes
created_at_str = job['created_at']
created_at = datetime.fromisoformat(created_at_str)

# Ensure we're comparing timezone-aware datetimes
if created_at.tzinfo is None:
    created_at = created_at.replace(tzinfo=timezone.utc)
if now.tzinfo is None:
    now = now.replace(tzinfo=timezone.utc)

# Now safe to compare
age_hours = (now - created_at).total_seconds() / 3600
```

### Applied to Both Comparisons

The fix was applied to:

1. **Created timestamp check** (line ~129): Prevents jobs marked as "too old" from being rejected
2. **Retry backoff check** (line ~153): Allows proper backoff period enforcement between retries

---

## Commits

### Commit 59ccec8
- **Message:** "fix: handle timezone-aware datetime comparison in job eligibility check"
- **Changes:** Added timezone import and normalization logic
- **Issue:** Initial commit had redundant local import causing scope error

### Commit ff7aeb4
- **Message:** "fix: remove redundant timezone import causing scope error"
- **Changes:** Removed local `from datetime import timezone` from inside the condition
- **Resolution:** Used the module-level import already present

---

## Impact

### Before Fix
- Background processor unable to process ANY pending jobs
- Job 03ba7 and others stuck indefinitely
- Logs showed: `[INFO] Checked for jobs, found 0 eligible jobs`
- Silent failure (no error logged, just no action taken)

### After Fix
- Background processor correctly identifies eligible pending jobs
- Jobs advance through processing pipeline: pending → processing → completed
- Proper retry backoff enforcement
- Full compatibility with timezone-aware datetime storage

---

## Testing

The fix was verified by:

1. **Deployment:** Pushed fix to main branch (commits 59ccec8, ff7aeb4)
2. **Server restart:** Restarted uvicorn to load new code
3. **Verification:** Confirmed no pending jobs remaining (all processed successfully)
4. **Log confirmation:** No timezone comparison errors in `/var/log/api.log`

---

## Code References

**File:** `decision_data/backend/services/audio_processor.py`

**Method:** `is_job_eligible()` (lines 117-161)

**Key Changes:**
- Line 11: Import timezone from datetime module
- Lines 128-137: Timezone normalization for created_at comparison
- Lines 151-153: Timezone normalization for last_attempt_time comparison

---

## Related Issues Fixed

This fix resolves:
- Job 03ba7 stuck in pending status
- Background processor unable to process pending jobs
- Silent failure in `get_eligible_pending_jobs()` method

---

## Lessons Learned

### 1. Timezone Consistency
Always be consistent with timezone awareness across your application:
- Choose either all timezone-naive OR all timezone-aware
- Our system uses timezone-aware (UTC) for all stored timestamps

### 2. Silent Failures
When catching exceptions silently, always log them:
```python
except Exception as e:
    logger.error(f"[ERROR] Error querying jobs: {e}")  # GOOD
    return []  # Default safe value
```

### 3. Testing Mixed Data
When migrating datetime formats, test with both:
- Old data (potentially timezone-naive)
- New data (timezone-aware with UTC)

---

## Prevention

To prevent similar issues in the future:

1. **Use consistent datetime format** across all layers
2. **Always handle both naive and aware datetimes** in comparison code
3. **Add type hints** to catch timezone issues earlier:
   ```python
   def is_job_eligible(self, job: dict, now: datetime) -> bool:
       # Type hints make timezone expectations explicit
   ```
4. **Add integration tests** for timezone-related code
5. **Log datetime values** during debugging to catch timezone issues:
   ```python
   logger.debug(f"Comparing: {now} (tzinfo={now.tzinfo}) vs {created_at} (tzinfo={created_at.tzinfo})")
   ```

---

## Status: CLOSED

**Fixed:** October 20, 2025 at 00:54 UTC
**Deployed:** Production (commit ff7aeb4)
**Verification:** Job queue processing normally, no pending jobs
