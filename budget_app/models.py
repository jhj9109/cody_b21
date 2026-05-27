import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Literal

from budget_app.validators import (
    validate_date_format,
    validate_month_format,
    validate_not_blank,
    validate_positive_number,
    validate_tags,
    validate_transaction_id,
    validate_transaction_type,
)

# 타입 힌트를 위한 커스텀 타입 정의
TransactionType = Literal["income", "expense"]


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
        validate_transaction_id(self.id)
        validate_transaction_type(self.type)
        validate_date_format(self.date)
        validate_positive_number(self.amount, "금액(amount)", allow_zero=False)
        validate_not_blank(self.category, "카테고리")
        if self.memo is not None:
            validate_not_blank(self.memo, "메모")
        if self.tags is not None:
            validate_tags(self.tags)

    def __lt__(self, other: "Transaction") -> bool:
        """heapq 연산 시 객체 스스로 날짜(최우선)와 ID를 기준으로 비교하게 만듭니다."""
        return self.date < other.date

    @property
    def id_number(self) -> int:
        """
        'TX-123456' 형태의 ID에서 하이픈(-) 뒷부분의 숫자만 추출하여 정수(int)로 반환합니다.
        """
        # 하이픈(-)을 기준으로 문자열을 쪼갠 뒤 뒤쪽('123456')만 가져와 정수 변환
        return int(self.id.split("-")[1])


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
        validate_positive_number(self.amount, "예산(amount)", allow_zero=False)
        validate_month_format(self.month)


@dataclass
class UpdateTransactionData:
    """
    거래 내역(수입/지출)을 표현하는 데이터 모델입니다.
    """

    id: str
    type: Optional[str]
    date: Optional[str]
    amount: Optional[int]
    category: Optional[str]
    memo: Optional[str]
    tags: Optional[list[str]]

    def __post_init__(self):

        exist_update_data = False
        validate_transaction_id(self.id)
        if self.type is not None:
            validate_transaction_type(self.type)
            exist_update_data = True
        if self.date is not None:
            validate_date_format(self.date)
            exist_update_data = True
        if self.amount is not None:
            validate_positive_number(self.amount, "금액", allow_zero=False)
            exist_update_data = True
        if self.category is not None:
            validate_not_blank(self.category, "카테고리")
            exist_update_data = True
        if self.memo is not None:
            exist_update_data = True
        if self.tags is not None:
            validate_tags(self.tags)
            exist_update_data = True

        if not exist_update_data:
            raise ValueError(
                "수정할 항목(--amount, --category 등)을 최소 하나 이상 지정해야 합니다."
            )

    def __lt__(self, other: "Transaction") -> bool:
        """heapq 연산 시 객체 스스로 날짜(최우선)와 ID를 기준으로 비교하게 만듭니다."""
        return self.date < other.date

    @property
    def id_number(self) -> int:
        """
        'TX-123456' 형태의 ID에서 하이픈(-) 뒷부분의 숫자만 추출하여 정수(int)로 반환합니다.
        """
        # 하이픈(-)을 기준으로 문자열을 쪼갠 뒤 뒤쪽('123456')만 가져와 정수 변환
        return int(self.id.split("-")[1])

    @property
    def update_data(self) -> int:
        update_data = dict()
        if self.type is not None:
            update_data["type"] = self.type
        if self.date is not None:
            update_data["date"] = self.date
        if self.amount is not None:
            update_data["amount"] = self.amount
        if self.category is not None:
            update_data["category"] = self.category
        if self.memo is not None:
            update_data["memo"] = self.memo.strip() if self.memo.strip() else None
        if self.tags is not None:
            update_data["tags"] = self.tags
        return update_data
