#!/bin/bash
cd "$(dirname "$0")/backend"
echo "🚀 Starting VideoGPT Pro Backend on http://localhost:8000"
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
