"""
agent.py - LiveKit Voice AI Agent
Uses: Deepgram STT, Cartesia TTS, Gemini LLM, with full tool calling
"""
import logging
import os
import re
from datetime import datetime
from typing import Annotated, Optional
from dotenv import load_dotenv

load_dotenv()

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, inference, TurnHandlingOptions
from livekit.plugins import deepgram, cartesia, silero
from livekit.agents import function_tool, RunContext
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import database as db

logger = logging.getLogger("mykare-agent")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────
class CallState:
    def __init__(self):
        self.phone_number: Optional[str] = None
        self.patient_name: Optional[str] = None
        self.identified: bool = False
        self.start_time: datetime = datetime.now()
        self.tool_calls: list[dict] = []
        self.appointments_this_call: list[dict] = []
        self.session_id: str = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def log_tool(self, name: str, result: str):
        self.tool_calls.append({
            "tool": name,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })


def extract_phone(text: str) -> Optional[str]:
    """Extract a 10-digit phone number from speech text."""
    # First try to find a clean 10+ digit sequence
    matches = re.findall(r'\b\d[\d\s\-]{8,}\d\b', text)
    for m in matches:
        digits = re.sub(r'\D', '', m)
        if len(digits) >= 10:
            return digits[-10:]

    # Fallback: collect all digits
    digits = re.sub(r'\D', '', text)
    if len(digits) >= 10:
        return digits[-10:]

    return None


# ─────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────
@function_tool
async def identify_user(
    context: RunContext,
    phone_number: Annotated[str, "Patient's 10-digit phone number. Must be exactly 10 digits, never 'unknown'."],
    name: Annotated[Optional[str], "Patient's name if they provided it"] = None,
) -> str:
    """
    Identify the user by their phone number.
    ONLY call this when you have a real 10-digit number from the user.
    Never call with 'unknown', empty string, or a name instead of a number.
    """
    state: CallState = context.userdata

    # Reject placeholder values
    cleaned = re.sub(r'\D', '', phone_number)
    if len(cleaned) < 10 or phone_number.lower() in ("unknown", "none", "", "n/a"):
        return "I need a valid 10-digit phone number. Could you please say your number again?"

    cleaned = cleaned[-10:]
    state.phone_number = cleaned
    if name:
        state.patient_name = name
    state.identified = True

    user = await db.get_or_create_user(cleaned, name)
    state.log_tool("identify_user", f"Identified: {cleaned}")

    display_name = user.get("name") or name
    if display_name:
        state.patient_name = display_name
        return f"Got it! Welcome, {display_name}. How can I help you today?"
    else:
        return f"I've verified your number ending in {cleaned[-4:]}. Could you tell me your name?"


@function_tool
async def fetch_slots(
    context: RunContext,
    date: Annotated[Optional[str], "Specific date in YYYY-MM-DD format, or empty for next 3 days"] = None,
) -> str:
    """Fetch available appointment slots."""
    state: CallState = context.userdata
    state.log_tool("fetch_slots", f"date={date or 'next 3 days'}")

    slots = await db.fetch_available_slots(date)
    if not slots:
        return "No available slots for that date. Please try a different date."

    result = "Here are the available slots:\n"
    for slot in slots:
        times = ", ".join(slot["available_times"][:4])
        result += f"\n{slot['day']} {slot['date']}: {times}"
    return result


@function_tool
async def book_appointment(
    context: RunContext,
    date: Annotated[str, "Date in YYYY-MM-DD format"],
    time: Annotated[str, "Time e.g. '10:00 AM'"],
    doctor: Annotated[str, "Doctor name"] = "Dr. General",
    department: Annotated[str, "Department"] = "General",
    notes: Annotated[str, "Special notes"] = "",
) -> str:
    """Book an appointment for the identified patient."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "I need to verify your identity first. What is your phone number?"

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
        state.log_tool("book_appointment", f"Booked #{appt['id']}: {date} {time}")
        return f"Appointment confirmed for {date} at {time} with {doctor}. Your booking ID is #{appt['id']}."
    else:
        state.log_tool("book_appointment", f"Failed: {result['error']}")
        return f"Sorry, that slot isn't available. {result['error']} Would you like a different time?"


@function_tool
async def retrieve_appointments(context: RunContext) -> str:
    """Retrieve all upcoming appointments for the current user."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please provide your phone number first."

    appointments = await db.retrieve_appointments(state.phone_number)
    state.log_tool("retrieve_appointments", f"Found {len(appointments)}")

    if not appointments:
        return "You have no upcoming appointments. Would you like to book one?"

    result = f"You have {len(appointments)} appointment(s):\n"
    for appt in appointments:
        result += f"\nID #{appt['id']}: {appt['date']} at {appt['time']} with {appt['doctor']}"
    return result


@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: Annotated[int, "The appointment ID to cancel"],
) -> str:
    """Cancel a specific appointment by ID."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please verify your identity first."

    result = await db.cancel_appointment(appointment_id, state.phone_number)
    state.log_tool("cancel_appointment", f"Cancel #{appointment_id}: {result['success']}")

    return f"Appointment #{appointment_id} cancelled successfully." if result["success"] else f"Couldn't cancel: {result['error']}"


@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: Annotated[int, "Appointment ID to modify"],
    new_date: Annotated[Optional[str], "New date YYYY-MM-DD"] = None,
    new_time: Annotated[Optional[str], "New time e.g. '02:00 PM'"] = None,
) -> str:
    """Modify the date or time of an existing appointment."""
    state: CallState = context.userdata

    if not state.identified or not state.phone_number:
        return "Please verify your identity first."

    result = await db.modify_appointment(appointment_id, state.phone_number, new_date, new_time)
    state.log_tool("modify_appointment", f"Modify #{appointment_id}: {result['success']}")

    return f"Appointment #{appointment_id} updated successfully." if result["success"] else f"Couldn't update: {result['error']}"


@function_tool
async def end_conversation(
    context: RunContext,
    summary: Annotated[str, "Brief summary of what was accomplished in this call"],
) -> str:
    """End the conversation. Call when patient says goodbye or is done."""
    state: CallState = context.userdata

    duration = int((datetime.now() - state.start_time).total_seconds())
    await db.save_call_session({
        "session_id": state.session_id,
        "phone_number": state.phone_number,
        "patient_name": state.patient_name,
        "summary": summary,
        "appointments_booked": state.appointments_this_call,
        "user_preferences": {},
        "duration_seconds": duration,
    })
    state.log_tool("end_conversation", "Session saved")
    return f"Thank you for calling Mykare Health! {summary} Have a great day, goodbye!"


# ─────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are Aria, a professional AI voice receptionist for Mykare Health Clinic.

## CRITICAL RULE — PHONE NUMBER FIRST
- You MUST collect the patient's phone number before doing ANYTHING else
- Do NOT call identify_user until the user has spoken at least 10 digits
- Do NOT pass "unknown", a name, or anything other than real digits to identify_user
- If the user gives their name before their number, say: "Thank you! And your phone number?"
- Only call identify_user once you have 10 real digits from the user's speech

## After identification
- Use the patient's name naturally in conversation
- Never ask for phone number again
- Help with: booking, viewing, cancelling, or modifying appointments
- Always fetch_slots before booking
- Confirm date and time with patient before calling book_appointment
- Call end_conversation when patient says goodbye or is done

## Voice style
- Keep replies under 2-3 sentences
- Speak naturally — this is a phone call
- Use natural date formats: "Monday the 5th at 10 AM"

Today is: {datetime.now().strftime("%A, %B %d, %Y")}"""


# ─────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────
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
            instructions=(
                "Greet the patient warmly as Aria from Mykare Health. "
                "Ask for their 10-digit phone number to get started. "
                "Do NOT call any tool yet."
            )
        )

    async def on_user_message(self, message: str):
        state: CallState = self.session.userdata

        # ── Gate: not yet identified ──────────────────────────────
        if not state.identified:
            phone = extract_phone(message)

            if phone:
                # We have a real number — force the LLM to call identify_user with it
                await self.session.generate_reply(
                    user_input=message,
                    instructions=(
                        f"The user's message contains the phone number {phone}. "
                        f"Call identify_user NOW with phone_number='{phone}'. "
                        "Do not say anything before calling the tool."
                    ),
                )
            else:
                # No number found — ask again
                await self.session.generate_reply(
                    user_input=message,
                    instructions=(
                        "The user has not provided a valid 10-digit phone number yet. "
                        "Politely ask them to say their phone number. "
                        "Do NOT call any tool."
                    ),
                )
            return

        # ── Normal flow after identification ─────────────────────
        await super().on_user_message(message)


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
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
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