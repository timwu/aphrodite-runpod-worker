import subprocess
import os
import time
from cryptography.fernet import Fernet
import requests
import json
import runpod

if "KEY" in os.environ:
    f = Fernet(os.environ.get("KEY"))
else:
    f = None

def start_aphrodite_engine():
    """Starts the aphrodite-engine binary as a background process."""
    try:
        if not os.environ.get("MODEL_FILE"):
            raise Exception("MODEL_FILE environment variable not set.")
        if not os.path.exists(os.environ.get("MODEL_FILE")):
            raise Exception(f"MODEL_FILE {os.environ.get('MODEL_FILE')} does not exist.")

        cmd = ["aphrodite", "run", os.environ.get("MODEL_FILE")]
        
        context_size = os.environ.get("CONTEXT_SIZE")
        if context_size and context_size.isdigit():
            cmd.extend(["--max-model-len", context_size])

        n_gpu = os.environ.get("N_GPU")
        if n_gpu and n_gpu.isdigit():
            n_gpu = int(n_gpu)
            if n_gpu > 1:
                if n_gpu % 2 == 0:
                    cmd.extend(["--tensor-parallel-size", str(n_gpu)])
                else:
                    cmd.extend(["--pipeline-parallel-size", str(n_gpu)])

        cmd.extend(["--gpu-memory-utilization", "0.95", "--host", "0.0.0.0", "--port", "2424"])

        process = subprocess.Popen(cmd, stdout=None, stderr=None)
        
        print(f"Started aphrodite with PID: {process.pid}")

        start_time = time.time()
        timeout = 600  # 10 minutes in seconds
        message_delay = 40
        while time.time() - start_time < timeout:
            
            if process.poll() is not None:
                raise Exception(f"aphrodite process exited with code {process.poll()}")

            message = None

            try:
                response = requests.get("http://localhost:2424/v1/completions")
                if response.status_code == 200:
                    print("aphrodite is ready.")
                    break
                else:
                    message = f"aphrodite not ready yet. Status code: {response.status_code}"
            except requests.exceptions.ConnectionError:
                message = "aphrodite not ready yet. Connection refused."
            except json.JSONDecodeError:
                message = "aphrodite not ready yet. Invalid JSON response."

            # Reduce print frequency, once every 10 seconds
            if message:
                if message_delay == 0:
                    print(message)
                    message_delay = 40
                else:
                    message_delay -= 1
            
            time.sleep(0.25)
        else:
            print("Timeout: aphrodite did not become ready within 10 minutes.")

            
    except FileNotFoundError:
        print("Error: aphrodite binary not found.")
    except Exception as e:
        print(f"Error starting aphrodite: {e}")

def handler(event):
    inp = event["input"]
    should_encrypt = False
    if "e_prompt" in inp:
        inp["prompt"] = f.decrypt(inp["e_prompt"].encode()).decode()
        del inp["e_prompt"]
        should_encrypt = True

    response = requests.post("http://localhost:2424/v1/completions", json=inp)

    if should_encrypt:
        for choice in response["choices"]:
            choice["e_text"] = f.encrypt(choice["text"].encode()).decode()
            del choice["text"]

    return response


if __name__ == "__main__":
    start_aphrodite_engine()
    runpod.serverless.start({"handler": handler})
