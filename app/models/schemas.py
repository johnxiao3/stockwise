from pydantic import BaseModel, Field
from typing import Optional



# Pydantic models
class StockData(BaseModel):
    symbol: str
    open: float
    close: float
    percentage_change: float
    vol_change_week1: Optional[float]
    vol_change_week2: Optional[float]
    vol_change_week3: Optional[float]
    vol_change_week4: Optional[float]

class DatabaseStats(BaseModel):
    total_records: int
    total_stocks: int
    database_size: float

class VolumeSummary(BaseModel):
    symbol: str
    current_open: float
    current_close: float
    current_volume: int
    prev_volume: int
    volume_change: float

class DataSummary(BaseModel):
    symbol: str
    timeframe: str
    count: int
    start_date: str
    end_date: str

class FilterParams(BaseModel):
    limit: int = Field(50, ge=1)
    min_price: float = Field(0, ge=0)
    min_volume: int = Field(0, ge=0)
    min_price_change: float = Field(-100)
    sort_by: str = Field("volume_change")
    sort_order: str = Field("DESC")

