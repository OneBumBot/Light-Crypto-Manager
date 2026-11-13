# Финальная архитектура

Основной demo использует compose.yaml + compose.control.yaml + compose.stage9.yaml + compose.stage16.yaml и приватный network.json. Исследовательские compose.research.yaml/compose.shadow.yaml не входят в обязательный старт. Explicit subnet решает исчерпание Docker auto pool без удаления старых сетей. Dashboard и broker публикуются только на loopback.

Единый CLI scripts.stage16_demo переиспользует Stage9 provisioning/probes, исходные Device Agents, control protocol и Compose. Stage16 добавляет lifecycle/evidence checks; provider/telemetry/Policy FSM не переписывались. Новых SQL migrations нет, head 0011_policy_throughput.

Исходники схем для редактирования/экспорта:

- [Общая система](diagrams/stage16/01-system.mmd).
- [Telemetry](diagrams/stage16/02-telemetry.mmd).
- [PREPARE/ACTIVATE/ACK](diagrams/stage16/03-control.mmd).
- [Effective confirmation](diagrams/stage16/04-effective.mmd).
- [Policy DRY_RUN](diagrams/stage16/05-policy.mmd).
- [Shadow isolation](diagrams/stage16/06-shadow.mmd).
- [State и recovery](diagrams/stage16/07-state.mmd).

Shadow на схемах — optional отдельная исследовательская архитектура; его наличие не означает активацию в основном demo. Ни на одной схеме нет разрешённого автоматического ML/Policy→ACTIVATE канала.
