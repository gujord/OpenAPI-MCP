# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Tests for retry logic in fastmcp_server module."""

import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
from openapi_mcp.fastmcp_server import (
    retry_with_backoff,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    RETRYABLE_STATUS_CODES,
)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_connect_error(self):
        """Test retry on ConnectError."""
        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(failing_then_success, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry on TimeoutException."""
        call_count = 0

        async def timeout_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Request timed out")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(timeout_then_success, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test exception raised when max retries exhausted."""

        async def always_failing():
            raise httpx.ConnectError("Connection failed")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await retry_with_backoff(always_failing, max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self):
        """Test no retry on non-retryable exception."""
        call_count = 0

        async def value_error_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await retry_with_backoff(value_error_func, max_retries=3)

        assert call_count == 1  # Only called once, no retries

    @pytest.mark.asyncio
    async def test_retry_on_retryable_status_codes(self):
        """Test retry on retryable HTTP status codes."""
        call_count = 0

        # Test each retryable status code
        for status_code in [429, 500, 502, 503, 504]:
            call_count = 0

            async def retryable_status():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    response = Mock()
                    response.status_code = status_code
                    response.headers = {}
                    raise httpx.HTTPStatusError(
                        f"HTTP {status_code}", request=Mock(), response=response
                    )
                return "success"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await retry_with_backoff(retryable_status, max_retries=3, base_delay=0.01)

            assert result == "success"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_status_code(self):
        """Test no retry on non-retryable status codes like 400, 401, 404."""
        for status_code in [400, 401, 403, 404, 405]:
            call_count = 0

            async def non_retryable_status():
                nonlocal call_count
                call_count += 1
                response = Mock()
                response.status_code = status_code
                response.headers = {}
                raise httpx.HTTPStatusError(
                    f"HTTP {status_code}", request=Mock(), response=response
                )

            with pytest.raises(httpx.HTTPStatusError):
                await retry_with_backoff(non_retryable_status, max_retries=3, base_delay=0.01)

            assert call_count == 1  # Only one attempt, no retries

    @pytest.mark.asyncio
    async def test_retry_after_header_respected(self):
        """Test that Retry-After header is respected."""
        call_count = 0
        sleep_durations = []

        async def mock_sleep(duration):
            sleep_durations.append(duration)

        async def rate_limited_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = Mock()
                response.status_code = 429
                response.headers = {"Retry-After": "5"}
                raise httpx.HTTPStatusError(
                    "HTTP 429", request=Mock(), response=response
                )
            return "success"

        with patch("asyncio.sleep", side_effect=mock_sleep):
            result = await retry_with_backoff(rate_limited_then_success, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert len(sleep_durations) == 1
        assert sleep_durations[0] == 5.0  # Respects Retry-After header

    @pytest.mark.asyncio
    async def test_logging_on_retry(self):
        """Test that retries are logged when logger provided."""
        logger = Mock()
        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection failed")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(
                failing_then_success, max_retries=3, base_delay=0.01, logger=logger
            )

        assert result == "success"
        assert logger.warning.called

    @pytest.mark.asyncio
    async def test_logging_on_exhaustion(self):
        """Test that exhaustion is logged when logger provided."""
        logger = Mock()

        async def always_failing():
            raise httpx.ConnectError("Connection failed")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.ConnectError):
                await retry_with_backoff(always_failing, max_retries=1, base_delay=0.01, logger=logger)

        assert logger.error.called


class TestRetryConstants:
    """Tests for retry constants."""

    def test_default_max_retries(self):
        """Test default max retries value."""
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_base_delay(self):
        """Test default base delay value."""
        assert DEFAULT_RETRY_BASE_DELAY == 1.0

    def test_default_max_delay(self):
        """Test default max delay value."""
        assert DEFAULT_RETRY_MAX_DELAY == 30.0

    def test_retryable_status_codes(self):
        """Test retryable status codes set."""
        assert 408 in RETRYABLE_STATUS_CODES  # Request Timeout
        assert 429 in RETRYABLE_STATUS_CODES  # Too Many Requests
        assert 500 in RETRYABLE_STATUS_CODES  # Internal Server Error
        assert 502 in RETRYABLE_STATUS_CODES  # Bad Gateway
        assert 503 in RETRYABLE_STATUS_CODES  # Service Unavailable
        assert 504 in RETRYABLE_STATUS_CODES  # Gateway Timeout

        # Non-retryable codes should not be in the set
        assert 400 not in RETRYABLE_STATUS_CODES
        assert 401 not in RETRYABLE_STATUS_CODES
        assert 404 not in RETRYABLE_STATUS_CODES
