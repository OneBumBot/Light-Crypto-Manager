FROM golang:1.27.3-bookworm@sha256:dc0963f32053e4bc451d24d87e3892d42d01021b61f093e98eb95c0352bb84b0 AS kuz-builder
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off
WORKDIR /build/native/kuzprovider
COPY third_party/go-gostcrypto /build/third_party/go-gostcrypto
COPY native/kuzprovider /build/native/kuzprovider
RUN go build -trimpath -buildvcs=false -ldflags=-buildid= -o /out/lcm-kuz-mgm .

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/publisher.txt requirements/receiver.txt /app/requirements/
COPY src/web/requirements.txt /app/requirements/web.txt
RUN pip install --no-cache-dir -r requirements/publisher.txt -r requirements/receiver.txt -r requirements/web.txt \
    && useradd --system --uid 10001 --create-home lightcrypto
COPY --from=kuz-builder /out/lcm-kuz-mgm /usr/local/bin/lcm-kuz-mgm
COPY --from=kuz-builder /usr/local/go/LICENSE /usr/share/licenses/lcm-kuz-mgm/GO-LICENSE
COPY third_party/go-gostcrypto/LICENSE third_party/go-gostcrypto/PROVENANCE.json /usr/share/licenses/lcm-kuz-mgm/
COPY src/device_control /app/src/device_control
COPY src/policy /app/src/policy
COPY src/*.py /app/src/
COPY src/publisher/*.py /app/src/publisher/
COPY src/brocker/*.py /app/src/brocker/
COPY src/web/*.py /app/src/web/
COPY src/web/templates /app/src/web/templates
COPY src/web/static /app/src/web/static
COPY src/web/ascon/*.py src/web/ascon/LICENSE /app/src/web/ascon/
COPY scripts/install_control.py scripts/install_stage10.py scripts/install_stage11.py scripts/install_stage12.py /app/scripts/
COPY scripts/provision_registry.py scripts/seed_demo.py scripts/mqtt_smoke.py scripts/install_storage.py scripts/install_security.py scripts/mqtt_security_smoke.py /app/scripts/
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
USER 10001:10001
CMD ["python", "-m", "src.brocker.mqtt_brocker"]

FROM runtime AS ml
USER root
COPY requirements/ml-runtime.txt /app/requirements/ml-runtime.txt
RUN pip install --no-cache-dir -r requirements/ml-runtime.txt
COPY src/classifier/ml /app/src/classifier/ml
COPY scripts/install_ml_model.py scripts/export_ml_telemetry.py /app/scripts/
USER 10001:10001
CMD ["python", "-m", "src.classifier.ml.worker"]

FROM ml AS tests
USER root
COPY requirements/dev.txt /app/requirements/dev.txt
RUN pip install --no-cache-dir -r requirements/dev.txt
COPY pyproject.toml /app/pyproject.toml
COPY tests/*.py /app/tests/
COPY src/classifier/research /app/src/classifier/research
COPY src/research_stand /app/src/research_stand
COPY scripts/stand_state.py /app/scripts/stand_state.py
COPY scripts/crypto_benchmark.py scripts/control_mutations.py scripts/control_system_probe.py scripts/control_security_probe.py /app/scripts/
COPY scripts/check_malformed_mqtt_recovery.py scripts/stage9_probe.py scripts/stage9_mutations.py scripts/performance_probe.py scripts/performance_lab.py /app/scripts/
COPY scripts/live_web_smoke.py scripts/dual_database_probe.py scripts/ml_system_probe.py scripts/policy_system_probe.py /app/scripts/
COPY scripts/prepare_compose.py /app/scripts/prepare_compose.py
COPY deploy/compose.env.example /app/deploy/compose.env.example
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
