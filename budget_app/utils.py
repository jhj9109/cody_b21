from budget_app.models import Transaction


def print_success(msg: str) -> None:
    print(f"\033[92m[성공]\033[0m {msg}")


def print_info(msg: str) -> None:
    print(f"\033[94m[안내]\033[0m {msg}")


def format_tx(tx: Transaction) -> str:
    """거래 내역을 보기 좋게 문자열로 포맷팅합니다."""

    return " | ".join(
        [
            f"{tx.id:<10}",
            f"{tx.date:<10}",
            f"{tx.type:<7}",
            f"{tx.category:<10}",
            f"{tx.amount:>8}원",
            f"{(tx.memo or '')}< {', '.join(tx.tags or [])} >",
        ]
    )


def parse_strs(strs: str, filter_empty=True) -> list[str]:
    result = []
    for s in strs.split(","):
        cleaned = s.strip()
        if not filter_empty or cleaned:
            result.append(cleaned)
    return result
