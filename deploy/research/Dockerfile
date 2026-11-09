FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tcpdump tshark libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && setcap cap_net_raw=ep /usr/bin/tcpdump \
    && useradd --system --uid 10001 --create-home lightcrypto
WORKDIR /app
COPY requirements/publisher.txt /tmp/publisher.txt
RUN pip install --no-cache-dir -r /tmp/publisher.txt
COPY src/*.py /app/src/
COPY src/web/ascon/*.py src/web/ascon/LICENSE /app/src/web/ascon/
COPY src/research_stand /app/src/research_stand
USER 10001:10001
CMD ["python", "-m", "src.research_stand.service"]
