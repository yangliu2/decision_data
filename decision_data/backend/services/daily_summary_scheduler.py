"""
Daily Summary Scheduler

Independently manages automatic daily summary job creation based on user preferences.
Runs in background and creates daily_summary jobs at each user's preferred time.

This is separate from the audio processor to maintain clean separation of concerns:
- audio_processor: Handles audio transcription jobs
- daily_summary_scheduler: Handles time-based daily summary scheduling
"""

import asyncio
from datetime import datetime, date
from typing import Dict
import logging

from decision_data.backend.services.transcription_service import UserTranscriptionService
from decision_data.backend.services.preferences_service import UserPreferencesService
from decision_data.backend.services.daily_summary_tracking_service import DailySummaryTrackingService
from decision_data.backend.config.config import backend_config

logger = logging.getLogger(__name__)


class DailySummaryScheduler:
    """Manages automatic daily summary job creation based on user preferences."""

    def __init__(self):
        self.transcription_service = UserTranscriptionService()
        self.preferences_service = UserPreferencesService()
        self.tracking_service = DailySummaryTrackingService()
        self.is_running = False

        # Track which users have had summaries scheduled today (in-memory cache)
        # Format: {user_id: date_scheduled}
        # This is populated from DB on startup and updated as jobs are created
        self.scheduled_today = {}

        # Only check schedule every 5 minutes (not every loop iteration)
        self.last_schedule_check = None
        self.schedule_check_interval_seconds = 300  # 5 minutes

    async def start_scheduler(self):
        """Start the daily summary scheduler background task."""
        logger.info("[SCHEDULER] Starting daily summary scheduler...")
        logger.info(f"[SCHEDULER] Will check for scheduled summaries every {self.schedule_check_interval_seconds} seconds")

        # Load today's scheduled summaries from database on startup
        logger.info("[SCHEDULER] Loading today's scheduled summaries from persistent storage...")
        try:
            today_scheduled = await asyncio.to_thread(
                self.tracking_service.reset_daily_tracking
            )
            self.scheduled_today.update(today_scheduled)
            logger.info(f"[SCHEDULER] Loaded {len(today_scheduled)} summaries from database")
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to load today's summaries from DB: {e}", exc_info=True)
            logger.warning("[SCHEDULER] Proceeding with empty cache (may create duplicate summaries if DB is unavailable)")

        self.is_running = True
        while self.is_running:
            try:
                await self.check_and_schedule_summaries()
                await asyncio.sleep(30)  # Check every 30 seconds (cheaper check)
            except Exception as e:
                logger.error(f"[SCHEDULER] Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(30)

    def stop_scheduler(self):
        """Stop the daily summary scheduler."""
        logger.info("[SCHEDULER] Stopping daily summary scheduler...")
        self.is_running = False

    async def check_and_schedule_summaries(self):
        """Check if it's time to create daily summary jobs for any users.

        This method:
        1. Checks if it's time to run (every 5 minutes)
        2. Scans all users with daily_summary enabled
        3. Checks each user's preferred summary_time_utc
        4. Creates job if time matches and not already sent today
        """
        try:
            now = datetime.utcnow()
            current_date = now.date()

            # Only do expensive preference scanning every 5 minutes
            if self.last_schedule_check is not None:
                time_since_check = (now - self.last_schedule_check).total_seconds()
                if time_since_check < self.schedule_check_interval_seconds:
                    return

            self.last_schedule_check = now
            current_hour = now.hour
            current_minute = now.minute

            logger.info(f"[SCHEDULER] Checking for users to send daily summaries (current UTC time: {current_hour:02d}:{current_minute:02d})")

            # Get all users with daily summary enabled
            try:
                users_to_summarize = self.preferences_service.get_users_with_daily_summary_enabled()
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to fetch users with daily summary enabled: {e}", exc_info=True)
                return

            if not users_to_summarize:
                logger.info("[SCHEDULER] No users with daily summary enabled")
                return

            logger.info(f"[SCHEDULER] Checking {len(users_to_summarize)} users with daily summary enabled")

            # Track how many jobs we create this cycle
            jobs_created = 0

            # Check each user's preferred summary time
            for preferences in users_to_summarize:
                user_id = preferences.user_id

                try:
                    # Check if we already scheduled for this user today
                    last_scheduled_date = self.scheduled_today.get(user_id)
                    if last_scheduled_date == current_date:
                        logger.info(f"[SCHEDULER] Daily summary already scheduled for user {user_id} today")
                        continue

                    # Convert user's local time to UTC for scheduling
                    # User preference: summary_time_local (e.g., "09:00") + timezone_offset_hours (e.g., -6)
                    # Example: 09:00 CST (offset -6) = 15:00 UTC
                    summary_time_local = preferences.summary_time_local
                    timezone_offset_hours = preferences.timezone_offset_hours

                    pref_hour_local, pref_minute = map(int, summary_time_local.split(':'))

                    # Convert local time to UTC by subtracting the offset
                    # (positive offset = east of UTC, negative = west of UTC)
                    pref_hour_utc = (pref_hour_local - timezone_offset_hours) % 24

                    logger.debug(f"[SCHEDULER] User {user_id} prefers {summary_time_local} local (offset {timezone_offset_hours:+d}h) = {pref_hour_utc:02d}:{pref_minute:02d} UTC")

                    # Check if current UTC time is within 5-minute window of preferred UTC time
                    # (allows for some flexibility in exact timing)
                    time_match = (
                        current_hour == pref_hour_utc and
                        current_minute >= pref_minute and
                        current_minute < pref_minute + 5
                    )

                    if not time_match:
                        continue

                    # It's time to create a summary job for this user!
                    logger.info(f"[SCHEDULER] Time match! Creating daily summary job for user {user_id} (preferred time: {pref_hour_utc:02d}:{pref_minute:02d} UTC, current time: {current_hour:02d}:{current_minute:02d} UTC)")

                    try:
                        # Create the daily_summary job
                        job_id = self.transcription_service.create_processing_job(
                            user_id=user_id,
                            job_type='daily_summary'
                        )

                        # Mark that we've scheduled for this user today (in memory)
                        self.scheduled_today[user_id] = current_date

                        # Persist the tracking record to database
                        date_str = current_date.strftime('%Y%m%d')
                        tracking_success = await asyncio.to_thread(
                            self.tracking_service.mark_summary_scheduled,
                            user_id, job_id, date_str
                        )

                        if tracking_success:
                            logger.info(f"[SCHEDULER] Created auto daily summary job {job_id} for user {user_id}")
                            jobs_created += 1
                        else:
                            logger.error(f"[SCHEDULER] Failed to track summary for user {user_id}, but job created: {job_id}")
                            # Still count it since the job was created, just tracking failed
                            jobs_created += 1

                    except Exception as e:
                        logger.error(f"[SCHEDULER] Failed to create daily summary job for user {user_id}: {e}", exc_info=True)
                        continue

                except ValueError as e:
                    logger.error(f"[SCHEDULER] Invalid summary time format for user {user_id}: {preferences.summary_time_utc} - {e}")
                    continue
                except Exception as e:
                    logger.error(f"[SCHEDULER] Error processing user {user_id}: {e}", exc_info=True)
                    continue

            if jobs_created > 0:
                logger.info(f"[SCHEDULER] Created {jobs_created} auto daily summary job(s) in this check")

        except Exception as e:
            logger.error(f"[SCHEDULER] Unexpected error in check_and_schedule_summaries: {e}", exc_info=True)

    def reset_daily_tracking(self):
        """Reset the daily tracking dictionary (called at midnight UTC).

        This allows the scheduler to create summaries again for each user the next day.
        """
        logger.info("[SCHEDULER] Resetting daily tracking - new day has started")
        self.scheduled_today = {}


# Global scheduler instance
scheduler = DailySummaryScheduler()


async def start_daily_summary_scheduler():
    """Start the daily summary scheduler background task."""
    await scheduler.start_scheduler()


def stop_daily_summary_scheduler():
    """Stop the daily summary scheduler."""
    scheduler.stop_scheduler()
