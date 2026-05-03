"""
agent.py - LiveKit Voice AI Agent
Uses: Deepgram STT, Cartesia TTS, Gemini LLM, with full tool calling
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Annotated, Optional
from dotenv import load_dotenv

load_dotenv()

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, inference
from livekit.plugins import deepgram, cartesia, silero
from livekit.agents import function_tool, RunContext

import database as db

logger = logging.getLogger("mykare-agent")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────
# Session state tracked per call
# ─────────────────────────────────────────────
class CallState:
    def __init__(self):
        self.phone_number: Optional[str] = None
        self.patient_name: Optional[str] = None
        self.identified: bool = False
        self.start_time: datetime = datetime.now()
        self.tool_calls: list[dict] = []
        self.appointments_this_call: list[dict] = []
        self.conversation_history: list[str] = []
        self.session_id: str = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def log_tool(self, name: str, result: str):
        self.tool_calls.append({
            "tool": name,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })


# ─────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────
@function_tool
async def identify_user(
    context: RunContext,
    phone_number: Annotated[str, "Patient's 10-digit phone number"],
    name: Annotated[Optional[str], "Patient's name if provided"] = None,
) -> str:
    """Identify the user by their phone number. Always call this first before any appointment action."""
    state: CallState = context.userdata

    # Clean phone number
    cleaned = "".join(filter(str.isdigit, phone_number))
    if len(cleaned) < 10:
        return "Invalid phone number. Please provide a valid 10-digit phone number."

    state.phone_number = cleaned
    if name:
        state.patient_name = name
    state.identified = True

    user = await db.get_or_create_user(cleaned, name)
    state.log_tool("identify_user", f"User identified: {cleaned}")

    if user.get("name"):
        return f"Welcome back, {user['name']}! I've identified you with phone number {cleaned}. How can I help you today?"
    else:
        return f"I've registered your phone number {cleaned}. Could you please tell me your name?"


@function_tool
async def fetch_slots(
    context: RunContext,
    date: Annotated[Optional[str], "Specific date in YYYY-MM-DD format, or leave empty for all available"] = None,
) -> str:
    """Fetch available appointment slots. Call this when patient wants to book or check availability."""
    state: CallState = context.userdata
    state.log_tool("fetch_slots", f"Fetching slots for {date or 'next 3 days'}")

    slots = await db.fetch_available_slots(date)

    if not slots:
        return "No available slots found for the requested date. Please try a different date."

    result = "Here are the available appointment slots:\n"
    for slot in slots:
        times = ", ".join(slot["available_times"][:4])
        result += f"\n📅 {slot['day']} {slot['date']}: {times}"

    return result


@function_tool
async def book_appointment(
    context: RunContext,
    date: Annotated[str, "Appointment date in YYYY-MM-DD format"],
    time: Annotated[str, "Appointment time e.g. '10:00 AM'"],
    doctor: Annotated[str, "Doctor name, default 'Dr. General'"] = "Dr. General",
    department: Annotated[str, "Department e.g. General, Cardiology"] = "General",
    notes: Annotated[str, "Any special notes"] = "",
) -> str:
    """Book an appointment for the identified user."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "I need to verify your identity first. Please provide your phone number."

    patient_name = state.patient_name or "Patient"
    result = await db.book_appointment(
        phone_number=state.phone_number,
        patient_name=patient_name,
        date=date,
        time=time,
        doctor=doctor,
        department=department,
        notes=notes,
    )

    if result["success"]:
        appt = result["appointment"]
        state.appointments_this_call.append(appt)
        state.log_tool("book_appointment", f"Booked: {date} {time}")
        return f"✅ Appointment confirmed! {result['message']} Your appointment ID is #{appt['id']}."
    else:
        state.log_tool("book_appointment", f"Failed: {result['error']}")
        return f"Sorry, I couldn't book that slot. {result['error']} Would you like to choose a different time?"


@function_tool
async def retrieve_appointments(
    context: RunContext,
) -> str:
    """Retrieve all upcoming appointments for the current user."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please provide your phone number first so I can look up your appointments."

    appointments = await db.retrieve_appointments(state.phone_number)
    state.log_tool("retrieve_appointments", f"Found {len(appointments)} appointments")

    if not appointments:
        return "You have no upcoming appointments. Would you like to book one?"

    result = f"You have {len(appointments)} appointment(s):\n"
    for appt in appointments:
        result += f"\n🗓 ID #{appt['id']}: {appt['date']} at {appt['time']} with {appt['doctor']} ({appt['department']})"
    return result


@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: Annotated[int, "The appointment ID to cancel"],
) -> str:
    """Cancel a specific appointment by its ID."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please verify your identity first."

    result = await db.cancel_appointment(appointment_id, state.phone_number)
    state.log_tool("cancel_appointment", f"Cancel ID #{appointment_id}: {result['success']}")

    if result["success"]:
        return f"✅ {result['message']} Is there anything else I can help you with?"
    else:
        return f"I couldn't cancel that appointment. {result['error']}"


@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: Annotated[int, "The appointment ID to modify"],
    new_date: Annotated[Optional[str], "New date in YYYY-MM-DD format"] = None,
    new_time: Annotated[Optional[str], "New time e.g. '02:00 PM'"] = None,
) -> str:
    """Modify the date or time of an existing appointment."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please verify your identity first."

    result = await db.modify_appointment(appointment_id, state.phone_number, new_date, new_time)
    state.log_tool("modify_appointment", f"Modify #{appointment_id}: {result['success']}")

    if result["success"]:
        return f"✅ {result['message']} Is there anything else I can help you with?"
    else:
        return f"I couldn't update that appointment. {result['error']}"


@function_tool
async def end_conversation(
    context: RunContext,
    summary: Annotated[str, "A brief summary of what was accomplished in this call"],
) -> str:
    """End the conversation and generate a call summary. Call this when patient says goodbye or conversation is complete."""
    state: CallState = context.userdata

    duration = int((datetime.now() - state.start_time).total_seconds())

    session_data = {
        "session_id": state.session_id,
        "phone_number": state.phone_number,
        "patient_name": state.patient_name,
        "summary": summary,
        "appointments_booked": state.appointments_this_call,
        "user_preferences": {},
        "duration_seconds": duration,
    }

    await db.save_call_session(session_data)
    state.log_tool("end_conversation", "Session saved")

    return (
        f"Thank you for calling Mykare Health! {summary} "
        "Have a great day and stay healthy! Goodbye! 👋"
    )


# ─────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are Aria, a warm and professional AI voice assistant for Mykare Health Clinic. 
Your role is to help patients book, manage, and cancel appointments efficiently and compassionately.

## Your Personality
- Warm, professional, empathetic healthcare assistant
- Speak naturally and conversationally — this is a voice call
- Be concise — patients are listening, not reading
- Always confirm important details (date, time, name)

## Conversation Flow
1. Greet the patient warmly
2. Ask for their phone number early (use identify_user tool)
3. Ask for their name if not given
4. Understand their intent (book/view/cancel/modify appointment)
5. Use appropriate tools to fulfill the request
6. Confirm actions clearly
7. Ask if there's anything else needed
8. Call end_conversation when done

## Important Rules
- ALWAYS call identify_user before any appointment action
- ALWAYS call fetch_slots before booking to check availability
- ALWAYS confirm date and time with the patient before booking
- Use natural date formats when speaking (e.g. "Monday, June 10th at 10 AM")
- Keep responses under 3 sentences for voice clarity
- If user says bye/goodbye/thank you — call end_conversation

## Tool Usage
- identify_user: First thing, get phone number
- fetch_slots: When patient wants to book or check times  
- book_appointment: After confirming slot with patient
- retrieve_appointments: When patient asks about existing bookings
- cancel_appointment: When patient wants to cancel
- modify_appointment: When patient wants to reschedule
- end_conversation: When call is complete

Today's date is: """ + datetime.now().strftime("%A, %B %d, %Y")


class MykareFrontDeskAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            tools=[
                identify_user,
                fetch_slots,
                book_appointment,
                retrieve_appointments,
                cancel_appointment,
                modify_appointment,
                end_conversation,
            ],
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet the patient warmly. Introduce yourself as Aria from Mykare Health. Ask how you can help them today."
        )


# ─────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────
async def entrypoint(ctx: agents.JobContext):
    await db.init_db()
    state = CallState()

    logger.info(f"[Agent] Starting session {state.session_id} in room {ctx.room.name}")

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-2",
            language="en-US",
            smart_format=True,
        ),
        llm=inference.LLM(
            model="google/gemini-2.5-flash",
             extra_kwargs={
                "max_completion_tokens": 1000,
                "temperature": 0.7,
            },
        ),
        tts=cartesia.TTS(
            model="sonic-english",
        ),
        vad=silero.VAD.load(),
        userdata=state,
    )

    await session.start(
        room=ctx.room,
        agent=MykareFrontDeskAgent(),
        room_input_options=RoomInputOptions(),
    )

    await ctx.connect()
    logger.info(f"[Agent] Connected to room {ctx.room.name}")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint)
    )
