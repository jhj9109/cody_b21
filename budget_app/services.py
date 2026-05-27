import sys
import time
import os
from functools import wraps
from typing import Iterator, List, Dict, Any, Optional

from budget_app.validators import parse_and_validate_int

from .models import Transaction, Budget, UpdateTransactionData
from .storage import read_stream, append_record, rewrite_records


# ==========================================
# 1. 데코레이터 (공통 관심사 분리)
# ==========================================
def time_logger(func):
    """함수의 실행 시간을 측정하는 데코레이터입니다. (성능 모니터링)"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        # 필요시 아래 주석을 해제하면 모든 실행 시간을 로깅할 수 있습니다.
        # print(f"[{func.__name__} 실행 완료 : {end_time - start_time:.4f}초]")
        return result

    return wrapper


def error_handler(func):
    """
    [핵심 요구사항] 예외 발생 시 스택트레이스를 숨기고
    사용자 친화적인 메시지와 힌트를 출력한 뒤 에러 코드(1)로 종료합니다.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C 또는 Ctrl+D 입력 시 진입
            print(
                "\n\n[안내] 사용자에 의해 프로그램이 종료되었습니다. 이용해 주셔서 감사합니다."
            )
            sys.exit(0)  # 사용자가 직접 종료한 것이므로 정상 종료 코드(0) 반환
        except ValueError as e:
            print(f"\n[오류] 입력값이 올바르지 않거나 규칙에 위배됩니다.")
            print(f"[원인] {e}")
            print(f"[힌트] 명령어와 옵션, 데이터 형식을 다시 확인해 주세요.")
            sys.exit(1)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)
        except Exception as e:
            print(f"\n[오류] 시스템 처리 중 문제가 발생했습니다.")
            print(f"[원인] {e}")
            sys.exit(1)

    return wrapper


# ==========================================
# 2. 비즈니스 로직 서비스
# ==========================================
class CategoryService:
    @staticmethod
    def get_all() -> List[str]:
        """현재 등록된 모든 카테고리 이름을 리스트로 반환합니다."""
        return [c["name"] for c in read_stream("categories")]

    @staticmethod
    def add(name: str) -> None:
        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError("카테고리 이름은 공백이거나 비어있을 수 없습니다.")

        categories = CategoryService.get_all()
        if cleaned_name in categories:
            raise ValueError(f"'{cleaned_name}'(은)는 이미 존재하는 카테고리입니다.")

        append_record("categories", {"name": cleaned_name})

    @staticmethod
    def remove(name: str) -> None:
        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError("카테고리 이름은 공백이거나 비어있을 수 없습니다.")

        categories = CategoryService.get_all()
        if cleaned_name not in categories:
            raise ValueError(f"'{cleaned_name}'(은)는 존재하지 않는 카테고리입니다.")

        for tx_dict in read_stream("transactions"):
            tx = Transaction(**tx_dict)
            if tx.category == cleaned_name:
                raise ValueError(
                    f"'{cleaned_name}' 카테고리는 기존 거래 내역에서 사용 중이므로 삭제할 수 없습니다."
                )

        def _filter_categories():
            for c in read_stream("categories"):
                if c["name"] != cleaned_name:
                    yield c

        rewrite_records("categories", _filter_categories())


class TransactionService:
    @staticmethod
    def _generate_id() -> str:
        """기존 데이터를 스캔하여 가장 높은 숫자 ID의 다음 번호를 생성합니다."""
        max_id = 0
        for tx_dict in read_stream("transactions"):
            tx = Transaction(**tx_dict)
            max_id = max(max_id, tx.id_number)
        return f"TX-{max_id + 1:06d}"

    @staticmethod
    def get_stream() -> Iterator[Dict[str, Any]]:
        """전체 거래 내역을 스트리밍으로 반환합니다."""
        yield from read_stream("transactions")

    @staticmethod
    @time_logger
    def add(tx: Transaction) -> str:
        if tx.category not in CategoryService.get_all():
            raise ValueError(
                f"'{tx.category}'는 등록되지 않은 카테고리입니다. category add 명령으로 먼저 추가하세요."
            )

        tx.id = TransactionService._generate_id()

        append_record("transactions", tx.__dict__)
        return tx.id

    @staticmethod
    def update(utx: UpdateTransactionData) -> None:
        """존재하는 ID를 찾아 값을 수정한 뒤 원자적으로 재기록합니다."""

        records = list(read_stream("transactions"))
        found = False

        for tx_dict in records:
            tx = Transaction(**tx_dict)
            if tx.id == utx.id:
                found = True
                # 카테고리가 변경되었다면 유효한 카테고리인지 사전 검사
                if utx.category and utx.category not in CategoryService.get_all():
                    raise ValueError(
                        f"존재하지 않는 카테고리입니다. (입력값: '{utx.category}')"
                    )
                tx_dict.update(utx.update_data)
                break

        if not found:
            raise ValueError(
                f"존재하지 않는 ID입니다. 삭제되었거나 오타일 수 있습니다. (입력값: '{utx.id}')"
            )

        rewrite_records("transactions", records)

    @staticmethod
    def delete(tx_id: str) -> None:
        """원자적 교체 방식을 통해 특정 ID의 내역만 제거하고 다시 저장합니다."""
        # 1. 우선 메모리 낭비 없이 해당 ID가 존재하는지 '스트리밍'으로 먼저 검사합니다.
        found = any(
            tx_dict.get("id") == tx_id for tx_dict in read_stream("transactions")
        )

        if not found:
            # ID가 없으면 디스크는 손대지도 않고 즉시 예외를 던져 종료합니다. (Early Exit)
            raise ValueError(f"id가 '{tx_id}'인 거래 내역을 찾을 수 없습니다.")

        # 2. ID가 확실히 존재할 때만 안전하게 원자적 삭제 쓰기를 수행합니다.
        def _filter_tx():
            for tx_id in read_stream("transactions"):
                if tx_id.get("id") == tx_id:
                    continue
                yield tx_id

        rewrite_records("transactions", _filter_tx())

    @staticmethod
    @time_logger
    def search(
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        category: Optional[str] = None,
        t_type: Optional[str] = None,
        q: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        [핵심] 조건에 맞는 내역만 필터링하여 제너레이터(yield) 파이프라인으로 반환합니다.
        데이터가 수백만 건이어도 메모리 부하 없이 검색이 가능합니다.
        """
        for tx_dict in read_stream("transactions"):
            tx = Transaction(**tx_dict)
            if not (
                any(
                    [
                        from_date and tx.date < from_date,
                        to_date and tx.date > to_date,
                        category and tx.category != category,
                        t_type and tx.type != t_type,
                        q and (tx.memo is None or q not in tx.memo),
                        tag and (tx.tags is None or tag not in tx.tags),
                    ]
                )
            ):
                yield tx


class BudgetService:
    @staticmethod
    def set_budget(b: Budget) -> None:
        budgets = list(read_stream("budgets"))

        existing_bd = None
        for bd_dict in budgets:
            bd = Budget(**bd_dict)
            if bd.month == b.month:
                existing_bd = bd_dict
                break

        if existing_bd is not None:
            # [경우의 수 A] 기존 데이터가 존재하는 상황
            if existing_bd.get("amount") == b.amount:
                # A-1. 데이터 상태 변화가 없으므로 디스크를 전혀 건드리지 않고 즉시 리턴 (Idempotency 보장)
                return

            # A-2. 금액이 달라졌으므로 메모리 상의 데이터를 수정 후 '원자적 전체 재기록' 수행
            existing_bd["amount"] = b.amount
            rewrite_records("budgets", iter(budgets))

        else:
            # [경우의 수 B] 기존에 해당 월의 예산이 아예 존재하지 않는 상황 (신규 등록)
            # 전체 파일을 새로 쓸 필요가 전혀 없으므로, 파일 끝에 가볍게 한 줄만 붙이는 원천 최적화 수행
            append_record("budgets", b.__dict__)

    @staticmethod
    def get_budget(month: str) -> Optional[int]:
        for bd_dict in read_stream("budgets"):
            bd = Budget(**bd_dict)
            if bd.month == month:
                return bd.amount
        return None


class SummaryService:
    @staticmethod
    @time_logger
    def get_monthly_summary(month: str) -> Optional[Dict[str, Any]]:
        """스트리밍 데이터를 활용해 특정 월의 요약 통계(수입/지출/카테고리별 합계)를 계산합니다."""
        total_income = 0
        total_expense = 0
        category_expenses = {}
        exist_data = False

        for tx_dict in read_stream("transactions"):
            tx = Transaction(**tx_dict)
            if tx.date.startswith(month):
                exist_data = True
                if tx.type == "income":
                    total_income += tx.amount
                elif tx.type == "expense":
                    total_expense += tx.amount
                    category_expenses[tx.category] = (
                        category_expenses.get(tx.category, 0) + tx.amount
                    )
        if not exist_data:
            return None
        else:
            return {
                "income": total_income,
                "expense": total_expense,
                "balance": total_income - total_expense,
                "category_expenses": category_expenses,
            }
