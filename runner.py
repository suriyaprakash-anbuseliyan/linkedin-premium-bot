"""
runner.py
─────────
This script is the master controller for the bot.
It runs the main `bot.py`. If `bot.py` exits with an error code (crashes),
it will automatically launch `fallback_bot.py` to notify users.
If `fallback_bot.py` crashes, it restarts it.
"""

import subprocess
import time
import sys
import os
import signal

# Global reference to the current child process
current_process = None

def signal_handler(sig, frame):
    """Handle graceful shutdown when the user hits Ctrl+C on the runner."""
    print("\n[Runner] Shutting down gracefully...")
    if current_process:
        current_process.terminate()
        current_process.wait()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def run_main_bot():
    global current_process
    print("[Runner] Starting MAIN bot...")
    current_process = subprocess.Popen([sys.executable, "bot.py"])
    return current_process.wait()

def run_fallback_bot():
    global current_process
    print("[Runner] Starting FALLBACK bot...")
    current_process = subprocess.Popen([sys.executable, "fallback_bot.py"])
    return current_process.wait()

def main():
    while True:
        # 1. Run main bot
        exit_code = run_main_bot()
        
        # If exited normally (0), assume intentional shutdown and break.
        if exit_code == 0:
            print("[Runner] Main bot exited normally. Stopping runner.")
            break
            
        print(f"[Runner] Main bot crashed with exit code {exit_code}. Switching to Fallback Bot!")
        
        # 2. Run fallback bot indefinitely. If it crashes, loop and restart fallback bot.
        while True:
            fb_exit_code = run_fallback_bot()
            print(f"[Runner] Fallback bot exited with code {fb_exit_code}. Restarting fallback bot in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
