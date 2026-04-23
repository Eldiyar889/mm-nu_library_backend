from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.routers.book import router as book_router
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.config import settings

app = FastAPI(title="Library API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory to serve files
if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Register routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(book_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Library API"}
