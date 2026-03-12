from __future__ import annotations

import json

import httpx


def test_upload_confirm_creates_no_tracking_row(client) -> None:
    response = client.post(
        "/api/uploads",
        files={"file": ("orders.csv", b"order_number\nORDER-1\n", "text/csv")},
    )
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]

    confirm = client.post(f"/api/uploads/{batch_id}/confirm", json={"mapping": {}})
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["success_rows"] == 1

    trackings = client.get("/api/trackings")
    assert trackings.status_code == 200
    items = trackings.json()["items"]
    assert items[0]["order_number"] == "ORDER-1"
    assert items[0]["current_status"] == "NO_TRACKING"


def test_upload_confirm_refreshes_tracking_with_mocked_sf(client, mocker) -> None:
    client.post(
        "/api/settings/api-keys",
        json={
            "label": "Sandbox",
            "environment": "sandbox",
            "partner_id": "PARTNER",
            "checkword": "CHECKWORD",
            "is_active": True,
        },
    )

    mocked_response = {
        "apiResultCode": "A1000",
        "apiResultData": json.dumps(
            {
                "errorCode": "S0000",
                "routeResps": [
                    {
                        "mailNo": "SF123",
                        "routes": [
                            {
                                "acceptTime": "2026-03-08 10:00:00",
                                "acceptAddress": "Seoul",
                                "opCode": "80",
                                "firstStatusCode": "80",
                                "secondaryStatusCode": "80",
                                "remark": "Delivered",
                            }
                        ],
                    }
                ],
            }
        ),
    }
    mocker.patch("app.services.sf_client.SFClient.search_routes", return_value=mocked_response)

    response = client.post(
        "/api/uploads",
        files={"file": ("orders.csv", b"order_number,tracking_number\nORDER-2,SF123\n", "text/csv")},
    )
    batch_id = response.json()["batch_id"]

    confirm = client.post(f"/api/uploads/{batch_id}/confirm", json={"mapping": {}})
    assert confirm.status_code == 200
    assert confirm.json()["refresh_summary"]["refreshed"] == 1

    detail = client.get("/api/trackings/SF123")
    assert detail.status_code == 200
    assert detail.json()["current_status"] == "DELIVERED"

    events = client.get("/api/trackings/SF123/events")
    assert events.status_code == 200
    assert len(events.json()) == 1


def test_upload_confirm_retries_sf_timeout_and_succeeds(client, mocker) -> None:
    client.post(
        "/api/settings/api-keys",
        json={
            "label": "Sandbox",
            "environment": "sandbox",
            "partner_id": "PARTNER",
            "checkword": "CHECKWORD",
            "is_active": True,
        },
    )

    success_response = mocker.Mock()
    success_response.raise_for_status.return_value = None
    success_response.json.return_value = {
        "apiResultCode": "A1000",
        "apiResultData": json.dumps(
            {
                "errorCode": "S0000",
                "routeResps": [
                    {
                        "mailNo": "SF123",
                        "routes": [
                            {
                                "acceptTime": "2026-03-08 10:00:00",
                                "acceptAddress": "Seoul",
                                "opCode": "80",
                                "firstStatusCode": "80",
                                "secondaryStatusCode": "80",
                                "remark": "Delivered",
                            }
                        ],
                    }
                ],
            }
        ),
    }

    http_client = mocker.Mock()
    http_client.post.side_effect = [httpx.ReadTimeout("timeout"), success_response]
    client_context = mocker.MagicMock()
    client_context.__enter__.return_value = http_client
    mocker.patch("app.services.sf_client.httpx.Client", return_value=client_context)
    mocker.patch("app.services.sf_client.random.uniform", return_value=0.0)
    mocker.patch("app.services.sf_client.time.sleep")

    response = client.post(
        "/api/uploads",
        files={"file": ("orders.csv", b"order_number,tracking_number\nORDER-2,SF123\n", "text/csv")},
    )
    batch_id = response.json()["batch_id"]

    confirm = client.post(f"/api/uploads/{batch_id}/confirm", json={"mapping": {}})
    assert confirm.status_code == 200
    assert confirm.json()["refresh_summary"]["refreshed"] == 1

    detail = client.get("/api/trackings/SF123")
    assert detail.status_code == 200
    assert detail.json()["current_status"] == "DELIVERED"


def test_upload_confirm_marks_query_unavailable_when_sf_returns_reason(client, mocker) -> None:
    client.post(
        "/api/settings/api-keys",
        json={
            "label": "Sandbox",
            "environment": "sandbox",
            "partner_id": "PARTNER",
            "checkword": "CHECKWORD",
            "is_active": True,
        },
    )

    mocked_response = {
        "apiResultCode": "A1000",
        "apiResultData": json.dumps(
            {
                "errorCode": "S0000",
                "routeResps": [
                    {
                        "mailNo": "SF20028",
                        "routes": [],
                        "reasonCode": "20028",
                        "reasonRemark": "月结卡号不匹配",
                    }
                ],
            }
        ),
    }
    mocker.patch("app.services.sf_client.SFClient.search_routes", return_value=mocked_response)

    response = client.post(
        "/api/uploads",
        files={"file": ("orders.csv", b"order_number,tracking_number\nORDER-4,SF20028\n", "text/csv")},
    )
    batch_id = response.json()["batch_id"]

    confirm = client.post(f"/api/uploads/{batch_id}/confirm", json={"mapping": {}})
    assert confirm.status_code == 200

    detail = client.get("/api/trackings/SF20028")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["current_status"] == "QUERY_UNAVAILABLE"
    assert payload["current_status_code"] == "20028"
    assert payload["current_status_detail"] == "月结卡号不匹配"
    assert payload["last_error_code"] == "20028"
    assert payload["last_error_message"] == "月结卡号不匹配"


def test_upload_confirm_ignores_duplicate_order_tracking_rows(client) -> None:
    response = client.post(
        "/api/uploads",
        files={
            "file": (
                "orders.csv",
                b"order_number,tracking_number\nORDER-3,SF999\nORDER-3,SF999\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]

    confirm = client.post(f"/api/uploads/{batch_id}/confirm", json={"mapping": {}})
    assert confirm.status_code == 200
    payload = confirm.json()
    assert payload["success_rows"] == 2
    assert payload["error_rows"] == 0
    assert payload["affected_tracking_numbers"] == ["SF999"]

    detail = client.get("/api/trackings/SF999")
    assert detail.status_code == 200
    assert len(detail.json()["linked_orders"]) == 1


def test_settings_and_export_endpoints(client) -> None:
    api_key = client.post(
        "/api/settings/api-keys",
        json={
            "label": "Normalized",
            "environment": " Production ",
            "partner_id": "PARTNER",
            "checkword": "CHECKWORD",
            "is_active": True,
        },
    )
    assert api_key.status_code == 200
    assert api_key.json()["environment"] == "production"

    polling = client.get("/api/settings/polling")
    assert polling.status_code == 200
    assert polling.json()["interval_hours"] == 2

    update = client.put(
        "/api/settings/polling",
        json={
            "enabled": True,
            "interval_hours": 4,
            "batch_size": 10,
            "delay_between_batches_seconds": 1,
            "max_retries": 3,
        },
    )
    assert update.status_code == 200
    assert update.json()["interval_hours"] == 4

    presets = client.get("/api/export/presets")
    assert presets.status_code == 200
    assert len(presets.json()) >= 2

    download = client.post("/api/export/download", json={"export_type": "summary", "file_format": "xlsx"})
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
