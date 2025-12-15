"""
Backup Scheduler Service - NUOVO MODULO
Scheduler automatico per backup periodici configurazioni dispositivi
Esegue backup secondo schedule configurati per cliente

Non modifica servizi esistenti
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from ..models.database import get_db_session
    from ..models.backup_models import BackupSchedule, BackupJob
    from .device_backup_service import DeviceBackupService
except ImportError:
    pass


class BackupScheduler:
    """
    Scheduler automatico per backup periodici
    Usa APScheduler per gestire job ricorrenti
    """

    def __init__(self, db_session_factory=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scheduler = AsyncIOScheduler()
        self.db_session_factory = db_session_factory or get_db_session
        self.running = False

        self.logger.info("BackupScheduler initialized")

    def start(self):
        """Avvia lo scheduler"""
        if not self.running:
            self.scheduler.start()
            self.running = True
            self.logger.info("BackupScheduler started")

            # Carica schedule esistenti
            self._load_schedules()

            # Aggiungi job per sync periodico schedule (ogni ora)
            self.scheduler.add_job(
                self._sync_schedules,
                trigger='interval',
                hours=1,
                id='sync_schedules',
                replace_existing=True
            )

    def stop(self):
        """Ferma lo scheduler"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            self.logger.info("BackupScheduler stopped")

    def _load_schedules(self):
        """Carica tutti gli schedule attivi dal database"""
        try:
            db = next(self.db_session_factory())

            schedules = db.query(BackupSchedule).filter_by(enabled=True).all()
            self.logger.info(f"Loading {len(schedules)} active schedules...")

            for schedule in schedules:
                self._add_schedule_job(schedule)

            db.close()

        except Exception as e:
            self.logger.error(f"Error loading schedules: {e}", exc_info=True)

    def _sync_schedules(self):
        """Sincronizza schedule dal database (chiamato periodicamente)"""
        try:
            self.logger.debug("Syncing schedules from database...")
            db = next(self.db_session_factory())

            schedules = db.query(BackupSchedule).filter_by(enabled=True).all()

            # Rimuovi job non più attivi
            current_jobs = {job.id for job in self.scheduler.get_jobs()}
            active_schedule_ids = {f"backup_schedule_{s.id}" for s in schedules}

            for job_id in current_jobs:
                if job_id.startswith("backup_schedule_") and job_id not in active_schedule_ids:
                    self.scheduler.remove_job(job_id)
                    self.logger.info(f"Removed inactive schedule job: {job_id}")

            # Aggiungi/aggiorna schedule attivi
            for schedule in schedules:
                self._add_schedule_job(schedule, replace=True)

            db.close()

        except Exception as e:
            self.logger.error(f"Error syncing schedules: {e}", exc_info=True)

    def _add_schedule_job(self, schedule: BackupSchedule, replace: bool = False):
        """
        Aggiunge un job di schedule allo scheduler

        Args:
            schedule: BackupSchedule dal database
            replace: Se True, sostituisce job esistente
        """
        try:
            job_id = f"backup_schedule_{schedule.id}"

            # Crea trigger basato su schedule_type
            trigger = self._create_trigger(schedule)

            if not trigger:
                self.logger.warning(f"Could not create trigger for schedule {schedule.id}")
                return

            # Aggiungi job
            self.scheduler.add_job(
                func=self._execute_scheduled_backup,
                trigger=trigger,
                args=[schedule.id],
                id=job_id,
                replace_existing=replace,
                misfire_grace_time=3600  # 1 ora di grace time
            )

            self.logger.info(f"Added schedule job: {job_id} ({schedule.schedule_type} @ {schedule.schedule_time})")

        except Exception as e:
            self.logger.error(f"Error adding schedule job for {schedule.id}: {e}", exc_info=True)

    def _create_trigger(self, schedule: BackupSchedule) -> Optional[CronTrigger]:
        """
        Crea trigger APScheduler basato su configurazione schedule

        Returns:
            CronTrigger configurato
        """
        try:
            # Parse schedule_time (HH:MM)
            if schedule.schedule_time:
                hour, minute = map(int, schedule.schedule_time.split(':'))
            else:
                hour, minute = 3, 0  # Default 03:00

            if schedule.schedule_type == "daily":
                # Ogni giorno alle HH:MM
                return CronTrigger(hour=hour, minute=minute)

            elif schedule.schedule_type == "weekly":
                # Giorni specifici della settimana
                if schedule.schedule_days:
                    # schedule_days: [0,1,2,3,4,5,6] (0=Lunedì)
                    # Converti a formato cron (0=Domenica)
                    cron_days = [(d + 1) % 7 for d in schedule.schedule_days]
                    day_of_week = ','.join(map(str, sorted(cron_days)))
                else:
                    day_of_week = '0'  # Default Domenica

                return CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week)

            elif schedule.schedule_type == "monthly":
                # Giorno specifico del mese
                day = schedule.schedule_day_of_month or 1
                return CronTrigger(hour=hour, minute=minute, day=day)

            elif schedule.schedule_type == "custom" and schedule.cron_expression:
                # Usa cron expression custom
                # Format: "minute hour day month day_of_week"
                parts = schedule.cron_expression.split()
                if len(parts) == 5:
                    return CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4]
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error creating trigger: {e}", exc_info=True)
            return None

    async def _execute_scheduled_backup(self, schedule_id: str):
        """
        Esegue backup schedulato

        Args:
            schedule_id: ID dello schedule da eseguire
        """
        db = None

        try:
            db = next(self.db_session_factory())

            # Recupera schedule
            schedule = db.query(BackupSchedule).filter_by(id=schedule_id).first()

            if not schedule or not schedule.enabled:
                self.logger.warning(f"Schedule {schedule_id} not found or disabled")
                return

            self.logger.info(f"Executing scheduled backup for customer {schedule.customer_id}")

            # Aggiorna last_run
            schedule.last_run_at = datetime.now()
            schedule.total_runs += 1
            db.commit()

            # Crea DeviceBackupService
            backup_service = DeviceBackupService(db=db)

            # Esegui backup di tutti i device del cliente
            result = backup_service.backup_customer_devices(
                customer_id=schedule.customer_id,
                backup_type=schedule.backup_types[0] if schedule.backup_types else "config",
                device_type_filter=schedule.device_type_filter,
                triggered_by=f"scheduler:{schedule_id}"
            )

            # Aggiorna statistiche schedule
            if result["success"]:
                schedule.total_successes += 1
                schedule.last_run_success = True
                schedule.last_run_devices_count = result.get("total_devices", 0)
                schedule.last_run_errors_count = result.get("failed_count", 0)
            else:
                schedule.total_failures += 1
                schedule.last_run_success = False

            # Calcola prossima esecuzione
            schedule.next_run_at = self._calculate_next_run(schedule)

            db.commit()

            # Esegui cleanup backup vecchi se configurato
            if schedule.retention_days:
                self.logger.info(f"Running cleanup for customer {schedule.customer_id}")
                cleanup_result = backup_service.cleanup_old_backups(
                    customer_id=schedule.customer_id,
                    retention_days=schedule.retention_days
                )
                self.logger.info(f"Cleanup completed: {cleanup_result}")

            self.logger.info(f"Scheduled backup completed for {schedule.customer_id}: "
                           f"{result.get('success_count', 0)} success, "
                           f"{result.get('failed_count', 0)} failed")

        except Exception as e:
            self.logger.error(f"Error executing scheduled backup {schedule_id}: {e}", exc_info=True)

            # Aggiorna schedule con errore
            if db and schedule:
                schedule.total_failures += 1
                schedule.last_run_success = False
                db.commit()

        finally:
            if db:
                db.close()

    def _calculate_next_run(self, schedule: BackupSchedule) -> Optional[datetime]:
        """
        Calcola prossima esecuzione dello schedule

        Returns:
            datetime della prossima esecuzione
        """
        try:
            job_id = f"backup_schedule_{schedule.id}"
            job = self.scheduler.get_job(job_id)

            if job and job.next_run_time:
                return job.next_run_time

            return None

        except Exception as e:
            self.logger.error(f"Error calculating next run: {e}")
            return None

    def add_schedule(self, schedule_id: str):
        """
        Aggiunge dinamicamente un nuovo schedule

        Args:
            schedule_id: ID schedule da aggiungere
        """
        try:
            db = next(self.db_session_factory())
            schedule = db.query(BackupSchedule).filter_by(id=schedule_id).first()

            if schedule and schedule.enabled:
                self._add_schedule_job(schedule, replace=True)
                self.logger.info(f"Schedule {schedule_id} added/updated")

            db.close()

        except Exception as e:
            self.logger.error(f"Error adding schedule {schedule_id}: {e}", exc_info=True)

    def remove_schedule(self, schedule_id: str):
        """
        Rimuove schedule

        Args:
            schedule_id: ID schedule da rimuovere
        """
        try:
            job_id = f"backup_schedule_{schedule_id}"
            self.scheduler.remove_job(job_id)
            self.logger.info(f"Schedule {schedule_id} removed")

        except Exception as e:
            self.logger.error(f"Error removing schedule {schedule_id}: {e}", exc_info=True)

    def get_next_runs(self) -> List[dict]:
        """
        Recupera lista prossime esecuzioni

        Returns:
            Lista dict con info prossimi job
        """
        jobs = self.scheduler.get_jobs()

        return [
            {
                "job_id": job.id,
                "schedule_id": job.id.replace("backup_schedule_", "") if job.id.startswith("backup_schedule_") else None,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in jobs
            if job.id.startswith("backup_schedule_")
        ]


# ==========================================
# SINGLETON INSTANCE
# ==========================================

_scheduler_instance: Optional[BackupScheduler] = None


def get_backup_scheduler() -> BackupScheduler:
    """
    Ottiene istanza singleton dello scheduler

    Returns:
        BackupScheduler instance
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = BackupScheduler()

    return _scheduler_instance


def start_backup_scheduler():
    """Avvia scheduler globale"""
    scheduler = get_backup_scheduler()
    if not scheduler.running:
        scheduler.start()


def stop_backup_scheduler():
    """Ferma scheduler globale"""
    scheduler = get_backup_scheduler()
    if scheduler.running:
        scheduler.stop()
