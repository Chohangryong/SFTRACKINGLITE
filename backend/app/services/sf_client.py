from __future__ import annotations

import json
import logging
import random
import ssl
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.utils.signature import build_msg_digest

SF_ENDPOINTS = {
    "sandbox": "https://sfapi-sbox.sf-express.com/std/service",
    "production": "https://sfapi.sf-express.com/std/service",
}
RETRYABLE_STATUS_CODES = {408, 429}
logger = logging.getLogger(__name__)


class SFClientError(Exception):
    pass


@dataclass
class SFClientCredentials:
    partner_id: str
    checkword: str
    environment: str


def build_ssl_verify() -> ssl.SSLContext | bool:
    try:
        import truststore
    except ImportError:
        return True
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class SFClient:
    def __init__(
        self,
        settings: Settings,
        credentials: SFClientCredentials,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.credentials = credentials
        self.http_client = http_client

    @staticmethod
    def create_http_client(settings: Settings) -> httpx.Client:
        return httpx.Client(
            timeout=settings.request_timeout_seconds,
            verify=build_ssl_verify(),
        )

    def call(self, service_code: str, msg_data: dict[str, Any]) -> dict[str, Any]:
        msg_data_str = json.dumps(msg_data, ensure_ascii=False)
        endpoint = SF_ENDPOINTS[self.credentials.environment]
        max_attempts = max(1, self.settings.sf_request_max_attempts)

        for attempt in range(1, max_attempts + 1):
            timestamp = str(int(time.time()))
            payload = {
                "partnerID": self.credentials.partner_id,
                "requestID": uuid4().hex,
                "serviceCode": service_code,
                "timestamp": timestamp,
                "msgDigest": build_msg_digest(msg_data_str, timestamp, self.credentials.checkword),
                "msgData": msg_data_str,
            }
            try:
                response = self._post(endpoint, payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as error:
                if not self._is_retryable_status(error.response.status_code) or attempt >= max_attempts:
                    if self._is_retryable_status(error.response.status_code):
                        raise self._build_retry_exhausted_error(error, attempt, max_attempts) from error
                    raise
                self._wait_before_retry(error, attempt, max_attempts)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as error:
                if attempt >= max_attempts:
                    raise self._build_retry_exhausted_error(error, attempt, max_attempts) from error
                self._wait_before_retry(error, attempt, max_attempts)

        raise SFClientError("SF request attempts exhausted without a terminal error")

    def search_routes(self, tracking_numbers: list[str], language: str | None = None) -> dict[str, Any]:
        msg_data = {
            "trackingType": "1",
            "trackingNumber": tracking_numbers,
            "methodType": "1",
            "language": language or self.settings.default_language,
        }
        return self.call("EXP_RECE_SEARCH_ROUTES", msg_data)

    def extract_route_payload(self, response: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        api_result_code = response.get("apiResultCode")
        if api_result_code != "A1000":
            raise SFClientError(response.get("apiErrorMsg") or f"Platform error: {api_result_code}")

        raw_result_data = response.get("apiResultData")
        if not raw_result_data:
            raise SFClientError("Missing apiResultData")
        try:
            payload = json.loads(raw_result_data)
        except json.JSONDecodeError as error:
            raise SFClientError(f"Invalid apiResultData JSON: {error}") from error

        error_code = payload.get("errorCode")
        if error_code != "S0000":
            raise SFClientError(payload.get("errorMsg") or f"Business error: {error_code}")

        msg_data = payload.get("msgData") if isinstance(payload.get("msgData"), dict) else None
        route_resps = payload.get("routeResps")
        if route_resps is None and msg_data is not None:
            route_resps = msg_data.get("routeResps")
        if route_resps is None:
            raise SFClientError("Missing routeResps")
        return route_resps, payload

    def _post(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        if self.http_client is not None:
            return self.http_client.post(endpoint, data=payload)

        with self.create_http_client(self.settings) as client:
            return client.post(endpoint, data=payload)

    def _wait_before_retry(self, error: Exception, attempt: int, max_attempts: int) -> None:
        delay = self._compute_retry_delay(attempt)
        logger.warning(
            "SF request retrying attempt=%s/%s delay=%.2fs error_type=%s error=%s",
            attempt,
            max_attempts,
            delay,
            type(error).__name__,
            error,
        )
        time.sleep(delay)

    def _compute_retry_delay(self, attempt: int) -> float:
        base_delay = min(
            self.settings.sf_request_retry_initial_delay_seconds * (2 ** (attempt - 1)),
            self.settings.sf_request_retry_max_delay_seconds,
        )
        jitter = 0.0
        if self.settings.sf_request_retry_jitter_ratio > 0:
            jitter = random.uniform(0, base_delay * self.settings.sf_request_retry_jitter_ratio)
        return base_delay + jitter

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES or status_code >= 500

    def _build_retry_exhausted_error(
        self,
        error: httpx.RequestError | httpx.HTTPStatusError,
        attempt: int,
        max_attempts: int,
    ) -> SFClientError:
        detail = type(error).__name__
        if isinstance(error, httpx.HTTPStatusError):
            detail = f"{detail} status={error.response.status_code}"
        return SFClientError(
            f"SF request attempts exhausted after {attempt}/{max_attempts} attempts ({detail}): {error}"
        )
