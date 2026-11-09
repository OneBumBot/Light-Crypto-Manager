FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/publisher.txt requirements/receiver.txt /app/requirements/
COPY src/web/requirements.txt /app/requirements/web.txt
RUN pip install --no-cache-dir -r requirements/publisher.txt -r requirements/receiver.txt -r requirements/web.txt \
    && useradd --system --uid 10001 --create-home lightcrypto
COPY src/*.py /app/src/
COPY src/publisher/*.py /app/src/publisher/
COPY src/brocker/*.py /app/src/brocker/
COPY src/web/*.py /app/src/web/
COPY src/web/templates /app/src/web/templates
COPY src/web/static /app/src/web/static
COPY src/web/ascon/*.py src/web/ascon/LICENSE /app/src/web/ascon/
COPY scripts/seed_demo.py scripts/mqtt_smoke.py scripts/install_storage.py scripts/install_security.py scripts/mqtt_security_smoke.py /app/scripts/
USER 10001:10001
CMD ["python", "-m", "src.brocker.mqtt_brocker"]

FROM runtime AS tests
USER root
COPY requirements/dev.txt /app/requirements/dev.txt
RUN pip install --no-cache-dir -r requirements/dev.txt
COPY pyproject.toml /app/pyproject.toml
COPY tests/*.py /app/tests/
COPY scripts/live_web_smoke.py /app/scripts/live_web_smoke.py
COPY scripts/prepare_compose.py /app/scripts/prepare_compose.py
COPY deploy/compose.env.example /app/deploy/compose.env.example
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
