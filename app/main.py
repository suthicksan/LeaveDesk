from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.leaves import router as leaves_router
from app.api.wfh import router as wfh_router
from app.models.wfh import WFHRequest
from app.api.manager import router as manager_router
from app.api.reports import router as reports_router
from app.api.health import router as health_router
app = FastAPI(
    title="LeaveDesk API",
    description="Employee Leave and Work From Home Management System",
    version="1.0.0"
)

# Register authentication routes
app.include_router(auth_router)
app.include_router(leaves_router)
app.include_router(wfh_router)
app.include_router(manager_router)
app.include_router(reports_router)
app.include_router(health_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to LeaveDesk API",
        "status": "running"
    }