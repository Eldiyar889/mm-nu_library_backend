from fastapi import FastAPI
from app.routers.book import router as book_router
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router

app = FastAPI(title="Library API")

# Register routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(book_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Library API"}
