"""Scheduler for automated tasks."""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask

from automation import AutomationEngine
from config import Config

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Manages scheduled automation tasks."""
    
    def __init__(self, app: Flask):
        """Initialize scheduler with Flask app context."""
        self.app = app
        self.scheduler = BackgroundScheduler()
        self.automation = AutomationEngine()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Configure scheduled jobs."""
        
        # Sync listings every hour
        self.scheduler.add_job(
            func=self._run_sync_listings,
            trigger='interval',
            hours=1,
            id='sync_listings',
            name='Sync Active Listings',
            replace_existing=True
        )
        
        # Check for stale listings (daily at configured time)
        self.scheduler.add_job(
            func=self._run_stale_check,
            trigger=CronTrigger.from_crontab(Config.STALE_CHECK_SCHEDULE),
            id='stale_check',
            name='Check Stale Listings',
            replace_existing=True
        )
        
        # Check for offer opportunities (daily at configured time)
        self.scheduler.add_job(
            func=self._run_offer_check,
            trigger=CronTrigger.from_crontab(Config.OFFER_CHECK_SCHEDULE),
            id='offer_check',
            name='Check Offer Opportunities',
            replace_existing=True
        )
        
        # Sync sold items every 2 hours
        self.scheduler.add_job(
            func=self._run_sync_sold,
            trigger='interval',
            hours=2,
            id='sync_sold',
            name='Sync Sold Items',
            replace_existing=True
        )
        
        # Check for feedback requests (daily at configured time)
        self.scheduler.add_job(
            func=self._run_feedback_check,
            trigger=CronTrigger.from_crontab(Config.FEEDBACK_CHECK_SCHEDULE),
            id='feedback_check',
            name='Request Feedback',
            replace_existing=True
        )
        
        logger.info("Scheduled jobs configured")
    
    def _run_sync_listings(self):
        """Run listing sync in app context."""
        with self.app.app_context():
            try:
                logger.info("Running scheduled listing sync...")
                result = self.automation.sync_listings()
                logger.info(f"Listing sync completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled listing sync: {e}", exc_info=True)
    
    def _run_stale_check(self):
        """Run stale listing check in app context."""
        with self.app.app_context():
            try:
                logger.info("Running scheduled stale listing check...")
                result = self.automation.check_stale_listings()
                logger.info(f"Stale check completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled stale check: {e}", exc_info=True)
    
    def _run_offer_check(self):
        """Run offer check in app context."""
        with self.app.app_context():
            try:
                logger.info("Running scheduled offer check...")
                result = self.automation.send_offers_to_watchers()
                logger.info(f"Offer check completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled offer check: {e}", exc_info=True)
    
    def _run_sync_sold(self):
        """Run sold items sync in app context."""
        with self.app.app_context():
            try:
                logger.info("Running scheduled sold items sync...")
                result = self.automation.sync_sold_items()
                logger.info(f"Sold items sync completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled sold items sync: {e}", exc_info=True)
    
    def _run_feedback_check(self):
        """Run feedback request check in app context."""
        with self.app.app_context():
            try:
                logger.info("Running scheduled feedback check...")
                result = self.automation.request_feedback_from_buyers()
                logger.info(f"Feedback check completed: {result}")
            except Exception as e:
                logger.error(f"Error in scheduled feedback check: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def get_jobs(self):
        """Get list of scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs


