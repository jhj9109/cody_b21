import sys
import time
from functools import wraps
from typing import Iterator, List, Dict, Any, Optional

from .models import Transaction, Budget
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
        except ValueError as e:
            print(f"\n[오류] 입력값이 올바르지 않거나 규칙에 위배됩니다.")
            print(f"[원인] {e}")
            print(f"[힌트] 명령어와 옵션, 데이터 형식을 다시 확인해 주세요.")
            sys.exit(1) # 0이 아닌 값으로 종료
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
        return [c['name'] for c in read_stream('categories')]

    @staticmethod
    def add(name: str) -> None:
        categories = CategoryService.get_all()
        if name in categories:
            raise ValueError(f"'{name}'(은)는 이미 존재하는 카테고리입니다.")
        append_record('categories', {'name': name})

    @staticmethod
    def remove(name: str) -> None:
        categories = CategoryService.get_all()
        if name not in categories:
            raise ValueError(f"'{name}'(은)는 존재하지 않는 카테고리입니다.")

        # [요구사항] 삭제하려는 카테고리가 거래 내역에서 사용 중인지 검사
        for tx in read_stream('transactions'):
            if tx.get('category') == name:
                raise ValueError(f"'{name}' 카테고리는 기존 거래 내역에서 사용 중이므로 삭제할 수 없습니다.")

        def _filter_categories():
            for c in read_stream('categories'):
                if c['name'] != name:
                    yield c
                    
        rewrite_records('categories', _filter_categories())


class TransactionService:
    @staticmethod
    def _generate_id() -> str:
        """기존 데이터를 스캔하여 가장 높은 숫자 ID의 다음 번호를 생성합니다."""
        max_id = 0
        for tx in read_stream('transactions'):
            tx_id = tx.get('id', '')
            if tx_id.startswith('TX-'):
                try:
                    num = int(tx_id.split('-')[1])
                    if num > max_id:
                        max_id = num
                except ValueError:
                    continue
        return f"TX-{max_id + 1:06d}"

    @staticmethod
    @time_logger
    def add(date: str, t_type: str, category: str, amount: int, memo: Optional[str], tags: List[str]) -> str:
        if category not in CategoryService.get_all():
            raise ValueError(f"'{category}'는 등록되지 않은 카테고리입니다. category add 명령으로 먼저 추가하세요.")
        
        new_id = TransactionService._generate_id()
        tx = Transaction(id=new_id, type=t_type, date=date, amount=amount, category=category, memo=memo, tags=tags)
        
        append_record('transactions', tx.__dict__)
        return new_id

    @staticmethod
    def get_stream() -> Iterator[Dict[str, Any]]:
        """전체 거래 내역을 스트리밍으로 반환합니다."""
        yield from read_stream('transactions')

    @staticmethod
    @time_logger
    def search(from_date: Optional[str] = None, 
               to_date: Optional[str] = None, 
               category: Optional[str] = None, 
               t_type: Optional[str] = None, 
               q: Optional[str] = None, 
               tag: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        """
        [핵심] 조건에 맞는 내역만 필터링하여 제너레이터(yield) 파이프라인으로 반환합니다.
        데이터가 수백만 건이어도 메모리 부하 없이 검색이 가능합니다.
        """
        for tx in read_stream('transactions'):
            if from_date and tx.get('date') < from_date: continue
            if to_date and tx.get('date') > to_date: continue
            if category and tx.get('category') != category: continue
            if t_type and tx.get('type') != t_type: continue
            if q and q not in str(tx.get('memo', '')): continue
            if tag and tag not in tx.get('tags', []): continue
            
            yield tx

    @staticmethod
    def delete(tx_id: str) -> None:
        """원자적 교체 방식을 통해 특정 ID의 내역만 제거하고 다시 저장합니다."""
        found = False
        def _filter_tx():
            nonlocal found
            for tx in read_stream('transactions'):
                if tx.get('id') == tx_id:
                    found = True
                    continue  # 삭제 대상은 yield 하지 않고 건너뜀
                yield tx
                
        rewrite_records('transactions', _filter_tx())
        if not found:
            raise ValueError(f"id가 '{tx_id}'인 거래 내역을 찾을 수 없습니다.")


class BudgetService:
    @staticmethod
    def set_budget(month: str, amount: int) -> None:
        b = Budget(month=month, amount=amount)
        budgets = list(read_stream('budgets'))
        
        updated = False
        for bd in budgets:
            if bd.get('month') == month:
                bd['amount'] = b.amount
                updated = True
                break
                
        if not updated:
            budgets.append(b.__dict__)
            
        rewrite_records('budgets', iter(budgets))

    @staticmethod
    def get_budget(month: str) -> Optional[int]:
        for bd in read_stream('budgets'):
            if bd.get('month') == month:
                return bd.get('amount')
        return None

class SummaryService:
    @staticmethod
    @time_logger
    def get_monthly_summary(month: str) -> Dict[str, Any]:
        """스트리밍 데이터를 활용해 특정 월의 요약 통계(수입/지출/카테고리별 합계)를 계산합니다."""
        total_income = 0
        total_expense = 0
        category_expenses = {}

        for tx in read_stream('transactions'):
            if tx.get('date', '').startswith(month): # 'YYYY-MM' 매칭
                amt = tx.get('amount', 0)
                if tx.get('type') == 'income':
                    total_income += amt
                elif tx.get('type') == 'expense':
                    total_expense += amt
                    cat = tx.get('category', '기타')
                    category_expenses[cat] = category_expenses.get(cat, 0) + amt

        return {
            "income": total_income,
            "expense": total_expense,
            "balance": total_income - total_expense,
            "category_expenses": category_expenses
        }