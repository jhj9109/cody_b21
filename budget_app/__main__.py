import argparse
import sys
from typing import Dict, Any
import heapq

# 내부 모듈 임포트
from .storage import init_storage, set_data_dir
from .services import (
    TransactionService,
    CategoryService,
    BudgetService,
    SummaryService,
    error_handler,
)
from .io_service import IOService
from .models import (
    Transaction,
    Budget,
    UpdateTransactionData,
)  # 데이터 클래스 엔진 임포트
from .validators import (
    parse_and_validate_int,
    validate_month_format,
    validate_positive_number,
    validate_transaction_id,
)  # 공통 검증기 임포트


# ==========================================
# 1. 공통 헬퍼 함수
# ==========================================
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
            f"{(tx.memo or '')}< {', '.join(tx.tags)} >",
        ]
    )


def parse_strs(strs: str, filter_empty=True) -> list[str]:
    result = []
    for s in strs.split(","):
        cleaned = s.strip()
        if not filter_empty or cleaned:
            result.append(cleaned)
    return result


# ==========================================
# 2. 명령어 처리기 (Command Handlers)
# ==========================================
@error_handler
def handle_add(args) -> None:
    """대화형으로 거래 내역을 추가합니다."""

    print("--- 새로운 거래 내역 추가 ---")

    # 입력 받기, 유효성 검증은 모두 끝난후에
    date = input("날짜(YYYY-MM-DD): ").strip()
    t_type = input("타입(income/expense): ").strip()
    category = input("카테고리: ").strip()
    amount_str = input("금액(양수): ")
    memo = input("메모(선택): ").strip() or None
    tags = parse_strs(input("태그(선택, 쉼표로 구분): ").strip(), filter_empty=True)

    amount = parse_and_validate_int(amount_str, "금액")

    tx = Transaction(
        id="TX-000000",
        type=t_type,
        date=date,
        amount=amount,
        category=category,
        memo=memo,
        tags=tags,
    )

    new_id = TransactionService.add(tx)

    print_success(f"저장 완료 (id={new_id})")


@error_handler
def handle_update(args) -> None:

    utx = UpdateTransactionData(
        id=args.id,
        type=args.type if args.type is None else args.type.strip(),
        date=args.date if args.date is None else args.date.strip(),
        amount=args.amount,
        category=args.category if args.category is None else args.category.strip(),
        memo=args.memo if args.memo is None else args.memo.strip(),
        tags=(
            args.tags
            if args.tags is None
            else parse_strs(args.tags.strip(), filter_empty=True)
        ),
    )

    TransactionService.update(utx)
    print_success(f"{utx.id} 내역이 안전하게 수정되었습니다.")


@error_handler
def handle_list(args) -> None:
    """최신순으로 내역을 출력합니다."""

    limit = args.limit
    validate_positive_number(limit, "출력 제한 건수(--limit)", allow_zero=False)

    min_heap = []

    for tx_dict in TransactionService.get_stream():

        tx = Transaction(**tx_dict)

        if len(min_heap) < limit:
            heapq.heappush(min_heap, tx)
        elif tx > min_heap[0]:
            heapq.heappushpop(min_heap, tx)

    min_heap.sort(reverse=True)

    print("-" * 90)
    for tx in min_heap:
        print(format_tx(tx))
    print("-" * 90)
    print_info(f"총 {len(min_heap)}건 출력됨 (제한: {limit}건)")


@error_handler
def handle_category(args) -> None:
    """카테고리를 관리합니다 (add, list, remove)"""
    action = args.action
    if action == "list":
        categories = CategoryService.get_all()
        print("--- 카테고리 목록 ---")
        for c in categories:
            print(f"- {c}")
    elif action == "add":
        name = input("추가할 카테고리명: ").strip()
        CategoryService.add(name)
        print_success(f"카테고리 '{name}' 추가 완료")
    elif action == "remove":
        name = input("삭제할 카테고리명: ").strip()
        CategoryService.remove(name)
        print_success(f"카테고리 '{name}' 삭제 완료")
    else:
        pass  # 도달하지 않음


@error_handler
def handle_budget(args) -> None:
    """예산을 설정합니다."""

    b = Budget(month=args.month, amount=args.amount)
    BudgetService.set_budget(b)
    print_success(f"{args.month} 예산 {args.amount}원 설정 완료")


@error_handler
def handle_delete(args) -> None:
    """특정 거래 내역을 삭제합니다."""
    validate_transaction_id(args.id)
    TransactionService.delete(args.id)
    print_success(f"id={args.id} 삭제 완료")


@error_handler
def handle_summary(args) -> None:
    if not args.month:
        raise ValueError(
            "summary 명령은 --month 옵션이 필수입니다. (예: --month 2024-01)"
        )

    validate_month_format(args.month)
    validate_positive_number(args.top, "TOP 출력 건수(--top)", allow_zero=False)

    summary = SummaryService.get_monthly_summary(args.month)

    # 예산 정보 연동
    budget = BudgetService.get_budget(args.month)

    if summary is None and budget is None:
        print_info(f"{args.month}월은 데이터 없음")
        return

    print(f"\n--- {args.month}월 요약 ---")

    if summary:
        print(f"총 수입: {summary['income']}원")
        print(f"총 지출: {summary['expense']}원")
        print(f"잔여액: {summary['balance']}원")
    else:
        print_info(f"{args.month}월은 수입/지출 내역 없음")
    if budget:
        usage = (
            (summary["expense"] if summary else 0 / budget) * 100 if budget > 0 else 0
        )
        warning = "\033[91m(초과 경고!)\033[0m" if usage > 100 else ""
        print(f"예산: {budget}원 (사용률 {usage:.1f}%) {warning}")

    if summary:
        print(f"\n지출 TOP {args.top}")
        sorted_cat = sorted(
            summary["category_expenses"].items(), key=lambda item: item[1], reverse=True
        )
        for i, (cat, amt) in enumerate(sorted_cat[: args.top], 1):
            print(f"{i}) {cat}: {amt}원")


@error_handler
def handle_export(args) -> None:
    count = IOService.export_csv(
        args.out, month=args.month, from_date=args.from_date, to_date=args.to_date
    )
    print_success(f"[완료] {args.out} ({count} records)")


@error_handler
def handle_import(args) -> None:
    imported, skipped = IOService.import_csv(args.from_path)
    print_success(f"[완료] imported={imported}, skipped={skipped}")


@error_handler
def handle_search(args) -> None:
    results = TransactionService.search(
        from_date=args.from_date,
        to_date=args.to_date,
        category=args.category,
        t_type=args.type,
        q=args.q,
        tag=args.tag,
    )

    count = 0
    print(f"\n{('-'*40 + '검색 결과' + '-'*40):^80}")
    for tx in results:
        print(format_tx(tx))
        count += 1
    print("-" * 90)
    if count == 0:
        print("조건에 일치하는 내역이 없습니다.")
    else:
        print(f"\n총 {count}건이 검색되었습니다.")


# ==========================================
# 3. 메인 CLI 진입점
# ==========================================


def main():
    parser = argparse.ArgumentParser(
        description="작은 서비스: 파일 기반 가계부 콘솔 프로그램"
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="데이터 파일이 저장될 폴더 경로 지정 (기본값: ./data)",
    )
    subparsers = parser.add_subparsers(dest="command", help="사용할 명령어")

    subparsers.add_parser("add", help="대화형으로 새로운 거래 내역을 추가합니다.")

    parser_list = subparsers.add_parser(
        "list", help="거래 내역 목록을 최신순으로 출력합니다."
    )
    parser_list.add_argument(
        "--limit", type=int, default=50, help="출력할 최대 건수 (기본값: 50)"
    )

    parser_cat = subparsers.add_parser(
        "category", help="카테고리 관리 (add, list, remove)"
    )
    parser_cat.add_argument(
        "action", choices=["add", "list", "remove"], help="수행할 작업"
    )

    parser_budget = subparsers.add_parser(
        "budget", help="예산 설정 (budget set --month ... --amount ...)"
    )
    parser_budget.add_argument("action", choices=["set"], help="수행할 작업")
    parser_budget.add_argument("--month", required=True, help="예산 월 (YYYY-MM)")
    parser_budget.add_argument("--amount", type=int, required=True, help="예산 금액")

    parser_del = subparsers.add_parser("delete", help="특정 거래 내역을 삭제합니다.")
    parser_del.add_argument(
        "--id", required=True, help="삭제할 거래 내역 ID (예: TX-000001)"
    )

    parser_sum = subparsers.add_parser("summary", help="월별 요약을 출력합니다.")
    parser_sum.add_argument("--month", required=True, help="요약할 월 (YYYY-MM)")
    parser_sum.add_argument(
        "--top", type=int, default=3, help="카테고리별 지출 TOP N (기본값 3)"
    )

    # 'export' 명령어
    parser_exp = subparsers.add_parser(
        "export", help="조건에 맞는 거래 내역을 CSV로 내보냅니다."
    )
    parser_exp.add_argument("--out", required=True, help="저장할 CSV 파일명")
    parser_exp.add_argument("--month", help="내보낼 월 (YYYY-MM)")
    parser_exp.add_argument("--from", dest="from_date", help="시작 날짜 (YYYY-MM-DD)")
    parser_exp.add_argument("--to", dest="to_date", help="종료 날짜 (YYYY-MM-DD)")

    # 'import' 명령어
    parser_imp = subparsers.add_parser(
        "import", help="CSV 파일에서 거래 내역을 일괄 등록합니다."
    )
    parser_imp.add_argument(
        "--from", dest="from_path", required=True, help="가져올 CSV 파일명"
    )

    # === [검색 파서] ===
    parser_search = subparsers.add_parser(
        "search", help="조건에 맞는 거래 내역을 검색합니다."
    )
    parser_search.add_argument(
        "--from", dest="from_date", help="검색 시작일 (예: 2024-01-01)"
    )
    parser_search.add_argument(
        "--to", dest="to_date", help="검색 종료일 (예: 2024-01-31)"
    )
    parser_search.add_argument("--category", help="카테고리 필터")
    parser_search.add_argument(
        "--type", choices=["income", "expense"], help="수입/지출 필터"
    )
    parser_search.add_argument("--q", help="메모 검색어 키워드")
    parser_search.add_argument("--tag", help="태그 검색어")

    # === [수정 파서] ===
    parser_update = subparsers.add_parser("update", help="기존 거래 내역을 수정합니다.")
    parser_update.add_argument(
        "--id", required=True, help="수정할 거래 내역의 ID (필수)"
    )
    parser_update.add_argument("--date", help="수정할 날짜 (YYYY-MM-DD)")
    parser_update.add_argument(
        "--type", choices=["income", "expense"], help="변경할 타입"
    )
    parser_update.add_argument("--category", help="변경할 카테고리")
    parser_update.add_argument("--amount", type=int, help="변경할 금액")
    parser_update.add_argument("--memo", help="변경할 메모")
    parser_update.add_argument("--tags", help="변경할 태그 (쉼표 구분)")

    args = parser.parse_args()

    if args.data_dir:
        set_data_dir(args.data_dir)
    init_storage()

    if args.command == "add":
        handle_add(args)
    elif args.command == "list":
        handle_list(args)
    elif args.command == "category":
        handle_category(args)
    elif args.command == "budget":
        handle_budget(args)
    elif args.command == "delete":
        handle_delete(args)
    elif args.command == "summary":
        handle_summary(args)
    elif args.command == "export":
        handle_export(args)
    elif args.command == "import":
        handle_import(args)
    elif args.command == "search":
        handle_search(args)
    elif args.command == "update":
        handle_update(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
