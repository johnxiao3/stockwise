from fastapi import APIRouter
from .endpoints import router as main_router
from .email_subscriptions import router as email_router

# Create a main router that includes all other routers
router = APIRouter()

# Include all routers
router.include_router(main_router)
router.include_router(email_router)

# Export schedulers from endpoints for use in main.py
from .endpoints import scheduler, db_scheduler