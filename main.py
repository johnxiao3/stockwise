from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from app.database import initialize_database
from app.api.endpoints import router
from app.config import HOST, PORT, DB_PATH
import os

from fastapi import HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware  # Changed import
from app.api.endpoints import scheduler
from typing import Optional
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Schedule the trading task
    scheduler.schedule_task()
    print('start job')
    yield
    # Shutdown: Cleanup (if needed)
    if scheduler.scheduler.running:
        scheduler.scheduler.shutdown()


# Initialize FastAPI app
app = FastAPI(title="Stock Market Analysis",
            lifespan=lifespan,
             description="A FastAPI application for stock market analysis",
             version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.urandom(24).hex(),
    session_cookie="session_token",
    max_age=3600
)



# Update initialization section
if __name__ == "__main__":
    # Initialize database if it doesn't exist
    if not os.path.exists(DB_PATH):
        initialize_database()
    #create_indexes()
    #create_top_gainers_indexes()
    
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)