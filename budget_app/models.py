import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Literal, Tuple

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


@dataclass
class ExportCommandData:
    """Export 명령어 입력값을 검증하고 정제하는 데이터 모델"""

    out_path: str
    month: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None

    def __post_init__(self):
        # 1. 파일명 유효성 및 편의 기능
        validate_not_blank(self.out_path, "출력 파일명(--out)")
        # 확장자를 안 적었을 경우 자동으로 .csv를 붙여주는 소소한 헬퍼 기능
        if not self.out_path.lower().endswith(".csv"):
            self.out_path += ".csv"

        # 2. 필수 조건 검사
        if not (self.month or self.from_date or self.to_date):
            raise ValueError(
                "export 명령은 --month 또는 --from / --to 조건 중 하나 이상이 필수입니다."
            )

        # 3. 날짜 포맷 검증
        if self.month:
            validate_month_format(self.month)
        if self.from_date:
            validate_date_format(self.from_date)
        if self.to_date:
            validate_date_format(self.to_date)

        # 4. 논리 검증: from이 to보다 미래일 수 없음
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError(
                "시작 날짜(--from)는 종료 날짜(--to)보다 이전이어야 합니다."
            )

    @property
    def effective_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        if self.month:
            return f"{self.month}-01", f"{self.month}-31"
        return self.from_date, self.to_date


@dataclass
class ImportCommandData:
    """Import 명령어 입력값을 검증하는 데이터 모델"""

    from_path: str

    def __post_init__(self):
        validate_not_blank(self.from_path, "가져올 파일명(--from)")

        # 1. 확장자 방어
        if not self.from_path.lower().endswith(".csv"):
            raise ValueError(
                f"CSV 파일만 가져올 수 있습니다. (입력값: '{self.from_path}')"
            )

        # 2. 파일 실제 존재 여부를 객체 생성 시점에 조기 차단(Early-catch)
        if not os.path.exists(self.from_path):
            raise ValueError(f"가져올 파일을 찾을 수 없습니다: {self.from_path}")


@dataclass
class BackupCommandData:
    """Backup 명령어 입력값을 검증하는 데이터 모델"""

    out_path: str

    def __post_init__(self):
        validate_not_blank(self.out_path, "백업 대상 폴더(--out)")


@dataclass
class RestoreCommandData:
    """Restore 명령어 입력값을 검증하는 데이터 모델"""

    from_path: str

    def __post_init__(self):
        validate_not_blank(self.from_path, "가져올 백업 파일명(--from)")

        if not self.from_path.lower().endswith(".zip"):
            raise ValueError(
                f"복구는 ZIP(.zip) 형태의 백업 파일만 지원합니다. (입력값: '{self.from_path}')"
            )

        if not os.path.exists(self.from_path):
            raise ValueError(f"가져올 백업 파일을 찾을 수 없습니다: {self.from_path}")
