from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .routers import submission, status, control

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

# CORS
origins = [
    "http://localhost",
    "http://localhost:5173", # Vite default
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(submission.router, prefix=settings.API_V1_STR + "/submit", tags=["submission"])
app.include_router(status.router, prefix=settings.API_V1_STR + "/status", tags=["status"])
app.include_router(control.router, prefix=settings.API_V1_STR + "/control", tags=["control"])

@app.get("/")
def read_root():
    return {"message": "Welcome to CiteGuard API"}
