#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"

trap 'kill $SERVER_PID $CLIENT_PID 2>/dev/null; exit' INT TERM EXIT

cd "$ROOT/server"
python3 -m uvicorn main:app --reload --port 8000 &
SERVER_PID=$!

cd "$ROOT/client"
npm run dev &
CLIENT_PID=$!

wait
