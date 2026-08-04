from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .serialization import load_document


class ResponseBehavior(BaseModel):
    status: int = 200
    json_body: Any = Field(default_factory=dict, alias="json")
    headers: dict[str, str] = Field(default_factory=dict)
    delay_ms: int = Field(default=0, ge=0, le=120_000)

    model_config = {"populate_by_name": True}


class RouteBehavior(BaseModel):
    id: str
    method: str
    path: str
    response: ResponseBehavior


class VirtualServiceBehavior(BaseModel):
    schema_version: str = "1.0"
    service: str
    routes: list[RouteBehavior]


def load_behavior(path: str | Path) -> VirtualServiceBehavior:
    return VirtualServiceBehavior.model_validate(load_document(path))


def create_virtual_service(behavior: VirtualServiceBehavior) -> FastAPI:
    app = FastAPI(title=f"Virtual service: {behavior.service}")
    calls: list[dict[str, Any]] = []

    @app.get("/__mock__/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": behavior.service}

    @app.get("/__mock__/calls")
    def call_log() -> list[dict[str, Any]]:
        return calls

    def handler_factory(route: RouteBehavior):
        async def handler(request: Request) -> JSONResponse:
            body = await request.body()
            calls.append(
                {
                    "route_id": route.id,
                    "method": request.method,
                    "path": request.url.path,
                    "body": body.decode("utf-8", errors="replace"),
                }
            )
            if route.response.delay_ms:
                await asyncio.sleep(route.response.delay_ms / 1000)
            return JSONResponse(
                status_code=route.response.status,
                content=route.response.json_body,
                headers=route.response.headers,
            )

        return handler

    for route in behavior.routes:
        app.add_api_route(
            route.path,
            handler_factory(route),
            methods=[route.method.upper()],
            name=route.id,
        )
    return app
