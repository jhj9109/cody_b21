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
    error_handler
)
from .io_service import IOService

# ==========================================
# 1. 공통 헬퍼 함수
# ==========================================
def print_success(msg: str) -> None:
    print(f"\033[92m[성공]\033[0m {msg}")

def print_info(msg: str) -> None:
    print(f"\033[94m[안내]\033[0m {msg}")

def format_tx(tx: Dict[str, Any]) -> str:
    """거래 내역을 보기 좋게 문자열로 포맷팅합니다."""
    # 보너스: 문자열 포맷팅으로 테이블 정렬 흉내내기
    memo = tx.get('memo') or ''
    tags = ','.join(tx.get('tags', []))
    tag_str = f" [{tags}]" if tags else ""
    return f"{tx['id']:<10} | {tx['date']:<10} | {tx['type']:<7} | {tx['category']:<10} | {tx['amount']:>8}원 | {memo}{tag_str}"


# ==========================================
# 2. 명령어 처리기 (Command Handlers)
# ==========================================
@error_handler
def handle_add(args) -> None:
    """대화형으로 거래 내역을 추가합니다."""
    print("--- 새로운 거래 내역 추가 ---")
    date = input("날짜(YYYY-MM-DD): ").strip()
    t_type = input("타입(income/expense): ").strip()
    category = input("카테고리: ").strip()
    
    amount_str = input("금액(양수): ").strip()
    try:
        amount = int(amount_str)
    except ValueError:
        raise ValueError("금액은 숫자로 입력해야 합니다.")
        
    memo = input("메모(선택, 없으면 엔터): ").strip()
    memo = memo if memo else None
    
    tags_str = input("태그(쉼표로 구분, 없으면 엔터): ").strip()
    tags = [t.strip() for t in tags_str.split(',')] if tags_str else []

    new_id = TransactionService.add(date, t_type, category, amount, memo, tags)
    print_success(f"저장 완료 (id={new_id})")


@error_handler
def handle_list(args) -> None:
    """최신순으로 내역을 출력합니다."""
    # 제너레이터를 리스트로 바꾸어 역순 정렬 (최신순)
    # 실제 대용량 환경에서는 파일 끝에서부터 읽는 방식을 써야 하지만, 
    # 요구사항의 단순화를 위해 메모리 정렬을 사용합니다.
    if args.limit <= 0:
        raise ValueError("출력 제한 건수(--limit)는 1 이상의 양수여야 합니다.")
    
    limit = args.limit
    min_heap = []
    
    # 1. 파일에서 한 줄씩 '스트리밍'으로 읽어옵니다. (메모리에 전체를 올리지 않음)
    for tx in TransactionService.get_stream():
        date = tx.get('date', '')
        tx_id = tx.get('id', '') # 날짜가 같을 경우를 대비한 세컨더리 키
        
        # 정렬 기준 매칭을 위해 (날짜, ID, 거래딕셔너리) 튜플 형태로 힙에 추가
        if len(min_heap) < limit:
            heapq.heappush(min_heap, (date, tx_id, tx))
        elif date > min_heap[0][0]:
            heapq.heappushpop(min_heap, (date, tx_id, tx))
                
    # 2. 힙에 살아남은 limit 개의 데이터를 꺼내서 역순 정렬 (최신순 배치)
    # 이 시점에서 transactions의 길이는 전체 데이터 수(N)가 아니라 오직 limit 수(K)입니다.
    transactions = [item[2] for item in min_heap]
    transactions.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # 3. 출력 레이어
    print("-" * 70)
    count = 0
    for tx in transactions:
        print(format_tx(tx))
        count += 1
    print("-" * 70)
    print_info(f"총 {count}건 출력됨 (제한: {limit}건)")


@error_handler
def handle_category(args) -> None:
    """카테고리를 관리합니다 (add, list, remove)"""
    action = args.action
    if action == 'list':
        categories = CategoryService.get_all()
        print("--- 카테고리 목록 ---")
        for c in categories:
            print(f"- {c}")
    elif action == 'add':
        name = input("추가할 카테고리명: ").strip()
        CategoryService.add(name)
        print_success(f"카테고리 '{name}' 추가 완료")
    elif action == 'remove':
        name = input("삭제할 카테고리명: ").strip()
        CategoryService.remove(name)
        print_success(f"카테고리 '{name}' 삭제 완료")


@error_handler
def handle_budget(args) -> None:
    """예산을 설정합니다."""
    if args.action == 'set':
        if not args.month or not args.amount:
            raise ValueError("budget set 명령은 --month와 --amount 옵션이 필수입니다.")
        BudgetService.set_budget(args.month, int(args.amount))
        print_success(f"{args.month} 예산 {args.amount}원 설정 완료")


@error_handler
def handle_delete(args) -> None:
    """특정 거래 내역을 삭제합니다."""
    if not args.id:
        raise ValueError("삭제할 내역의 id를 --id 옵션으로 지정해야 합니다.")
    TransactionService.delete(args.id)
    print_success(f"id={args.id} 삭제 완료")

@error_handler
def handle_summary(args) -> None:
    if not args.month:
        raise ValueError("summary 명령은 --month 옵션이 필수입니다. (예: --month 2024-01)")
    
    # 🌟 [추가] 1. Month 인자 유효성 검사
    import re
    from datetime import datetime
    if not re.match(r"^\d{4}-\d{2}$", args.month):
        raise ValueError(f"요약 월 형식이 올바르지 않습니다. YYYY-MM 형식을 맞춰주세요. (입력값: '{args.month}')")
    try:
        datetime.strptime(f"{args.month}-01", "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"존재하지 않는 연/월입니다. 달력을 확인해 주세요. (입력값: '{args.month}')")

    # 🌟 [추가] 2. Top 인자 유효성 검사
    if args.top <= 0:
        raise ValueError(f"TOP 출력 건수(--top)는 1 이상의 양수여야 합니다. (입력값: {args.top})")
    
    data = SummaryService.get_monthly_summary(args.month)
    
    if data['income'] == 0 and data['expense'] == 0:
        print_info(f"{args.month}월은 데이터 없음")
        return

    print(f"\n--- {args.month}월 요약 ---")
    print(f"총 수입: {data['income']}원")
    print(f"총 지출: {data['expense']}원")
    print(f"잔여액: {data['balance']}원")

    # 예산 정보 연동
    budget = BudgetService.get_budget(args.month)
    if budget:
        usage = (data['expense'] / budget) * 100 if budget > 0 else 0
        warning = "\033[91m(초과 경고!)\033[0m" if usage > 100 else ""
        print(f"예산: {budget}원 (사용률 {usage:.1f}%) {warning}")

    print(f"\n지출 TOP {args.top}")
    sorted_cat = sorted(data['category_expenses'].items(), key=lambda item: item[1], reverse=True)
    for i, (cat, amt) in enumerate(sorted_cat[:args.top], 1):
        print(f"{i}) {cat}: {amt}원")

@error_handler
def handle_export(args) -> None:
    if not args.out:
        raise ValueError("내보낼 파일명을 --out 옵션으로 지정하세요.")
    count = IOService.export_csv(args.out, month=args.month, from_date=getattr(args, 'from', None), to_date=args.to)
    print_success(f"[완료] {args.out} ({count} records)")

@error_handler
def handle_import(args) -> None:
    if not getattr(args, 'from'):
        raise ValueError("가져올 파일명을 --from 옵션으로 지정하세요.")
    imported, skipped = IOService.import_csv(getattr(args, 'from'))
    print_success(f"[완료] imported={imported}, skipped={skipped}")

@error_handler
def handle_search(args) -> None:
    # 서비스 계층에 인자 전달
    results = TransactionService.search(
        from_date=args.from_date,
        to_date=args.to_date,
        category=args.category,
        tx_type=args.type,
        q=args.q,
        tag=args.tag
    )
    
    count = 0
    print(f"\n[{'검색 결과':^30}]")
    for tx in results:
        # 데이터 출력 (기존 list 출력 포맷과 동일하게 맞추시면 됩니다)
        tags_str = f" [태그: {','.join(tx.get('tags', []))}]" if tx.get('tags') else ""
        memo_str = f" - {tx.get('memo')}" if tx.get('memo') else ""
        print(f"{tx['id']} | {tx['date']} | {tx['type']:<7} | {tx['category']:<10} | {tx['amount']}원{memo_str}{tags_str}")
        count += 1
        
    if count == 0:
        print("조건에 일치하는 내역이 없습니다.")
    else:
        print(f"\n총 {count}건이 검색되었습니다.")

@error_handler
def handle_update(args) -> None:
    # 수정할 데이터만 딕셔너리로 추출 (None 값 제외)
    update_data = {}
    if args.date: update_data['date'] = args.date
    if args.type: update_data['type'] = args.type
    if args.category: update_data['category'] = args.category
    if args.amount is not None: update_data['amount'] = args.amount
    if args.memo is not None: update_data['memo'] = args.memo
    if args.tags is not None:
        update_data['tags'] = [t.strip() for t in args.tags.split(',') if t.strip()]

    if not update_data:
        raise ValueError("수정할 항목(--amount, --category 등)을 하나 이상 지정해야 합니다.")

    TransactionService.update(args.id, update_data)
    print(f"[성공] {args.id} 내역이 안전하게 수정되었습니다.")

# ==========================================
# 3. 메인 CLI 진입점
# ==========================================
def main():
    
    # 1. Argument Parser 설정
    parser = argparse.ArgumentParser(description="작은 서비스: 파일 기반 가계부 콘솔 프로그램")
    parser.add_argument('--data-dir', default='./data', help='데이터 파일이 저장될 폴더 경로 지정 (기본값: ./data)')
    subparsers = parser.add_subparsers(dest='command', help='사용할 명령어')

    # 'add' 명령어
    subparsers.add_parser('add', help='대화형으로 새로운 거래 내역을 추가합니다.')

    # 'list' 명령어
    parser_list = subparsers.add_parser('list', help='거래 내역 목록을 최신순으로 출력합니다.')
    parser_list.add_argument('--limit', type=int, default=50, help='출력할 최대 건수 (기본값: 50)')

    # 'category' 명령어
    parser_cat = subparsers.add_parser('category', help='카테고리 관리 (add, list, remove)')
    parser_cat.add_argument('action', choices=['add', 'list', 'remove'], help='수행할 작업')

    # 'budget' 명령어
    parser_budget = subparsers.add_parser('budget', help='예산 설정 (budget set --month ... --amount ...)')
    parser_budget.add_argument('action', choices=['set'], help='수행할 작업')
    parser_budget.add_argument('--month', help='예산 월 (YYYY-MM)')
    parser_budget.add_argument('--amount', help='예산 금액')

    # 'delete' 명령어
    parser_del = subparsers.add_parser('delete', help='특정 거래 내역을 삭제합니다.')
    parser_del.add_argument('--id', help='삭제할 거래 내역 ID (예: TX-000001)')

    # (기존 'delete' 명령어 아래에 추가하세요)

    # 'summary' 명령어
    parser_sum = subparsers.add_parser('summary', help='월별 요약을 출력합니다.')
    parser_sum.add_argument('--month', help='요약할 월 (YYYY-MM)')
    parser_sum.add_argument('--top', type=int, default=3, help='카테고리별 지출 TOP N (기본값 3)')

    # 'export' 명령어
    parser_exp = subparsers.add_parser('export', help='조건에 맞는 거래 내역을 CSV로 내보냅니다.')
    parser_exp.add_argument('--out', help='저장할 CSV 파일명')
    parser_exp.add_argument('--month', help='내보낼 월 (YYYY-MM)')
    parser_exp.add_argument('--from', help='시작 날짜 (YYYY-MM-DD)')
    parser_exp.add_argument('--to', help='종료 날짜 (YYYY-MM-DD)')

    # 'import' 명령어
    parser_imp = subparsers.add_parser('import', help='CSV 파일에서 거래 내역을 일괄 등록합니다.')
    parser_imp.add_argument('--from', help='가져올 CSV 파일명')

    # === [검색 파서] ===
    parser_search = subparsers.add_parser('search', help='조건에 맞는 거래 내역을 검색합니다.')
    # 파이썬 예약어 from과 겹치지 않도록 dest='from_date'를 사용합니다.
    parser_search.add_argument('--from', dest='from_date', help='검색 시작일 (예: 2024-01-01)')
    parser_search.add_argument('--to', dest='to_date', help='검색 종료일 (예: 2024-01-31)')
    parser_search.add_argument('--category', help='카테고리 필터')
    parser_search.add_argument('--type', choices=['income', 'expense'], help='수입/지출 필터')
    parser_search.add_argument('--q', help='메모 검색어 키워드')
    parser_search.add_argument('--tag', help='태그 검색어')

    # === [수정 파서] ===
    parser_update = subparsers.add_parser('update', help='기존 거래 내역을 수정합니다.')
    parser_update.add_argument('--id', required=True, help='수정할 거래 내역의 ID (필수)')
    parser_update.add_argument('--date', help='수정할 날짜 (YYYY-MM-DD)')
    parser_update.add_argument('--type', choices=['income', 'expense'], help='변경할 타입')
    parser_update.add_argument('--category', help='변경할 카테고리')
    parser_update.add_argument('--amount', type=int, help='변경할 금액')
    parser_update.add_argument('--memo', help='변경할 메모')
    parser_update.add_argument('--tags', help='변경할 태그 (쉼표 구분)')

    # 파싱 및 분기
    args = parser.parse_args()

    # 2. 저장소 초기화 (data 폴더 및 파일 생성) with 경로 설정
    if (args.data_dir):
        set_data_dir(args.data_dir)
    init_storage()

    if args.command == 'add':
        handle_add(args)
    elif args.command == 'list':
        handle_list(args)
    elif args.command == 'category':
        handle_category(args)
    elif args.command == 'budget':
        handle_budget(args)
    elif args.command == 'delete':
        handle_delete(args)
    elif args.command == 'summary':
        handle_summary(args)
    elif args.command == 'export':
        handle_export(args)
    elif args.command == 'import':
        handle_import(args)
    elif args.command == 'search':
        handle_search(args)
    elif args.command == 'update':
        handle_update(args)
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == '__main__':
    main()