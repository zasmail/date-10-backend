import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()  # Load .env file before anything else

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.models import Trip, Preference, UserPreferences, Conversation, Message, Itinerary, SharedItinerary, ItineraryVersion, SectionedItineraryModel  # noqa: F401 - needed for table creation
from app.routers import health_router, preferences_router, chat_router, itineraries_router, flights_router, accommodations_router, activities_router, share_router, versions_router, geocoding_router, refinements_router, sections_router, agent_chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

# CORS origins - allow localhost for dev, plus any configured frontend URLs
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add configured frontend URL(s) from environment
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    cors_origins.append(frontend_url)

# Also allow all Vercel preview deployments
cors_origins.append("https://*.vercel.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(preferences_router)
app.include_router(chat_router)
app.include_router(itineraries_router)
app.include_router(flights_router)
app.include_router(accommodations_router)
app.include_router(activities_router)
app.include_router(share_router)
app.include_router(versions_router)
app.include_router(geocoding_router)
app.include_router(refinements_router)
app.include_router(sections_router)
app.include_router(agent_chat_router)
