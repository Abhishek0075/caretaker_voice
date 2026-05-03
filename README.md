# 🩺 Mykare Voice AI — Full Stack Voice Agent

A production-grade AI voice receptionist for healthcare appointment booking.
Built with LiveKit Agents, Deepgram STT, Cartesia TTS, Tavus Avatar, Gemini LLM, Python, Next.js, and SQLite.

---

## Architecture

```
Browser (Next.js)
    │  WebRTC (LiveKit)
    ▼
LiveKit Cloud ──────── LiveKit Agent (Python)
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
            Deepgram    Gemini      Cartesia
              (STT)      (LLM)      (TTS)
                            │
                       SQLite DB
                            │
                       FastAPI REST
                            │
                    Tavus Avatar (optional)
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- LiveKit Cloud account (free tier works): https://cloud.livekit.io
- Deepgram API key: https://deepgram.com
- Cartesia API key: https://cartesia.ai
- Google AI API key (Gemini): https://aistudio.google.com
- Tavus API key (optional): https://tavus.io

---

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Backend .env

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091

GOOGLE_API_KEY=your_gemini_key

TAVUS_API_KEY=your_tavus_key          # optional
TAVUS_REPLICA_ID=your_replica_id      # optional

FRONTEND_URL=http://localhost:3000
```

### Run Backend Services

**Terminal 1 — FastAPI REST server:**
```bash
cd backend
python server.py
# Runs on http://localhost:8000
```

**Terminal 2 — LiveKit Voice Agent:**
```bash
cd backend
python agent.py dev
# Connects to LiveKit and waits for participants
```

---

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy and fill environment variables
cp .env.local.example .env.local
# Edit .env.local:
# NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
# NEXT_PUBLIC_LIVEKIT_URL=wss://your-project.livekit.cloud

# Run development server
npm run dev
# Opens on http://localhost:3000
```

---

## Tool Calling Flow

| Tool | Trigger | Description |
|------|---------|-------------|
| `identify_user` | Always first | Phone number lookup/registration |
| `fetch_slots` | Before booking | Returns available time slots |
| `book_appointment` | After slot selection | Creates DB record, prevents double-booking |
| `retrieve_appointments` | "Show my appointments" | Lists patient's upcoming bookings |
| `cancel_appointment` | "Cancel appointment" | Marks as cancelled by ID |
| `modify_appointment` | "Reschedule" | Updates date/time |
| `end_conversation` | "Goodbye" | Generates summary, saves session |

---

## Database Schema

```sql
users (id, phone_number, name, created_at)
appointments (id, user_id, phone_number, patient_name, date, time, doctor, department, status, notes, created_at)
call_sessions (id, session_id, phone_number, patient_name, summary, appointments_booked, started_at, ended_at, duration_seconds)
```

---

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/token` | Generate LiveKit token |
| POST | `/api/tavus/session` | Create Tavus avatar session |
| GET | `/api/slots` | Get available appointment slots |
| GET | `/api/appointments/{phone}` | Get patient appointments |
| POST | `/api/appointments` | Book appointment |
| DELETE | `/api/appointments/{id}` | Cancel appointment |
| PATCH | `/api/appointments/{id}` | Modify appointment |
| GET | `/api/sessions/{id}` | Get call session summary |
| GET | `/api/health` | Health check |

---

## Deployment

### Backend (Railway / Render / EC2)
```bash
# Set environment variables in your platform
# Run both services:
uvicorn server:app --host 0.0.0.0 --port 8000
python agent.py start  # production mode
```

### Frontend (Vercel)
```bash
cd frontend
vercel deploy
# Set NEXT_PUBLIC_BACKEND_URL and NEXT_PUBLIC_LIVEKIT_URL in Vercel dashboard
```

---

## Cost Per Call Estimate

| Service | Model | Approx Cost |
|---------|-------|-------------|
| LiveKit | Realtime | ~$0.002/min |
| Deepgram | Nova-2 | ~$0.006/min |
| Cartesia | Sonic | ~$0.005/min |
| Gemini | 2.0 Flash | ~$0.001/min |
| **Total** | | **~$0.014/min** |

Average 5-minute call ≈ **$0.07**

---

## Tech Stack

- **STT**: Deepgram Nova-2 (< 300ms latency)
- **LLM**: Google Gemini 2.0 Flash
- **TTS**: Cartesia Sonic-English
- **Voice Agent**: LiveKit Agents Python SDK
- **Avatar**: Tavus Conversational Video Interface
- **Backend**: FastAPI + aiosqlite
- **Frontend**: Next.js 15 + TypeScript
- **Database**: SQLite (via aiosqlite)
