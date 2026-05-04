"""
database.py - SQLite database layer using aiosqlite
"""
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

DB_PATH = os.getenv("DATABASE_PATH", "./mykare.db")


async def init_db():
    """Initialize the SQLite database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phone_number TEXT NOT NULL,
                patient_name TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                doctor TEXT DEFAULT 'Dr. General',
                department TEXT DEFAULT 'General',
                status TEXT DEFAULT 'confirmed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS call_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                phone_number TEXT,
                patient_name TEXT,
                room_name TEXT,
                summary TEXT,
                appointments_booked TEXT,
                user_preferences TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                duration_seconds INTEGER
            )
        """)

        await db.commit()
    print(f"[DB] Database initialized at {DB_PATH}")


async def get_or_create_user(phone_number: str, name: Optional[str] = None) -> dict:
    """Get existing user or create new one."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE phone_number = ?", (phone_number,)
        ) as cursor:
            user = await cursor.fetchone()

        if user:
            if name and user["name"] != name:
                await db.execute(
                    "UPDATE users SET name = ?, updated_at = ? WHERE phone_number = ?",
                    (name, datetime.now().isoformat(), phone_number),
                )
                await db.commit()
            return dict(user)
        else:
            await db.execute(
                "INSERT INTO users (phone_number, name) VALUES (?, ?)",
                (phone_number, name),
            )
            await db.commit()
            async with db.execute(
                "SELECT * FROM users WHERE phone_number = ?", (phone_number,)
            ) as cursor:
                user = await cursor.fetchone()
            return dict(user)


async def fetch_available_slots(date: Optional[str] = None) -> list[dict]:
    """Return hardcoded available appointment slots."""
    from datetime import datetime, timedelta

    today = datetime.now()
    slots = []

    # Generate slots for next 7 days
    for day_offset in range(0, 7):
        slot_date = today + timedelta(days=day_offset)
        date_str = slot_date.strftime("%Y-%m-%d")

        # Check which slots are already booked
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT time FROM appointments WHERE date = ? AND status != 'cancelled'",
                (date_str,),
            ) as cursor:
                booked_times = {row["time"] async for row in cursor}

        # Available time slots
        all_times = [
            "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
            "11:00 AM", "11:30 AM", "02:00 PM", "02:30 PM",
            "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM",
        ]

        available_times = [t for t in all_times if t not in booked_times]

        if available_times:
            slots.append({
                "date": date_str,
                "day": slot_date.strftime("%A"),
                "available_times": available_times[:6],  # Show max 6 per day
            })

    if date:
        slots = [s for s in slots if s["date"] == date]

    return slots[:3]  # Return max 3 days


async def book_appointment(
    phone_number: str,
    patient_name: str,
    date: str,
    time: str,
    doctor: str = "Dr. General",
    department: str = "General",
    notes: str = "",
) -> dict:
    """Book an appointment, preventing double-booking."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Check for double booking
        async with db.execute(
            "SELECT id FROM appointments WHERE date = ? AND time = ? AND status != 'cancelled'",
            (date, time),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            return {"success": False, "error": f"Slot {time} on {date} is already booked."}

        # Get or create user
        user = await get_or_create_user(phone_number, patient_name)

        await db.execute(
            """INSERT INTO appointments 
               (user_id, phone_number, patient_name, date, time, doctor, department, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
            (user["id"], phone_number, patient_name, date, time, doctor, department, notes),
        )
        await db.commit()

        async with db.execute(
            "SELECT * FROM appointments WHERE phone_number = ? ORDER BY id DESC LIMIT 1",
            (phone_number,),
        ) as cursor:
            appt = await cursor.fetchone()

        return {
            "success": True,
            "appointment": dict(appt),
            "message": f"Appointment confirmed for {patient_name} on {date} at {time} with {doctor}.",
        }


async def retrieve_appointments(phone_number: str) -> list[dict]:
    """Retrieve all appointments for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM appointments 
               WHERE phone_number = ? AND status != 'cancelled'
               ORDER BY date ASC, time ASC""",
            (phone_number,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def cancel_appointment(appointment_id: int, phone_number: str) -> dict:
    """Cancel an appointment by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM appointments WHERE id = ? AND phone_number = ?",
            (appointment_id, phone_number),
        ) as cursor:
            appt = await cursor.fetchone()

        if not appt:
            return {"success": False, "error": "Appointment not found or not owned by this user."}

        await db.execute(
            "UPDATE appointments SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), appointment_id),
        )
        await db.commit()
        return {"success": True, "message": f"Appointment #{appointment_id} cancelled successfully."}


async def modify_appointment(
    appointment_id: int,
    phone_number: str,
    new_date: Optional[str] = None,
    new_time: Optional[str] = None,
) -> dict:
    """Modify an existing appointment."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM appointments WHERE id = ? AND phone_number = ? AND status != 'cancelled'",
            (appointment_id, phone_number),
        ) as cursor:
            appt = await cursor.fetchone()

        if not appt:
            return {"success": False, "error": "Appointment not found."}

        target_date = new_date or appt["date"]
        target_time = new_time or appt["time"]

        # Check double booking for new slot
        async with db.execute(
            """SELECT id FROM appointments 
               WHERE date = ? AND time = ? AND status != 'cancelled' AND id != ?""",
            (target_date, target_time, appointment_id),
        ) as cursor:
            conflict = await cursor.fetchone()

        if conflict:
            return {"success": False, "error": f"Slot {target_time} on {target_date} is already booked."}

        await db.execute(
            "UPDATE appointments SET date = ?, time = ?, updated_at = ? WHERE id = ?",
            (target_date, target_time, datetime.now().isoformat(), appointment_id),
        )
        await db.commit()
        return {
            "success": True,
            "message": f"Appointment #{appointment_id} updated to {target_date} at {target_time}.",
        }


async def save_call_session(session_data: dict) -> dict:
    """Save a completed call session summary."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO call_sessions 
               (session_id, phone_number, patient_name, room_name, summary, 
                appointments_booked, user_preferences, ended_at, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_data.get("session_id"),
                session_data.get("phone_number"),
                session_data.get("patient_name"),
                session_data.get("room_name"),
                session_data.get("summary"),
                str(session_data.get("appointments_booked", [])),
                str(session_data.get("user_preferences", {})),
                datetime.now().isoformat(),
                session_data.get("duration_seconds", 0),
            ),
        )
        await db.commit()

    # Generate PDF summary
    pdf_path = generate_call_summary_pdf(session_data)
    
    return {"success": True, "pdf_path": pdf_path}


def generate_call_summary_pdf(session_data: dict) -> str:
    """Generate a PDF summary of the call."""
    session_id = session_data.get("session_id")
    filename = f"summary_{session_id}.pdf"
    pdf_dir = os.path.join(os.path.dirname(DB_PATH), "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    filepath = os.path.join(pdf_dir, filename)

    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "Mykare Health Call Summary")

    # Patient Info
    c.setFont("Helvetica", 12)
    y = height - 130
    c.drawString(100, y, f"Patient Name: {session_data.get('patient_name', 'N/A')}")
    y -= 20
    c.drawString(100, y, f"Phone Number: {session_data.get('phone_number', 'N/A')}")
    y -= 20
    c.drawString(100, y, f"Session ID: {session_id}")
    y -= 20
    c.drawString(100, y, f"Call Duration: {session_data.get('duration_seconds', 0)} seconds")
    y -= 40

    # Summary
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y, "Call Summary:")
    y -= 20
    c.setFont("Helvetica", 12)
    summary = session_data.get("summary", "")
    # Wrap text
    lines = []
    words = summary.split()
    line = ""
    for word in words:
        if c.stringWidth(line + word, "Helvetica", 12) < 400:
            line += word + " "
        else:
            lines.append(line)
            line = word + " "
    lines.append(line)
    for line in lines:
        c.drawString(100, y, line.strip())
        y -= 15
        if y < 100:
            c.showPage()
            y = height - 100

    # Appointments Booked
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, y, "Appointments Booked:")
    y -= 20
    c.setFont("Helvetica", 12)
    appointments = session_data.get("appointments_booked", [])
    if appointments:
        for appt in appointments:
            c.drawString(100, y, f"- {appt.get('date')} at {appt.get('time')} with {appt.get('doctor')}")
            y -= 15
    else:
        c.drawString(100, y, "None")

    c.save()
    return filepath


async def get_call_session(session_id: str) -> Optional[dict]:
    """Get a call session by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM call_sessions WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None
