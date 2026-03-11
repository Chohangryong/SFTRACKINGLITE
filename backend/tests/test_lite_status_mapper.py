from __future__ import annotations

from app.services.lite_status_mapper import map_route_response


def test_map_route_response_splits_80_401_by_remark() -> None:
    arrived = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 09:00:00",
                    "opCode": "80",
                    "firstStatusCode": "4",
                    "secondaryStatusCode": "401",
                    "remark": "\u5df2\u6d3e\u9001\u81f3\uff08\u987a\u4e30\u81ea\u52a9\u67dc\uff09",
                }
            ]
        }
    )
    collected = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 10:00:00",
                    "opCode": "80",
                    "firstStatusCode": "4",
                    "secondaryStatusCode": "401",
                    "remark": "\u60a8\u7684\u5feb\u4ef6\u5df2\u6d3e\u9001\u81f3\u672c\u4eba",
                }
            ]
        }
    )

    assert arrived.status == "ARRIVED"
    assert collected.status == "COLLECTED"


def test_map_route_response_handles_query_unavailable() -> None:
    result = map_route_response(
        {
            "routes": [],
            "reasonCode": "20028",
            "reasonRemark": "\u6708\u7ed3\u5361\u53f7\u4e0d\u5339\u914d",
        }
    )

    assert result.status == "QUERY_UNAVAILABLE"
    assert result.sf_express_code == "20028"
    assert result.sf_express_remark == "\u6708\u7ed3\u5361\u53f7\u4e0d\u5339\u914d"


def test_map_route_response_covers_arrived_shipped_and_exception_rules() -> None:
    arrived = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 11:00:00",
                    "opCode": "642",
                    "firstStatusCode": "11",
                    "secondaryStatusCode": "1101",
                    "remark": "\u5feb\u4ef6\u5230\u8fbe\u6307\u5b9a\u81ea\u53d6\u70b9",
                }
            ]
        }
    )
    shipped = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 12:00:00",
                    "opCode": "634",
                    "firstStatusCode": "3",
                    "secondaryStatusCode": "301",
                    "remark": "\u5feb\u4ef6\u6b63\u5728\u6d3e\u9001\u9014\u4e2d",
                }
            ]
        }
    )
    canceled = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 13:00:00",
                    "opCode": "33",
                    "firstStatusCode": "5",
                    "secondaryStatusCode": "501",
                    "remark": "\u5feb\u4ef6\u5df2\u4f5c\u5e9f",
                }
            ]
        }
    )
    exception = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 13:30:00",
                    "opCode": "126",
                    "firstStatusCode": "11",
                    "secondaryStatusCode": "1101",
                    "remark": "\u53d6\u4ef6\u7801\u5df2\u5931\u6548",
                }
            ]
        }
    )

    assert arrived.status == "ARRIVED"
    assert shipped.status == "SHIPPED"
    assert canceled.status == "CANCELED"
    assert exception.status == "EXCEPTION"


def test_map_route_response_uses_unknown_for_unmapped_latest_state() -> None:
    result = map_route_response(
        {
            "routes": [
                {
                    "acceptTime": "2026-03-10 14:00:00",
                    "opCode": "999",
                    "firstStatusCode": "9",
                    "secondaryStatusCode": "909",
                    "remark": "Unmapped state",
                }
            ]
        }
    )

    assert result.status == "UNKNOWN"
