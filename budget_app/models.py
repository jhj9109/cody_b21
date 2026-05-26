from dataclasses import dataclass, field
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
    tags: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        """데이터 객체 생성 직후 간단한 무결성 검증을 수행합니다."""
        if self.amount <= 0:
            raise ValueError("금액(amount)은 양수여야 합니다.")
        if self.type not in ('income', 'expense'):
            raise ValueError("타입(type)은 'income' 또는 'expense'만 가능합니다.")

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