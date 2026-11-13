# Capture image has no crypto library, MQTT client or key mount.
FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS capture
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tcpdump libcap2-bin && rm -rf /var/lib/apt/lists/* && setcap cap_net_raw=ep /usr/bin/tcpdump
WORKDIR /app
COPY src/shadow_ids /app/src/shadow_ids
CMD ["python", "-m", "src.shadow_ids.capture"]
