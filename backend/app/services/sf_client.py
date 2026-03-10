from __future__ import annotations

import json
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
    def __init__(self, settings: Settings, credentials: SFClientCredentials) -> None:
        self.settings = settings
        self.credentials = credentials

    def call(self, service_code: str, msg_data: dict[str, Any]) -> dict[str, Any]:
        timestamp = str(int(time.time()))
        msg_data_str = json.dumps(msg_data, ensure_ascii=False)
        payload = {
            "partnerID": self.credentials.partner_id,
            "requestID": uuid4().hex,
            "serviceCode": service_code,
            "timestamp": timestamp,
            "msgDigest": build_msg_digest(msg_data_str, timestamp, self.credentials.checkword),
            "msgData": msg_data_str,
        }
        endpoint = SF_ENDPOINTS[self.credentials.environment]
        with httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            verify=build_ssl_verify(),
        ) as client:
            response = client.post(endpoint, data=payload)
            response.raise_for_status()
            return response.json()

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
