from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .relay_claims import ClaimControlError, RegistryRevisionConflict, parse_utc

INTEGRATION_ACTIVITY_SIGNALS = (
    "recent_pr_activity",
    "active_ci",
    "recent_main_activity",
)


def recover_stale_integration_lease(
    lease: Mapping[str, Any],
    *,
    expected_revision: int,
    now: datetime,
    activity: Mapping[str, bool],
) -> tuple[dict[str, Any], str | None, bool]:
    """Recover an expired integration lease only when no live activity protects it.

    Returns ``(updated_lease, recovered_work_item_id, protected)``. An unexpired
    or already-idle lease is returned unchanged. Expired leases remain ACTIVE
    when recent PR/main activity or active CI is observed, preventing a second
    integrator from starting while the first one may still be completing work.
    """

    if lease.get("schema_version") != 1:
        raise ClaimControlError("unsupported integration lease schema")
    if lease.get("revision") != expected_revision:
        raise RegistryRevisionConflict("integration lease revision changed")
    if now.tzinfo is None:
        raise ClaimControlError("now must include a timezone")

    status = lease.get("status")
    updated = deepcopy(dict(lease))
    if status == "IDLE":
        return updated, None, False
    if status != "ACTIVE":
        raise ClaimControlError("integration lease status must be IDLE or ACTIVE")

    expires_at = lease.get("expires_at")
    if not isinstance(expires_at, str):
        raise ClaimControlError("active integration lease needs expires_at")
    if parse_utc(expires_at) > now.astimezone(UTC):
        return updated, None, False

    if any(activity.get(signal, False) for signal in INTEGRATION_ACTIVITY_SIGNALS):
        return updated, None, True

    work_item_id = lease.get("work_item_id")
    if not isinstance(work_item_id, str) or not work_item_id:
        raise ClaimControlError("active integration lease needs work_item_id")

    updated.update(
        {
            "revision": int(lease["revision"]) + 1,
            "status": "IDLE",
            "integration_token": None,
            "work_item_id": None,
            "started_at": None,
            "expires_at": None,
        }
    )
    return updated, work_item_id, False
