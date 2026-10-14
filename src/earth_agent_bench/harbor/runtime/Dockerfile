FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl bash libhdf4-alt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY agent-requirements.txt /tmp/agent-requirements.txt
RUN pip install --no-cache-dir -r /tmp/agent-requirements.txt

# Instrument the access libraries so the verifier sees the calls the agent made.
COPY eab_instrument.py /opt/eab/eab_instrument.py
RUN printf 'import sys; sys.path.insert(0, "/opt/eab"); import eab_instrument' > /usr/local/lib/python3.12/site-packages/eab_instrument.pth

WORKDIR /app
RUN mkdir -p /app/output /home/user/input /home/user/output
