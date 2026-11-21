from fastapi import FastAPI

from app.api.auth import router as auth_router


app = FastAPI(
    title="LeaveDesk API",
    description="Employee Leave and Work From Home Management System",
    version="1.0.0"
)

# Register authentication routes
app.include_router(auth_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to LeaveDesk API",
        "status": "running"
    }