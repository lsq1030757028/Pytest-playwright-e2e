from fastapi.testclient import TestClient

from test_workflow.virtual_service import (
    ResponseBehavior,
    RouteBehavior,
    VirtualServiceBehavior,
    create_virtual_service,
)


def test_virtual_service_returns_configured_response_and_records_call() -> None:
    behavior = VirtualServiceBehavior(
        service="telemetry_service",
        routes=[
            RouteBehavior(
                id="track",
                method="POST",
                path="/track",
                response=ResponseBehavior(
                    status=202,
                    json={"accepted": True, "event_id": "evt-1"},
                ),
            )
        ],
    )
    client = TestClient(create_virtual_service(behavior))

    response = client.post("/track", json={"name": "todo.created"})

    assert response.status_code == 202
    assert response.json()["accepted"] is True
    calls = client.get("/__mock__/calls").json()
    assert calls[0]["route_id"] == "track"
