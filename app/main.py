from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()  # Load .env file before anything else

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.models import Trip, Preference, UserPreferences, Conversation, Message, Itinerary, SharedItinerary, ItineraryVersion  # noqa: F401 - needed for table creation
from app.routers import health_router, preferences_router, chat_router, itineraries_router, flights_router, accommodations_router, activities_router, share_router, versions_router, geocoding_router, refinements_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
