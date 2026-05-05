"""
Tests for the /api/v1/health endpoint.
"""
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import create_app
from app.dependencies import get_session


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200_when_all_ok(self):
        """Health endpoint should return 200 with status=ok when DB and Redis are healthy."""
        app = create_app()

        # Mock the DB session dependency
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()

        with patch("app.api.v1.health.aioredis") as mock_aioredis:
            mock_aioredis.from_url = MagicMock(return_value=mock_redis)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["redis"] == "ok"
        assert body["version"] == "1.0.0"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_health_returns_503_when_db_fails(self):
        """Health endpoint should return 503 when database check fails."""
        app = create_app()

        # Mock the DB session that raises an error
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("Connection refused"))

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        # Mock Redis (healthy)
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()

        with patch("app.api.v1.health.aioredis") as mock_aioredis:
            mock_aioredis.from_url = MagicMock(return_value=mock_redis)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/health")

        assert response.status_code == 503
        body = response.json()
        assert body["detail"]["status"] == "degraded"
        assert "error" in body["detail"]["checks"]["database"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_health_returns_503_when_redis_fails(self):
        """Health endpoint should return 503 when Redis check fails."""
        app = create_app()

        # Mock the DB session (healthy)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        # Mock Redis that raises an error
        with patch("app.api.v1.health.aioredis") as mock_aioredis:
            mock_aioredis.from_url = MagicMock(
                side_effect=Exception("Redis connection failed")
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/health")

        assert response.status_code == 503
        body = response.json()
        assert body["detail"]["status"] == "degraded"
        assert "error" in body["detail"]["checks"]["redis"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_health_returns_503_when_both_fail(self):
        """Health endpoint should return 503 when both DB and Redis fail."""
        app = create_app()

        # Mock failing DB
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB down"))

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        # Mock failing Redis
        with patch("app.api.v1.health.aioredis") as mock_aioredis:
            mock_aioredis.from_url = MagicMock(
                side_effect=Exception("Redis down")
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/health")

        assert response.status_code == 503
        body = response.json()
        assert "error" in body["detail"]["checks"]["database"]
        assert "error" in body["detail"]["checks"]["redis"]

        app.dependency_overrides.clear()
