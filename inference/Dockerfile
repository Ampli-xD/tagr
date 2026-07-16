# Production RunPod serverless image (GPU).
# Local CPU development:
#   docker build --build-arg TARGET=dev -t tagr-inference:dev ./inference

ARG TARGET=runpod

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS base-gpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

FROM python:3.11-slim AS base-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

FROM base-gpu AS final-runpod
FROM base-cpu AS final-dev

FROM final-${TARGET} AS final
ARG TARGET

WORKDIR /workspace

COPY requirements.txt .
RUN if [ "$TARGET" = "runpod" ]; then \
      pip install --no-cache-dir -r requirements.txt; \
    else \
      pip install --no-cache-dir \
        fastapi==0.111.0 uvicorn==0.30.1 httpx==0.27.0 numpy==1.26.4 \
        opencv-python-headless insightface onnxruntime runpod==1.7.12; \
    fi

COPY core.py handler.py server.py main.py ./

ENV INFERENCE_DEVICE=gpu \
    INFERENCE_MODE=runpod \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PORT_HEALTH=8000 \
    HEALTH_CHECK_PATH=/ping

EXPOSE 8000

CMD ["python", "-u", "main.py"]
