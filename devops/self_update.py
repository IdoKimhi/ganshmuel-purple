import subprocess
import os
import threading
import time

CI_SCRIPT_PATH = "../ci.sh"
CI_COMPOSE_FILE = "docker-compose-ci-server.yml"

def execute_self_update():

    print("CI_SELF_UPDATE: Initiating asynchronous self-update sequence...")
    

    time.sleep(1) 
    
    try:

        print("CI_SELF_UPDATE: Stopping current container to free port...")
        subprocess.run(
            ["docker", "compose", "-f", CI_COMPOSE_FILE, "down"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            check=False,
            capture_output=True,
            text=True
        )
        print("CI_SELF_UPDATE: Current container stopped. Launching new stack...")
        
        subprocess.Popen(
            ["bash", CI_SCRIPT_PATH],
            cwd="../",
            start_new_session=True, 
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        print("CI_SELF_UPDATE: Full CI setup script launched. Server will restart shortly.")
        
    except Exception as e:
        print(f"CI_SELF_UPDATE_FATAL_ERROR: Failed to execute CI script or Docker command: {e}")

def trigger_update_async():
    """Starts the execute_self_update function in a new thread."""
    threading.Thread(target=execute_self_update).start()