from __future__ import annotations

import sys
import types

import httpx
import pytest

from app.core.config import Settings
from app.services.sf_client import SFClient, SFClientCredentials, SFClientError, build_ssl_verify


def test_build_ssl_verify_uses_truststore_when_available(mocker) -> None:
    fake_context = object()
    fake_truststore = types.SimpleNamespace(SSLContext=mocker.Mock(return_value=fake_context))

    mocker.patch.dict(sys.modules, {"truststore": fake_truststore})

    assert build_ssl_verify() is fake_context
    fake_truststore.SSLContext.assert_called_once()


def test_sf_client_call_passes_verify_to_httpx_client(mocker) -> None:
    fake_verify = object()
    mocker.patch("app.services.sf_client.build_ssl_verify", return_value=fake_verify)

    response = mocker.Mock()
    response.json.return_value = {"apiResultCode": "A1000"}
    client = mocker.MagicMock()
    client.__enter__.return_value.post.return_value = response
    client_factory = mocker.patch("app.services.sf_client.httpx.Client", return_value=client)

    sf_client = SFClient(
        Settings(),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
    )
    result = sf_client.call("PING", {"hello": "world"})

    assert result == {"apiResultCode": "A1000"}
    assert client_factory.call_args.kwargs["verify"] is fake_verify


def test_sf_client_call_uses_provided_http_client(mocker) -> None:
    response = mocker.Mock()
    response.json.return_value = {"apiResultCode": "A1000"}
    provided_client = mocker.Mock()
    provided_client.post.return_value = response
    client_factory = mocker.patch("app.services.sf_client.httpx.Client")

    sf_client = SFClient(
        Settings(),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )
    result = sf_client.call("PING", {"hello": "world"})

    assert result == {"apiResultCode": "A1000"}
    provided_client.post.assert_called_once()
    client_factory.assert_not_called()


def test_extract_route_payload_supports_nested_msg_data() -> None:
    sf_client = SFClient(
        Settings(),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
    )

    route_resps, payload = sf_client.extract_route_payload(
        {
            "apiResultCode": "A1000",
            "apiResultData": (
                '{"success": true, "errorCode": "S0000", "errorMsg": null, '
                '"msgData": {"routeResps": [{"mailNo": "SF1", "routes": []}]}}'
            ),
        }
    )

    assert route_resps == [{"mailNo": "SF1", "routes": []}]
    assert payload["msgData"]["routeResps"][0]["mailNo"] == "SF1"


def test_sf_client_call_retries_timeout_then_succeeds(mocker) -> None:
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"apiResultCode": "A1000"}

    provided_client = mocker.Mock()
    provided_client.post.side_effect = [
        httpx.ReadTimeout("timeout"),
        response,
    ]

    sleep = mocker.patch("app.services.sf_client.time.sleep")
    mocker.patch("app.services.sf_client.random.uniform", return_value=0.0)

    sf_client = SFClient(
        Settings(
            sf_request_max_attempts=3,
            sf_request_retry_initial_delay_seconds=0.5,
            sf_request_retry_max_delay_seconds=2.0,
            sf_request_retry_jitter_ratio=0.3,
        ),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )

    result = sf_client.call("PING", {"hello": "world"})

    assert result == {"apiResultCode": "A1000"}
    assert provided_client.post.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_sf_client_call_retries_503_then_succeeds(mocker) -> None:
    request = httpx.Request("POST", "https://example.com")
    retryable_response = mocker.Mock()
    retryable_response.status_code = 503
    retryable_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Server Error",
        request=request,
        response=httpx.Response(503, request=request),
    )

    success_response = mocker.Mock()
    success_response.raise_for_status.return_value = None
    success_response.json.return_value = {"apiResultCode": "A1000"}

    provided_client = mocker.Mock()
    provided_client.post.side_effect = [retryable_response, success_response]

    sleep = mocker.patch("app.services.sf_client.time.sleep")
    mocker.patch("app.services.sf_client.random.uniform", return_value=0.0)

    sf_client = SFClient(
        Settings(),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )

    result = sf_client.call("PING", {"hello": "world"})

    assert result == {"apiResultCode": "A1000"}
    assert provided_client.post.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_sf_client_call_does_not_retry_404(mocker) -> None:
    request = httpx.Request("POST", "https://example.com")
    response = mocker.Mock()
    response.status_code = 404
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found",
        request=request,
        response=httpx.Response(404, request=request),
    )
    provided_client = mocker.Mock()
    provided_client.post.return_value = response

    sleep = mocker.patch("app.services.sf_client.time.sleep")

    sf_client = SFClient(
        Settings(),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )

    with pytest.raises(httpx.HTTPStatusError):
        sf_client.call("PING", {"hello": "world"})

    provided_client.post.assert_called_once()
    sleep.assert_not_called()


def test_sf_client_call_adds_jitter_to_retry_delay(mocker) -> None:
    provided_client = mocker.Mock()
    provided_client.post.side_effect = [
        httpx.ReadTimeout("timeout-1"),
        httpx.ReadTimeout("timeout-2"),
        mocker.Mock(
            raise_for_status=mocker.Mock(return_value=None),
            json=mocker.Mock(return_value={"apiResultCode": "A1000"}),
        ),
    ]

    sleep = mocker.patch("app.services.sf_client.time.sleep")
    mocker.patch("app.services.sf_client.random.uniform", side_effect=[0.1, 0.2])

    sf_client = SFClient(
        Settings(
            sf_request_max_attempts=3,
            sf_request_retry_initial_delay_seconds=0.5,
            sf_request_retry_max_delay_seconds=2.0,
            sf_request_retry_jitter_ratio=0.3,
        ),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )

    result = sf_client.call("PING", {"hello": "world"})

    assert result == {"apiResultCode": "A1000"}
    assert sleep.call_args_list[0].args == (0.6,)
    assert sleep.call_args_list[1].args == (1.2,)


def test_sf_client_call_raises_sf_client_error_after_retry_exhausted(mocker) -> None:
    provided_client = mocker.Mock()
    provided_client.post.side_effect = [
        httpx.ReadTimeout("timeout-1"),
        httpx.ReadTimeout("timeout-2"),
        httpx.ReadTimeout("timeout-3"),
    ]

    mocker.patch("app.services.sf_client.time.sleep")
    mocker.patch("app.services.sf_client.random.uniform", return_value=0.0)

    sf_client = SFClient(
        Settings(sf_request_max_attempts=3),
        SFClientCredentials(partner_id="partner", checkword="checkword", environment="sandbox"),
        http_client=provided_client,
    )

    with pytest.raises(SFClientError, match="attempts exhausted"):
        sf_client.call("PING", {"hello": "world"})
