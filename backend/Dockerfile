# Healthcare Secure API
FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Skip heavy Whisper in image by default — mount or install later for voice.
# Skip faster-whisper (heavy). openai SDK is required for Groq/OpenAI STT+LLM clients.
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy \
    python-dotenv python-multipart psycopg2-binary cryptography fpdf2 tzdata httpx \
    openai qrcode[pil]

COPY app ./app

ENV APP_ENV=production
ENV REQUIRE_CLINIC_USERS=true
ENV WHISPER_PRELOAD=false
# Voice: set WHISPER_PROVIDER=groq|openai and WHISPER_API_KEY at runtime (image has no faster-whisper).
# LLM: set LLM_PROVIDER=groq|openai and LLM_API_KEY (no Ollama in image).
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
