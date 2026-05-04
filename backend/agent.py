"""
agent.py - LiveKit Voice AI Agent
Uses: Deepgram STT, Cartesia TTS, Gemini LLM, with full tool calling
"""
import asyncio
import json
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
# Session state tracked per call
# ─────────────────────────────────────────────
class CallState:
    def __init__(self):
        self.phone_number: Optional[str] = None
        self.patient_name: Optional[str] = None
        self.identified: bool = False
        self.stage: str = "IDENTIFICATION"
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
    
    """ 
    Args :
        - phone_number: The patient's phone number, extracted from their speech. Should be 10 digits.
        - name: Optional patient name if they provided it during identification. This can be used to personalize the conversation immediately, but we will also look up the name in the database if possible.
    """
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

    if user.get("name") or name:
        state.patient_name = user.get("name") or name
        state.stage = "INTENT"
        return f"Welcome back, {state.patient_name}! I've identified you with phone number {cleaned}. How can I help you today?"
    else:
        state.stage = "IDENTIFICATION"
        return f"I've registered your phone number {cleaned}. Could you please tell me your name?"


@function_tool
async def fetch_slots(
    context: RunContext,
    date: Annotated[Optional[str], "Specific date in YYYY-MM-DD format, or leave empty for all available"] = None,
) -> str:
    """Fetch available appointment slots. Call this when patient wants to book or check availability."""
    """
    Args:
    - date: Optional specific date to check availability for. If not provided, fetch all upcoming slots.
    """
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
    
    """
    Args:
    - date: The date for the appointment in YYYY-MM-DD format.
    - time: The time for the appointment, e.g. "10:00 AM".
    - doctor: The doctor the patient wants to see. Default is "Dr. General".
    - department: The department for the appointment, e.g. "General", "Cardiology". Default is "General".
    - notes: Any special notes or requests from the patient.
    """
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
    """
    Args:
        None
    """
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
    """
    Args:
    - appointment_id: The unique ID of the appointment to cancel. You can find this ID by first calling retrieve_appointments.
    """
    
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
    
    """
    Args:
        - appointment_id: The unique ID of the appointment to modify. You can find this ID by first calling retrieve_appointments.
        - new_date: The new date for the appointment in YYYY-MM-DD format. Leave empty if you only want to change the time.
        - new_time: The new time for the appointment, e.g. "02:00 PM". Leave empty if you only want to change the date.
    """
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
    """
    Args:
        - summary: A brief summary of the call, including any appointments booked, cancelled, or modified. This will be saved to the database along with the call details for future reference.
    """
    
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
- Speak naturally and conversationally — this is a voice call
- Be concise — patients are listening, not reading
- Always confirm important details (date, time, name)

## Conversation Flow
1. Greet the patient warmly
2. Ask for their phone number early and as soon as user provides a phone number, IMMEDIATELY  (call identify_user tool)
3. Do not respond without calling it
4. Ask for their name if not given
5. Understand their intent (book/view/cancel/modify appointment)
6. Use appropriate tools to fulfill the request
7. Confirm actions clearly
8. Ask if there's anything else needed
9. Call end_conversation user is finished and says bye/goodbye/thank you

## Important Rules
- ALWAYS call identify_user before any appointment action
- If the user provides a phone number, IMMEDIATELY call identify_user
- ALWAYS call fetch_slots before booking to check availability
- ALWAYS confirm date and time with the patient before booking
- Use natural date formats when speaking (e.g. "Monday, June 10th at 10 AM")
- The user's phone number and name are stored after identification
- NEVER ask for phone number again if already identified
- ALWAYS use their name naturally in conversation
- You already know who they are — act like it
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
    async def on_user_message(self, message: str):
        state: CallState = self.session.userdata

        def extract_phone(text: str) -> Optional[str]:
            digits = re.findall(r"\d", text)
            if len(digits) >= 10:
                cleaned = "".join(digits)
                return cleaned[-10:]
            return None

        # 🚨 HARD GATE: If not identified → force identify_user
        if not state.identified:
            phone = extract_phone(message)
            if phone:
                await self.session.generate_reply(
                    user_input=message,
                    instructions=(
                        "The user has provided a phone number in their message. "
                        "Call identify_user with that phone number and do not proceed to any other task."
                    ),
                    tools=["identify_user"],
                )
                return

            await self.session.generate_reply(
                user_input=message,
                instructions=(
                    "Politely ask the user for their 10-digit phone number. "
                    "Do NOT proceed to any other task until identity is confirmed."
                ),
                tools=["identify_user"],
            )
            return

        # After identification → move to intent stage
        if state.stage == "IDENTIFICATION":
            state.stage = "INTENT"

            await self.session.generate_reply(
                instructions=(
                    f"The user is identified as {state.patient_name or 'the patient'} "
                    f"with phone number {state.phone_number}. "
                    "Now ask what they would like to do: "
                    "book, view, cancel, or reschedule an appointment."
                )
            )
            return

        # Normal flow after that
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
