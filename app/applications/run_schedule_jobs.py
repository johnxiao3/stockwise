import os,sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from applications.update_db import update_database
from applications.schedule_jobs.top10_bp import filter_stock
from applications.schedule_jobs.top10_rsi import analyze_rsi
from applications.schedule_jobs.top10_volume import analyze_volume
from applications.schedule_jobs.combine_daily_emails import combine_daily_emails
from applications.schedule_jobs.sendemail_test import send_emails_to_all_subscribers

import time


if __name__ == "__main__":
    # To update current week's data:
    DB_PATH = "static/stock_data.db"
    attempts = 0
    max_attempts = 20
    total_added = 1  # Initialize with non-zero value to enter the loop
    while total_added > 0 and attempts < max_attempts:
        total_added = update_database(DB_PATH, period='current')
        attempts += 1
        if attempts == max_attempts:
            print(f"Reached maximum attempts ({max_attempts})")
        elif total_added == 0:
            print(f"Update completed successfully after {attempts} attempts")    
        time.sleep(20)

    filter_stock(0)
    analyze_rsi()
    analyze_volume()
    combine_daily_emails()

    #send_emails_to_all_subscribers()