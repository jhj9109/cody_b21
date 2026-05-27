import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Literal

# 타입 힌트를 위한 커스텀 타입 정의
TransactionType = Literal['income', 'expense']

@dataclass
class Transaction:
    """
    거래 내역(수입/지출)을 표현하는 데이터 모델입니다.
    """
    id: str
    type: TransactionType
    date: str  # 형식: YYYY-MM-DD
    amount: int
    category: str
    memo: Optional[str] = None
    tags: Optional[List[str]] = field(default_factory=list) # 인스턴스 생성시마다 새로운 동적 리스트 만들어라.

    def __post_init__(self):
        """데이터 객체 생성 직후 간단한 무결성 검증을 수행합니다."""
        # ID 형식 유효성 검증
        if not re.match(r"^TX-\d{6}$", self.id):
            raise ValueError(f"ID 형식이 가계부 규격에 맞지 않습니다. (입력값: '{self.id}')")
        # 타입 검증
        if self.type not in ('income', 'expense'):
            raise ValueError(f"타입(type)은 'income' 또는 'expense'만 가능합니다. (입력값: {self.type})")
        # 날짜 형식 검증
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", self.date):
            raise ValueError(f"날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 맞춰주세요. (입력값: '{self.date}')")
        try:
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"존재하지 않는 날짜입니다. 실제 달력에 맞는 날짜를 입력해 주세요. (입력값: '{self.date}')")
        # 금액 검증
        if self.amount <= 0:
            raise ValueError(f"금액(amount)은 양수여야 합니다. (입력값: {self.amount})")
        # 카테고리 공백 검증
        if not self.category or not self.category.strip():
            raise ValueError("카테고리는 비어있거나 공백일 수 없습니다.")

        # 태그 데이터 정밀 무결성 검사
        if self.tags:
            if any(not t.strip() for t in self.tags):
                raise ValueError(f"태그 목록에 비어있는 값이나 공백 문자가 포함되어 있습니다. (입력값: {self.tags})")
            if len(self.tags) != len(set(self.tags)):
                raise ValueError(f"태그 목록에 중복된 값이 존재합니다. 중복을 제거해 주세요. (입력값: {self.tags})")
        
        if self.memo:
            if any(not t.strip() for t in self.memo):
                raise ValueError(f"메모 목록에 비어있는 값이나 공백 문자가 포함되어 있습니다. (입력값: {self.memo})")

@dataclass
class Category:
    """
    카테고리를 표현하는 데이터 모델입니다.
    """
    name: str

@dataclass
class Budget:
    """
    월별 예산을 표현하는 데이터 모델입니다.
    """
    month: str  # 형식: YYYY-MM
    amount: int

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("예산(amount)은 0 이상이어야 합니다.")
        
        if not re.match(r"^\d{4}-\d{2}$", self.month):
            raise ValueError(f"날짜 형식이 올바르지 않습니다. YYYY-MM 형식을 맞춰주세요. (입력값: '{self.month}')")
        try:
            datetime.strptime(self.month, "%Y-%m")
        except ValueError:
            raise ValueError(f"존재하지 않는 달입니다. 실제 달력에 맞는 달을 입력해 주세요. (입력값: '{self.month}')")