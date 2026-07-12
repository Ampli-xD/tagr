import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .auth import router as auth_router
from .photos import router as photos_router
from .internal import router as internal_router
from .social import router as social_router

# Initialize the main App
app = FastAPI(title="Tagr Gateways")

# Allow CORS for easy debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Sub-app to prefix everything under /api/v1 per specification
api_v1 = FastAPI(title="Tagr API", version="1.0")
api_v1.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1.include_router(auth_router)
api_v1.include_router(photos_router)
api_v1.include_router(internal_router)
api_v1.include_router(social_router)

# Mount API
app.mount("/api/v1", api_v1)

# Check if we should serve static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

# Mount frontend client at root
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
