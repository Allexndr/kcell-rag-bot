import subprocess
import time
import sys
import signal
import os

def signal_handler(sig, frame):
    print('Shutting down services...')
    if server_process:
        server_process.terminate()
    if bot_process:
        bot_process.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("🚀 Starting Kcell RAG System...")

# Start FastAPI Server
print("📡 Starting Web Server (Port 8000)...")
server_process = subprocess.Popen([sys.executable, "server.py"], cwd=os.getcwd())

# Start Telegram Bot
print("🤖 Starting Telegram Bot...")
bot_process = subprocess.Popen([sys.executable, "main.py"], cwd=os.getcwd())

print("✅ System execution started. Press Ctrl+C to stop.")

# Keep main thread alive
while True:
    time.sleep(1)
    if server_process.poll() is not None:
        print("❌ Server stopped unexpectedly.")
        break
    if bot_process.poll() is not None:
        print("❌ Bot stopped unexpectedly.")
        break
