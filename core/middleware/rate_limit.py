from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_rpm: int = 60):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.route_overrides: dict[str, int] = {}
        self.clients: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - 60

        self.clients[client_ip] = [t for t in self.clients[client_ip] if t > window]

        rpm = self.route_overrides.get(request.url.path, self.default_rpm)
        if len(self.clients[client_ip]) >= rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded ({rpm} req/min)."},
            )

        self.clients[client_ip].append(now)
        return await call_next(request)
