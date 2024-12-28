from datetime import datetime, timedelta
import asyncio
import os,sys,subprocess
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ..models.strading_state import TradingState
from ..models.db_update_state import DBUpdateState

class TradingScheduler:
    def __init__(self, trading_state: TradingState):
        self.trading_state = trading_state
        self.scheduler = AsyncIOScheduler()
        self.log_file = "static/log.txt"
        
    async def run_trading_task(self):
        """Execute the trading task and log the execution"""
        if not self.trading_state.enabled:
            return
            
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

        print("run onces")
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] Trading task executed\n"
        
        with open(self.log_file, "a") as f:
            f.write(log_message)
            
        self.trading_state.last_run = datetime.now()
        self.trading_state.save_config()
        
    def schedule_task(self):
        """Schedule the trading task based on the configured time"""
        try:
            # Clear existing job if it exists
            if hasattr(self, 'job') and self.job:
                self.job.remove()
                print("Removed existing job")

            # Parse schedule time
            hour, minute = map(int, self.trading_state.schedule_time.split(':'))
            print(f"Scheduling task for {hour}:{minute}")

            # Add new job
            self.job = self.scheduler.add_job(
                self.run_trading_task,
                CronTrigger(hour=hour, minute=minute),
                id='trading_task',
                replace_existing=True  # This ensures no duplicate jobs
            )
            print(f"Added new job with ID: trading_task")

            # Start scheduler if not running
            if not self.scheduler.running:
                print("Starting scheduler...")
                self.scheduler.start()
                print("Scheduler started successfully")

            # Print next run time for verification
            next_run = self.job.next_run_time
            print(f"Next scheduled run time: {next_run}")

        except Exception as e:
            print(f"Error in schedule_task: {str(e)}")

    def get_time_until_next_run(self) -> str:
        """Calculate time remaining until next run"""
        next_run = self.trading_state.calculate_next_run()
        if not next_run:
            return "Not scheduled"
            
        now = datetime.now()
        time_diff = next_run - now
        
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        
        return f"{hours}h {minutes}m"

class DBUpdateScheduler:
    def __init__(self, update_state: DBUpdateState):
        self.update_state = update_state
        self.scheduler = AsyncIOScheduler()
        self.log_file = "static/logs/update_db.txt"

    async def run_update_task(self):
        """Execute the database update task and log the execution"""
        if not self.update_state.enabled:
            return
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        print("Running database update")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] Database update task executed\n"

        with open(self.log_file, "a") as f:
            f.write(log_message)

        self.update_state.last_run = datetime.now()
        self.update_state.save_config()

        #DB_PATH = "static/stock_data.db"
        #update_database(DB_PATH, period='current')
        # Launch subprocess
        subprocess.Popen([sys.executable, 'app/applications/update_db.py'])

        # Add your database update logic here
        # For example:
        # await update_stock_data()
        # await update_market_metrics()

    def schedule_task(self):
        """Schedule the database update task based on the configured time"""
        try:
            # Clear existing job if it exists
            if hasattr(self, 'job') and self.job:
                self.job.remove()
                print("Removed existing DB update job")

            # Parse schedule time
            hour, minute = map(int, self.update_state.schedule_time.split(':'))
            print(f"Scheduling DB update task for {hour}:{minute}")

            # Add new job
            self.job = self.scheduler.add_job(
                self.run_update_task,
                CronTrigger(hour=hour, minute=minute,day_of_week='mon-fri'),
                id='db_update_task',
                replace_existing=True
            )
            print(f"Added new DB update job with ID: db_update_task")

            # Start scheduler if not running
            if not self.scheduler.running:
                print("Starting DB update scheduler...")
                self.scheduler.start()
                print("DB update scheduler started successfully")

            # Print next run time for verification
            next_run = self.job.next_run_time
            print('aa',next_run)
            print(f"Next scheduled DB update run time: {next_run}")

        except Exception as e:
            print(f"Error in DB update schedule_task: {str(e)}")

    def get_time_until_next_run(self) -> str:
        """Calculate time remaining until next database update"""
        next_run = self.update_state.calculate_next_run()
        if not next_run:
            return "Not scheduled"

        # Skip if next run falls on weekend
        while next_run.weekday() in [5, 6]:
            next_run += timedelta(days=1)

        now = datetime.now()
        time_diff = next_run - now
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        return f"{hours}h {minutes}m"