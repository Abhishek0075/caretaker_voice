#!/bin/bash
# start_backend.sh - Start all backend services

set -e

echo "🩺 Starting Mykare Voice AI Backend..."
echo ""

# Check .env exists
if [ ! -f .env ]; then
  echo "❌ .env file not found. Copy .env.example and fill in your API keys."
  exit 1
fi

# Activate venv if present
# if [ -d "venv" ]; then
#   source venv/bin/activate
#   echo "✅ Virtual environment activated"
# fi

# Start FastAPI in background
echo "🚀 Starting FastAPI server on port 8000..."
uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!
echo "   PID: $FASTAPI_PID"

sleep 2

# Start LiveKit agent
echo "🎙 Starting LiveKit Voice Agent..."
python agent.py dev &
AGENT_PID=$!
echo "   PID: $AGENT_PID"

echo ""
echo "✅ All services running!"
echo "   FastAPI: http://localhost:8000"
echo "   Agent:   Connected to LiveKit"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait and cleanup
trap "kill $FASTAPI_PID $AGENT_PID 2>/dev/null; echo 'Services stopped.'" EXIT
wait
