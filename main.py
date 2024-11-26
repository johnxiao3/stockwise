from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from app.database import initialize_database
from app.api.endpoints import router
from app.config import HOST, PORT, DB_PATH
import os

# Initialize FastAPI app
app = FastAPI(title="Stock Market Analysis",
             description="A FastAPI application for stock market analysis",
             version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router)


# Update initialization section
if __name__ == "__main__":
    # Initialize database if it doesn't exist
    if not os.path.exists(DB_PATH):
        initialize_database()
    #create_indexes()
    #create_top_gainers_indexes()
    
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)