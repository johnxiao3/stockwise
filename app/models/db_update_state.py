from datetime import datetime, timedelta
import json
import os

class DBUpdateState:
    def __init__(self):
        self.enabled = False
        self.schedule_time = "00:00"  # Default to midnight
        self.last_run = None
        self.config_file = "config/db_update_config.json"
        self.load_config()

    def load_config(self):
        """Load configuration from file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.enabled = config.get('enabled', False)
                    self.schedule_time = config.get('schedule_time', "00:00")
                    last_run = config.get('last_run')
                    self.last_run = datetime.fromisoformat(last_run) if last_run else None
        except Exception as e:
            print(f"Error loading DB update config: {str(e)}")

    def save_config(self):
        """Save current configuration to file"""
        try:
            config = {
                'enabled': self.enabled,
                'schedule_time': self.schedule_time,
                'last_run': self.last_run.isoformat() if self.last_run else None
            }
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving DB update config: {str(e)}")

    def calculate_next_run(self) -> datetime:
        """Calculate the next run time based on schedule"""
        if not self.schedule_time:
            return None

        now = datetime.now()
        hour, minute = map(int, self.schedule_time.split(':'))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if next_run <= now:
            next_run += timedelta(days=1)

        return next_run