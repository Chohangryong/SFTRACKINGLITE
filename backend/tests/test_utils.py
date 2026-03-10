from app.utils.excel_safe import escape_excel_formula
from app.utils.signature import build_msg_digest


def test_build_msg_digest_is_deterministic() -> None:
    digest = build_msg_digest('{"trackingNumber":"123"}', "1710000000", "secret")
    assert digest == build_msg_digest('{"trackingNumber":"123"}', "1710000000", "secret")
    assert digest != build_msg_digest('{"trackingNumber":"124"}', "1710000000", "secret")


def test_escape_excel_formula_prefixes_dangerous_values() -> None:
    assert escape_excel_formula("=cmd") == "'=cmd"
    assert escape_excel_formula("+sum") == "'+sum"
    assert escape_excel_formula("safe") == "safe"
