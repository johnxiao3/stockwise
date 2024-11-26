from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List, Dict
import pandas as pd

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

# Setup templates
templates = Jinja2Templates(directory="templates")

# FastAPI routes
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
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
async def stock_detail(request: Request, symbol: str):
    """Show detailed stock data"""
    try:
        cache_timestamp = get_cache_timestamp()
        plot_data = get_stock_data(symbol, cache_timestamp)
        return templates.TemplateResponse(
            "stock_detail.html",
            {"request": request, "symbol": symbol, "plot": plot_data}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/stock_filter", response_class=HTMLResponse)
async def stock_filter(request: Request):
    """Render stock filter page"""
    return templates.TemplateResponse("stock_filter.html", {"request": request})

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