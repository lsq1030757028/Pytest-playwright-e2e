from test_workflow.memory_contracts import (
    MemoryAclPort,
    MemoryAuditPort,
    MemoryMaintenancePort,
    MemoryQueryPort,
    MemoryRevisionPort,
    MemoryStatePort,
)
from tests.memory_contract_fixtures import make_store


def test_reference_adapter_implements_all_vendor_neutral_ports() -> None:
    store = make_store()

    assert isinstance(store, MemoryRevisionPort)
    assert isinstance(store, MemoryStatePort)
    assert isinstance(store, MemoryAclPort)
    assert isinstance(store, MemoryQueryPort)
    assert isinstance(store, MemoryAuditPort)
    assert isinstance(store, MemoryMaintenancePort)


def test_port_module_contains_no_vendor_specific_contract_types() -> None:
    import inspect

    from test_workflow.memory_contracts import ports

    source = inspect.getsource(ports).lower()
    for vendor in ("postgres", "redis", "sqlite", "mongodb", "pinecone", "milvus"):
        assert vendor not in source
