"""Explicit evidence provenance. A captured packet is not proof of IDS effectiveness."""


def statuses(source):
    provenance = source.get("provenance", {})
    return dict(
        engineering_validated=bool(source.get("schema_version")),
        laboratory_labels_validated=bool(provenance.get("independent_label_verification")),
        independent_external_validation_pending=True,
        real_attack_detection_unproven=True,
        real_packet_capture=provenance.get(
            "real_packet_capture", not source.get("synthetic", True)
        ),
        generated_test_clients=provenance.get("generated_test_clients", None),
        controlled_lab_scenarios=provenance.get("controlled_lab_scenarios", None),
        label_unit=source.get("label_unit", "undeclared"),
        label_evidence_level=source.get("label_evidence_level", "unreviewed"),
        independent_label_verification=bool(provenance.get("independent_label_verification")),
        external_validation_performed=False,
        attack_realism_scope=provenance.get("attack_realism_scope", "unreviewed"),
        known_shortcut_risks=provenance.get("known_shortcut_risks", ["not independently reviewed"]),
        scientific_quality_available=False,
    )
