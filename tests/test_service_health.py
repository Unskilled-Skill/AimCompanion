from core.service_health import ServiceHealthStore, ServiceStatus
from models.database import Database


def test_error_survives_store_reopen_until_resolved():
    database = Database(":memory:")
    try:
        store = ServiceHealthStore(database.conn)
        store.update(ServiceStatus(
            "definitions", "warning", "Using cached definitions",
            "Remote schema changed", "retry_definition_sync",
        ))
        reopened = ServiceHealthStore(database.conn)
        assert reopened.all()["definitions"].recovery_action == "retry_definition_sync"
        reopened.update(ServiceStatus("definitions", "ok", "Definitions ready", ""))
        assert store.all()["definitions"].state == "ok"
    finally:
        database.close()
