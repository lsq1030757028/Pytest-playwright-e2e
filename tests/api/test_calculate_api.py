import httpx
import pytest


@pytest.mark.api
@pytest.mark.parametrize(
    ("free_minutes", "close_seconds", "expected"),
    [
        (2, 119, True),
        (2, 120, True),
        (2, 121, False),
        (0, 0, False),
    ],
)
def test_free_time_boundary(
    demo_server_url: str,
    free_minutes: int,
    close_seconds: int,
    expected: bool,
) -> None:
    response = httpx.post(
        f"{demo_server_url}/api/calculate",
        json={"free_minutes": free_minutes, "close_seconds": close_seconds},
        timeout=2,
    )

    response.raise_for_status()
    assert response.json()["free_time_applied"] is expected
