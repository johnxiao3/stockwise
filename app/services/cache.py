from datetime import datetime
from functools import lru_cache
from ..config import CACHE_DURATION

# Cache and utility functions
def get_cache_timestamp():
    """Return a timestamp rounded to 5-minute intervals for cache key"""
    now = datetime.now()
    return now.replace(second=0, microsecond=0).timestamp() // CACHE_DURATION * CACHE_DURATION

# Define cache decorators
top_gainers_cache = lru_cache(maxsize=100)
stock_data_cache = lru_cache(maxsize=100)
database_stats_cache = lru_cache(maxsize=100)