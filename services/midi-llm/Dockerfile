FROM python:3.14-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/cache/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# The PyPI torch wheel is the CUDA build. 2.14.1 publishes a cp314 CPU wheel.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu \
    && python -c "import sys, torch; assert sys.version_info[:2] == (3, 14); assert torch.version.cuda is None"

RUN pip install --no-cache-dir \
        fastapi==0.146.0 \
        uvicorn==0.54.0 \
        transformers \
        huggingface-hub \
        mido \
        "anticipation @ git+https://github.com/jthickstun/anticipation.git@af37397922665a0fb8d474d7988b0f3755a38d45" \
    && python -c "import torch; assert torch.version.cuda is None" \
    && python -c "import io, mido; buf = io.BytesIO(); mido.MidiFile().save(file=buf); assert buf.getvalue().startswith(b'MThd')" \
    && python -c "from anticipation.convert import events_to_midi"

# Upstream license file stays in the image. Do not edit this clone.
RUN git clone --depth 1 https://github.com/slSeanWU/MIDI-LLM.git /opt/MIDI-LLM

WORKDIR /app
COPY src /app/src
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["python", "-m", "midi_llm_http"]
