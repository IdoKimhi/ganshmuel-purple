import subprocess
import os
import threading
import time

CI_SCRIPT_PATH = "/app_root/ci.sh"
CI_COMPOSE_FILE = "docker-compose-ci-server.yml"

def execute_self_update():

    print("CI_SELF_UPDATE: Initiating asynchronous self-update sequence...")
    
    time.sleep(1) 
    
    try:
        command = f"cd /app_root && nohup bash {CI_SCRIPT_PATH} > /proc/1/fd/1 2>&1 &"
        
        os.system(command)
        
        print("CI_SELF_UPDATE: Full CI setup script launched and detached. Server will restart shortly.")
        
    except Exception as e:

        print(f"CI_SELF_UPDATE_FATAL_ERROR: Failed to launch detached CI script: {e}")

def trigger_update_async():
    """Starts the execute_self_update function in a new thread."""
    threading.Thread(target=execute_self_update).start()