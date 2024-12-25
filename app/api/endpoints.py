from fastapi import APIRouter, Request, HTTPException, Query, Depends,Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import pandas as pd
from passlib.context import CryptContext
import aiofiles
from pathlib import Path

from datetime import datetime, time, timedelta
from app.models.scheduler import TradingScheduler
from ..models.scheduler import TradingScheduler, DBUpdateScheduler
from ..models.strading_state import TradingState
from ..models.db_update_state import DBUpdateState

# Initialize router
from ..models.strading_state import *
from ..database import get_db_connection
from ..services.cache import get_cache_timestamp
from ..services.stock import (
    get_top_gainers_data,
    get_stock_data,
    get_database_stats,
    get_data_summary,
    get_filtered_stocks
)

# Initialize router
router = APIRouter()



# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
HASHED_PASSWORD = pwd_context.hash("0705")

def verify_password(plain_password: str) -> bool:
    return pwd_context.verify(plain_password, HASHED_PASSWORD)

def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated", False)

async def require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return True


# Setup templates
templates = Jinja2Templates(directory="templates")

# FastAPI routes
@router.get("/", response_class=HTMLResponse)
async def index(request: Request,auth: bool = Depends(require_auth)):
    """Show all available stock data"""
    try:
        cache_timestamp = get_cache_timestamp()
        stats = get_database_stats(cache_timestamp)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "total_records": stats['total_records'],
                "total_stocks": stats['total_stocks'],
                "database_size": stats['database_size']
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/top-gainers", response_class=HTMLResponse)
async def top_gainers(request: Request):
    """Show top 20 stocks by percentage increase from last week"""
    try:
        cache_timestamp = get_cache_timestamp()
        result_dict = get_top_gainers_data(cache_timestamp)
        return templates.TemplateResponse(
            "top_gainers.html",
            {"request": request, "top_stocks": result_dict}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stock/{symbol}")
async def stock(symbol: str):
    """Handle stock links from top-gainers page"""
    return RedirectResponse(url=f"/stockdetail/{symbol}")



@router.get("/stockdetail/{symbol}", response_class=HTMLResponse)
async def stock_detail(request: Request, symbol: str, auth: bool = Depends(require_auth)):
    """Show detailed stock data"""
    try:
        cache_timestamp = get_cache_timestamp()
        plot_data = get_stock_data(symbol, cache_timestamp)
        
        return templates.TemplateResponse(
            "stock_detail_wrapper.html",
            {
                "request": request, 
                "symbol": symbol, 
                "plot": plot_data
            }
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Error in stock_detail for {symbol}: {str(e)}")
        
        # Return an error page instead of raising an exception
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": f"Error loading stock data for {symbol}: {str(e)}"
            },
            status_code=500
        )

@router.get("/api/filtered_stocks")
async def filtered_stocks(
    limit: int = Query(50, ge=1),
    min_price: float = Query(0, ge=0),
    min_volume: int = Query(0, ge=0),
    min_price_change: float = Query(-100),
    sort_by: str = Query("volume_change", pattern="^(volume|price|volume_change|price_change)$"),
    sort_order: str = Query("DESC", pattern="^(ASC|DESC)$")
):
    """API endpoint for filtered stocks"""
    try:
        results = get_filtered_stocks(limit, min_price, min_volume, min_price_change, sort_by, sort_order)
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stockfilter", response_class=HTMLResponse)
async def stockfilter(request: Request):
    """Render stock filter page"""
    return templates.TemplateResponse("stock_filter_wrapper.html", {"request": request})

@router.get("/autotrading", response_class=HTMLResponse)
async def stockfilter(request: Request):
    """Render stock filter page"""
    return templates.TemplateResponse("autotrading.html", {"request": request})

@router.get("/clear_cache")
async def clear_cache():
    """Clear the LRU cache"""
    get_stock_data.cache_clear()
    return {"message": "Cache cleared"}



# Additional FastAPI routes
@router.get("/summary", response_class=HTMLResponse)
async def summary(request: Request):
    """Show data summary"""
    counts = get_data_summary()
    return templates.TemplateResponse(
        "summary.html",
        {"request": request, "counts": counts}
    )

@router.get("/volume-gainers", response_class=HTMLResponse)
async def volume_gainers(request: Request):
    """Show top 20 stocks by volume increase"""
    conn = get_db_connection()
    try:
        # Get the latest date that's a Monday
        date_query = """
        SELECT MAX(date) 
        FROM stock_prices 
        WHERE timeframe = 'weekly' AND symbol='AAPL'
        """
        latest_date = pd.read_sql_query(date_query, conn).iloc[0, 0]
        
        # Get the previous week's Monday
        prev_date = pd.read_sql_query(
            """
            SELECT MAX(date) 
            FROM stock_prices 
            WHERE timeframe = 'weekly' AND symbol='AAPL'
            AND date < ?
            """,
            conn,
            params=(latest_date,)
        ).iloc[0, 0]

        volume_query = """
        WITH CurrentWeek AS (
            SELECT symbol, volume, open, close
            FROM stock_prices
            WHERE timeframe = 'weekly' 
            AND date = ?
        ),
        PrevWeek AS (
            SELECT symbol, volume as prev_volume
            FROM stock_prices
            WHERE timeframe = 'weekly' 
            AND date = ?
        )
        SELECT 
            c.symbol,
            c.open as current_open,
            c.close as current_close,
            c.volume as current_volume,
            p.prev_volume,
            ROUND(((c.volume - p.prev_volume) * 100.0 / p.prev_volume), 2) as volume_change
        FROM CurrentWeek c
        JOIN PrevWeek p ON c.symbol = p.symbol
        WHERE p.prev_volume > 0
        ORDER BY volume_change DESC
        LIMIT 20
        """
        
        df = pd.read_sql_query(
            volume_query,
            conn,
            params=(latest_date, prev_date),
            coerce_float=True
        )
        
        df['current_volume'] = df['current_volume'].astype(int)
        df['prev_volume'] = df['prev_volume'].astype(int)
        
        return templates.TemplateResponse(
            "volume_gainers.html",
            {"request": request, "top_stocks": df.to_dict('records')}
        )
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        conn.close()

@router.get("/stock/{symbol}")
async def stock_data(request: Request, symbol: str):
    """Show data for a specific stock"""
    conn = get_db_connection()
    
    # Get summary counts
    total_records = pd.read_sql_query(
        "SELECT COUNT(*) as count FROM stock_prices",
        conn
    ).iloc[0]['count']
    
    total_stocks = pd.read_sql_query(
        "SELECT COUNT(DISTINCT symbol) as count FROM stock_prices",
        conn
    ).iloc[0]['count']
    
    # Get data for specific stock
    daily_data = pd.read_sql_query(
        "SELECT * FROM stock_prices WHERE symbol=? AND timeframe='daily' ORDER BY date DESC LIMIT 100",
        conn,
        params=(symbol,)
    )
    
    weekly_data = pd.read_sql_query(
        "SELECT * FROM stock_prices WHERE symbol=? AND timeframe='weekly' ORDER BY date DESC LIMIT 52",
        conn,
        params=(symbol,)
    )
    
    conn.close()
    
    return templates.TemplateResponse(
        "stock_data.html",
        {
            "request": request,
            "symbol": symbol,
            "total_records": total_records,
            "total_stocks": total_stocks,
            "daily_data": daily_data.to_dict('records'),
            "weekly_data": weekly_data.to_dict('records')
        }
    )




@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None}
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if verify_password(password):
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401
    )

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)




# Create global trading state
#trading_state = TradingState()
#scheduler = TradingScheduler(trading_state)

trading_state = TradingState()
db_update_state = DBUpdateState()
scheduler = TradingScheduler(trading_state)
db_scheduler = DBUpdateScheduler(db_update_state)


#===================================
@router.post("/api/trigger-db-update")
async def trigger_db_update():
    try:
        # Run the update task directly
        await db_scheduler.run_update_task()
        return {"status": "success", "message": "Database update triggered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# Add these new routes for database updates
@router.get("/updatedb", response_class=HTMLResponse)
async def get_updatedb_page(request: Request):
    return templates.TemplateResponse("updatedb.html", {"request": request})

@router.post("/api/toggle-db-update")
async def toggle_db_update(enabled: dict):
    db_update_state.enabled = enabled.get("enabled", False)
    db_update_state.save_config()
    return {"status": "success", "enabled": db_update_state.enabled}

@router.post("/api/update-db-schedule")
async def update_db_schedule(schedule: dict):
    new_time = schedule.get("time")
    if not new_time:
        raise HTTPException(status_code=400, detail="Time not provided")
    
    db_update_state.schedule_time = new_time
    db_update_state.save_config()
    db_scheduler.schedule_task()
    
    next_run = db_update_state.calculate_next_run()
    return {
        "status": "success",
        "schedule_time": db_update_state.schedule_time,
        "next_run": next_run.isoformat() if next_run else None
    }

@router.get("/api/db-update-status")
async def get_db_update_status():
    next_run = db_update_state.calculate_next_run()
    return {
        "enabled": db_update_state.enabled,
        "schedule_time": db_update_state.schedule_time,
        "last_run": db_update_state.last_run.isoformat() if db_update_state.last_run else None,
        "next_run": next_run.isoformat() if next_run else None
    }

@router.get("/api/db-next-run-time")
async def get_db_next_run_time():
    next_run = db_update_state.calculate_next_run()
    return {
        "lastRun": db_update_state.last_run.isoformat() if db_update_state.last_run else None,
        "nextRun": next_run.isoformat() if next_run else None
    }

@router.get("/api/db-update-log")
async def get_db_update_log():
    try:
        with open("static/logs/update_db.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "No log entries yet."
#===================================


# Router endpoints
@router.post("/api/toggle-trading")
async def toggle_trading(status: TradingStatusUpdate):
    trading_state.enabled = status.enabled
    trading_state.save_config()
    return {"status": "success", "enabled": trading_state.enabled}

@router.post("/api/update-schedule")
async def update_schedule(schedule: ScheduleUpdate):
    try:
        # Validate time format
        time.fromisoformat(schedule.time)
        
        # Update the schedule time in trading state
        trading_state.schedule_time = schedule.time
        trading_state.save_config()
        
        # Reschedule the job with new time
        scheduler.schedule_task()  # This will remove old job and create new one
        
        print(f"Schedule updated to: {schedule.time}")
        print(f"Next run time: {scheduler.job.next_run_time if hasattr(scheduler, 'job') else 'No job scheduled'}")
        
        return {
            "status": "success", 
            "schedule_time": schedule.time,
            "next_run": scheduler.job.next_run_time if hasattr(scheduler, 'job') else None
        }
    except ValueError as e:
        print(f"Error updating schedule: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid time format")
    except Exception as e:
        print(f"Unexpected error updating schedule: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update schedule")

@router.post("/api/update-token")
async def update_token():
    try:
        # Simulate token refresh - replace with actual Schwab API call
        trading_state.token_expire = datetime.now() + timedelta(hours=24)
        trading_state.save_config()
        return {"status": "success", "expire_time": trading_state.token_expire}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/token-status", response_model=TokenStatus)
async def get_token_status():
    if not trading_state.token_expire:
        # If no token exists, set a expired time
        return TokenStatus(expireTime=datetime.now())
    return TokenStatus(expireTime=trading_state.token_expire)

@router.get("/api/next-run-time", response_model=RunTimes)
async def get_run_times():
    return RunTimes(
        lastRun=trading_state.last_run,
        nextRun=trading_state.calculate_next_run()
    )

@router.get("/api/trading-log")
async def get_trading_log():
    log_path = Path("static/log.txt")
    try:
        # Check if file exists and create it if it doesn't
        if not log_path.exists():
            # Create directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty file
            log_path.touch()
            return "No log entries yet."
        
        # Read file content
        async with aiofiles.open(log_path, mode='r', encoding='utf-8') as file:
            content = await file.read()
            return content if content else "No log entries yet."
            
    except Exception as e:
        print(f"Error reading log file: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

# Optional: Endpoint to get current trading status
@router.get("/api/trading-status")
async def get_trading_status():
    return {
        "enabled": trading_state.enabled,
        "schedule_time": trading_state.schedule_time,
        "last_run": trading_state.last_run,
        "next_run": trading_state.calculate_next_run(),
        "token_expire": trading_state.token_expire
    }