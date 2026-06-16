#!/bin/bash

# This script runs inside the ollama container to initialize the model
# It will be called automatically when the container starts

set -e

echo "[Ollama Init] Waiting for Ollama server to be ready..."

# Wait for Ollama API to be available
max_attempts=60
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "[Ollama Init] Ollama server is ready!"
        break
    fi
    
    echo "[Ollama Init] Attempt $attempt/$max_attempts - Ollama not ready yet, waiting..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "[Ollama Init] ERROR: Ollama server did not become ready in time"
    exit 1
fi

echo "[Ollama Init] Checking if neural-chat model is available..."

# Check if model already exists
if curl -s http://localhost:11434/api/tags | grep -q "neural-chat"; then
    echo "[Ollama Init] Model neural-chat is already available"
    exit 0
fi

echo "[Ollama Init] Pulling neural-chat model (this may take several minutes)..."
ollama pull neural-chat

if [ $? -eq 0 ]; then
    echo "[Ollama Init] Successfully pulled neural-chat model"
else
    echo "[Ollama Init] ERROR: Failed to pull neural-chat model"
    exit 1
fi

echo "[Ollama Init] Ollama initialization complete!"
