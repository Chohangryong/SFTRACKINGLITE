from __future__ import annotations

import sys
import types

from app.core.config import Settings
from app.services.sf_client import SFClient, SFClientCredentials, build_ssl_verify


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
