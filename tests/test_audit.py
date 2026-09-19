from app.services.audit import AuditService


def test_audit_event_is_persisted(tmp_path):
    database = tmp_path / "audit.db"

    audit = AuditService(str(database))

    event_id = audit.record(
        migration_id="migration-001",
        event_type="mapping_decision",
        entity_id="E001",
        details={
            "source_field": "Employee No",
            "target_field": "employee_id",
            "confidence": 0.95,
            "decision": "auto_approve",
            "reason": "High-confidence synonym match.",
        },
    )

    assert event_id > 0

    events = audit.list_events("migration-001")

    assert len(events) == 1
    assert events[0]["event_type"] == "mapping_decision"
    assert events[0]["entity_id"] == "E001"
    assert events[0]["details"]["decision"] == "auto_approve"