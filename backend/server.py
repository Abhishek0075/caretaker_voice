"""
server.py - FastAPI REST API server
Handles: LiveKit token generation, Tavus avatar, call sessions, appointments REST API
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db

# LiveKit server SDK
from livekit.api import AccessToken, VideoGrants, LiveKitAPI

logger = logging.getLogger("mykare-server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mykare Voice AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000"), "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────
class TokenRequest(BaseModel):
    room_name: Optional[str] = None
    participant_name: Optional[str] = "Patient"


class TavusSessionRequest(BaseModel):
    room_name: str
    session_id: str


class AppointmentCreate(BaseModel):
    phone_number: str
    patient_name: str
    date: str
    time: str
    doctor: str = "Dr. General"
    department: str = "General"
    notes: str = ""


class ModifyAppointment(BaseModel):
    new_date: Optional[str] = None
    new_time: Optional[str] = None


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await db.init_db()
    logger.info("[Server] Database initialized")


# ─────────────────────────────────────────────
# LiveKit Token endpoint
# ─────────────────────────────────────────────
@app.post("/api/token")
async def generate_token(request: TokenRequest):
    """Generate a LiveKit access token for the frontend participant."""
    try:
        room_name = request.room_name or f"mykare-{uuid.uuid4().hex[:8]}"
        participant_name = request.participant_name or "Patient"

        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        livekit_url = os.getenv("LIVEKIT_URL")

        if not all([api_key, api_secret, livekit_url]):
            raise HTTPException(status_code=500, detail="LiveKit credentials not configured")

        token = (
            AccessToken(api_key, api_secret)
            .with_identity(participant_name)
            .with_name(participant_name)
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .with_ttl(timedelta(hours=2))
            .to_jwt()
        )

        return {
            "token": token,
            "room_name": room_name,
            "livekit_url": livekit_url,
            "session_id": f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        }
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Tavus Avatar endpoints
# ─────────────────────────────────────────────
@app.post("/api/tavus/session")
async def create_tavus_session(request: TavusSessionRequest):
    """Create a Tavus conversational video session."""
    tavus_api_key = os.getenv("TAVUS_API_KEY")
    replica_id = os.getenv("TAVUS_REPLICA_ID")

    if not tavus_api_key or not replica_id:
        # Return mock data if Tavus not configured
        return {
            "conversation_id": f"mock_{uuid.uuid4().hex[:8]}",
            "conversation_url": None,
            "status": "not_configured",
            "message": "Tavus not configured. Using audio-only mode.",
        }

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "replica_id": replica_id,
                "conversation_name": f"Mykare Call {request.session_id}",
                "conversational_context": (
                    "You are Aria, a healthcare front-desk assistant for Mykare Health Clinic. "
                    "Be warm, professional, and helpful."
                ),
                "custom_greeting": "Hello! I'm Aria from Mykare Health. How can I assist you today?",
                "properties": {
                    "max_call_duration": 3600,
                    "enable_recording": False,
                },
            }

            async with session.post(
                "https://tavusapi.com/v2/conversations",
                json=payload,
                headers={
                    "x-api-key": tavus_api_key,
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "conversation_id": data.get("conversation_id"),
                        "conversation_url": data.get("conversation_url"),
                        "status": "created",
                    }
                else:
                    text = await resp.text()
                    logger.error(f"Tavus error {resp.status}: {text}")
                    return {"status": "error", "message": text}

    except Exception as e:
        logger.error(f"Tavus session error: {e}")
        return {"status": "error", "message": str(e)}


@app.delete("/api/tavus/session/{conversation_id}")
async def end_tavus_session(conversation_id: str):
    """End a Tavus conversation session."""
    tavus_api_key = os.getenv("TAVUS_API_KEY")
    if not tavus_api_key:
        return {"status": "ok"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"https://tavusapi.com/v2/conversations/{conversation_id}",
                headers={"x-api-key": tavus_api_key},
            ) as resp:
                return {"status": "ended" if resp.status in [200, 204] else "error"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─────────────────────────────────────────────
# Appointments REST API
# ─────────────────────────────────────────────
@app.get("/api/slots")
async def get_slots(date: Optional[str] = None):
    """Get available appointment slots."""
    slots = await db.fetch_available_slots(date)
    return {"slots": slots}


@app.get("/api/appointments/{phone_number}")
async def get_appointments(phone_number: str):
    """Get all appointments for a phone number."""
    appointments = await db.retrieve_appointments(phone_number)
    return {"appointments": appointments}


@app.post("/api/appointments")
async def create_appointment(data: AppointmentCreate):
    """Book an appointment via REST API."""
    result = await db.book_appointment(
        phone_number=data.phone_number,
        patient_name=data.patient_name,
        date=data.date,
        time=data.time,
        doctor=data.doctor,
        department=data.department,
        notes=data.notes,
    )
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: int, phone_number: str):
    """Cancel an appointment."""
    result = await db.cancel_appointment(appointment_id, phone_number)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.patch("/api/appointments/{appointment_id}")
async def update_appointment(appointment_id: int, phone_number: str, data: ModifyAppointment):
    """Modify an appointment."""
    result = await db.modify_appointment(appointment_id, phone_number, data.new_date, data.new_time)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ─────────────────────────────────────────────
# Call Sessions
# ─────────────────────────────────────────────
@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get call session summary."""
    session = await db.get_call_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "service": "Mykare Voice AI"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
