from __future__ import annotations

import json
from io import BytesIO

from openpyxl import load_workbook


def test_lite_analyze_dedupes_pairs_and_counts_missing_tracking(client) -> None:
    response = client.post(
        "/api/lite/analyze",
        files={
            "file": (
                "orders.csv",
                (
                    "Order Number,Tracking Number\n"
                    "ORDER-1,SF111\n"
                    "ORDER-1,SF111\n"
                    "ORDER-1,SF222\n"
                    ",SF333\n"
                    "ORDER-2,\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detected_mapping"] == {
        "order_number": "Order Number",
        "tracking_number": "Tracking Number",
    }
    assert payload["total_rows"] == 5
    assert payload["missing_order_rows"] == 1
    assert payload["duplicate_pairs_removed"] == 1
    assert payload["deduped_rows"] == 3
    assert payload["query_target_count"] == 2
    assert payload["no_tracking_rows"] == 1


def test_lite_run_uses_analyzed_status_rules(client, mocker) -> None:
    client.post(
        "/api/settings/api-keys",
        json={
            "label": "Production",
            "environment": "production",
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
                        "mailNo": "SFARRIVED",
                        "routes": [
                            {
                                "acceptTime": "2026-03-10 09:00:00",
                                "opCode": "80",
                                "firstStatusCode": "4",
                                "secondaryStatusCode": "401",
                                "remark": "\u5df2\u6d3e\u9001\u81f3\uff08\u987a\u4e30\u81ea\u52a9\u67dc\uff09",
                            }
                        ],
                    },
                    {
                        "mailNo": "SFCOLLECTED",
                        "routes": [
                            {
                                "acceptTime": "2026-03-10 10:00:00",
                                "opCode": "80",
                                "firstStatusCode": "4",
                                "secondaryStatusCode": "401",
                                "remark": "\u60a8\u7684\u5feb\u4ef6\u5df2\u6d3e\u9001\u81f3\u672c\u4eba",
                            }
                        ],
                    },
                    {
                        "mailNo": "SFSHIPPED",
                        "routes": [
                            {
                                "acceptTime": "2026-03-10 11:00:00",
                                "opCode": "634",
                                "firstStatusCode": "3",
                                "secondaryStatusCode": "301",
                                "remark": "\u5feb\u4ef6\u6b63\u5728\u6d3e\u9001\u9014\u4e2d",
                            }
                        ],
                    },
                    {
                        "mailNo": "SFUNAVAILABLE",
                        "routes": [],
                        "reasonCode": "20028",
                        "reasonRemark": "\u6708\u7ed3\u5361\u53f7\u4e0d\u5339\u914d",
                    },
                    {
                        "mailNo": "SFNOROUTE",
                        "routes": [],
                    },
                ],
            }
        ),
    }
    mocker.patch("app.services.sf_client.SFClient.search_routes", return_value=mocked_response)

    response = client.post(
        "/api/lite/run",
        files={
            "file": (
                "orders.csv",
                (
                    "Order Number,Tracking Number\n"
                    "ORDER-1,SFARRIVED\n"
                    "ORDER-2,SFCOLLECTED\n"
                    "ORDER-3,SFSHIPPED\n"
                    "ORDER-4,SFUNAVAILABLE\n"
                    "ORDER-5,SFNOROUTE\n"
                    "ORDER-6,\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    rows = {row["order_number"]: row for row in payload["rows"]}
    assert rows["ORDER-1"]["status"] == "ARRIVED"
    assert rows["ORDER-2"]["status"] == "COLLECTED"
    assert rows["ORDER-3"]["status"] == "SHIPPED"
    assert rows["ORDER-4"]["status"] == "QUERY_UNAVAILABLE"
    assert rows["ORDER-4"]["sf_express_code"] == "20028"
    assert rows["ORDER-5"]["status"] == "NO_ROUTE"
    assert rows["ORDER-6"]["status"] == "NO_TRACKING"
    assert payload["summary"]["status_counts"] == {
        "ARRIVED": 1,
        "COLLECTED": 1,
        "SHIPPED": 1,
        "QUERY_UNAVAILABLE": 1,
        "NO_ROUTE": 1,
        "NO_TRACKING": 1,
    }


def test_lite_export_uses_customer_headers(client, mocker) -> None:
    client.post(
        "/api/settings/api-keys",
        json={
            "label": "Production",
            "environment": "production",
            "partner_id": "PARTNER",
            "checkword": "CHECKWORD",
            "is_active": True,
        },
    )
    mocker.patch(
        "app.services.sf_client.SFClient.search_routes",
        return_value={
            "apiResultCode": "A1000",
            "apiResultData": json.dumps(
                {
                    "errorCode": "S0000",
                    "routeResps": [
                        {
                            "mailNo": "SF123",
                            "routes": [
                                {
                                    "acceptTime": "2026-03-10 10:00:00",
                                    "opCode": "80",
                                    "firstStatusCode": "4",
                                    "secondaryStatusCode": "401",
                                    "remark": "\u5df2\u6d3e\u9001\u81f3\uff08\u987a\u4e30\u81ea\u52a9\u67dc\uff09",
                                }
                            ],
                        },
                        {
                            "mailNo": "SF456",
                            "routes": [
                                {
                                    "acceptTime": "2026-03-10 10:30:00",
                                    "opCode": "634",
                                    "firstStatusCode": "3",
                                    "secondaryStatusCode": "301",
                                    "remark": "\u5feb\u4ef6\u6b63\u5728\u6d3e\u9001\u9014\u4e2d",
                                }
                            ],
                        },
                    ],
                }
            ),
        },
    )

    response = client.post(
        "/api/lite/export",
        data={"file_format": "xlsx"},
        files={
            "file": (
                "orders.csv",
                "Order Number,Tracking Number\nORDER-1,SF123\nORDER-2,SF456\n".encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ["ARRIVED_COLLECTED", "OTHER_STATUS"]

    primary_sheet = workbook["ARRIVED_COLLECTED"]
    secondary_sheet = workbook["OTHER_STATUS"]
    headers = [cell.value for cell in primary_sheet[1]]
    assert headers == [
        "ORDER NUMBER",
        "TRACKING NO",
        "STATUS",
        "SF EXPRESS CODE",
        "SF EXPRESS REMARK",
    ]
    assert primary_sheet["A2"].value == "ORDER-1"
    assert primary_sheet["C2"].value == "ARRIVED"
    assert secondary_sheet["A2"].value == "ORDER-2"
    assert secondary_sheet["C2"].value == "SHIPPED"
