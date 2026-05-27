# validators.py
import re
from datetime import datetime
from typing import List, Optional


def validate_month_format(month: str) -> None:
    """YYYY-MM 형식 및 실제 달력상의 연/월인지 검증합니다."""
    if not month or not re.match(r"^\d{4}-\d{2}$", month):
        raise ValueError(
            f"연/월 형식이 올바르지 않습니다. YYYY-MM 형식을 맞춰주세요. (입력값: '{month}')"
        )
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise ValueError(
            f"존재하지 않는 연/월입니다. 달력을 확인해 주세요. (입력값: '{month}')"
        )
    return True


def validate_date_format(date_str: str) -> None:
    """YYYY-MM-DD 형식 및 실제 달력상의 날짜(윤년 포함)인지 검증합니다."""
    if not date_str or not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError(
            f"날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 맞춰주세요. (입력값: '{date_str}')"
        )
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"존재하지 않는 날짜입니다. 실제 달력에 맞는 날짜를 입력해 주세요. (입력값: '{date_str}')"
        )
    return True


def validate_positive_number(
    value: int, field_name: str, allow_zero: bool = False
) -> None:
    """숫자가 양수인지 검증합니다. (옵션에 따라 0 허용 여부 결정)"""
    if allow_zero and value < 0:
        raise ValueError(f"{field_name}은(는) 0 이상이어야 합니다. (입력값: {value})")
    if not allow_zero and value <= 0:
        raise ValueError(
            f"{field_name}은(는) 1 이상의 양수여야 합니다. (입력값: {value})"
        )
    return True


def validate_not_blank(value: str, field_name: str) -> None:
    """문자열이 비어있거나 공백 문자로만 이루어져 있는지 검증합니다."""
    if not value.strip():
        raise ValueError(f"{field_name}은(는) 비어있거나 공백일 수 없습니다.")
    return True


def validate_transaction_id(tx_id: str) -> None:
    """가계부 ID가 규격(TX-숫자6자리)에 맞는지 검증합니다."""
    if not tx_id or not re.match(r"^TX-\d{6}$", tx_id):
        raise ValueError(
            f"ID 형식이 가계부 규격(TX-000000)에 맞지 않습니다. (입력값: '{tx_id}')"
        )
    return True


def validate_transaction_type(t_type: str) -> None:
    """거래 타입이 income 또는 expense 인지 검증합니다."""
    if t_type not in ("income", "expense"):
        raise ValueError(
            f"타입은 'income' 또는 'expense'만 가능합니다. (입력값: '{t_type}')"
        )
    return True


def validate_tags(tags: List[str]) -> None:
    """태그 리스트 내 공백 요소 및 중복이 존재하는지 검증합니다."""
    if any(not tag.strip() for tag in tags):
        raise ValueError(
            f"태그 목록에 비어있는 값이나 공백 문자가 포함되어 있습니다. (입력값: {tags})"
        )
    if len(tags) != len(set(tags)):
        raise ValueError(
            f"태그 목록에 중복된 값이 존재합니다. 중복을 제거해 주세요. (입력값: {tags})"
        )
    return True


def parse_and_validate_int(value_str: str, field_name: str) -> int:
    """
    문자열 데이터를 정수(int)형으로 안전하게 변환합니다.
    숫자가 아니거나 정수 포맷이 아닐 경우 사용자 친화적인 ValueError를 던집니다.
    """
    try:
        return int(value_str.strip())
    except (ValueError, TypeError):
        raise ValueError(
            f"{field_name}은(는) 반드시 숫자로만 입력해야 합니다. (입력값: '{value_str}')"
        )
