
from pydantic import BaseModel
from datetime import datetime, time, timedelta
from typing import Optional
import os,json

# Pydantic models for request/response validation
class TradingStatusUpdate(BaseModel):
    enabled: bool

class ScheduleUpdate(BaseModel):
    time: str  # HH:MM format

class TokenStatus(BaseModel):
    expireTime: datetime

class RunTimes(BaseModel):
    lastRun: Optional[datetime]
    nextRun: Optional[datetime]

# Helper class to manage trading state
class TradingState:
    def __init__(self):
        self.config_file = "trading_config.json"
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.enabled = config.get('enabled', False)
                    self.schedule_time = config.get('schedule_time', "09:30")
                    self.last_run = datetime.fromisoformat(config.get('last_run')) if config.get('last_run') else None
                    self.token_expire = datetime.fromisoformat(config.get('token_expire')) if config.get('token_expire') else None
            else:
                self.enabled = False
                self.schedule_time = "09:30"
                self.last_run = None
                self.token_expire = None
        except Exception as e:
            print(f"Error loading config: {e}")
            self.enabled = False
            self.schedule_time = "09:30"
            self.last_run = None
            self.token_expire = None

    def save_config(self):
        config = {
            'enabled': self.enabled,
            'schedule_time': self.schedule_time,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'token_expire': self.token_expire.isoformat() if self.token_expire else None
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f)

    def calculate_next_run(self) -> Optional[datetime]:
        if not self.schedule_time:
            return None
            
        hour, minute = map(int, self.schedule_time.split(':'))
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_run <= now:
            next_run += timedelta(days=1)
            
        return next_run