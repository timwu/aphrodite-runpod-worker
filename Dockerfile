FROM nvidia/cuda:12.1.1-base-ubuntu22.04
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

