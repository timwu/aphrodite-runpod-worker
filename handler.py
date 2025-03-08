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
        cmd = ["aphrodite", "run"]

        model_file = os.environ.get("MODEL_FILE")
        if model_file:
            cmd.extend(["--model", model_file])

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

        cmd.extend(["--gpu-memory-utilization", "0.95"])

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print(f"Started aphrodite with PID: {process.pid}")

        start_time = time.time()
        timeout = 600  # 10 minutes in seconds
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:2424/v1/completions")
                if response.status_code == 200:
                    print("aphrodite is ready.")
                    break
                else:
                    print(f"aphrodite not ready yet. Status code: {response.status_code}")
            except requests.exceptions.ConnectionError:
                print("aphrodite not ready yet. Connection refused.")
            except json.JSONDecodeError:
                print("aphrodite not ready yet. Invalid JSON response.")
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
