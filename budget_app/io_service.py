import csv
import os
from typing import Optional, Tuple

from .services import TransactionService, CategoryService
from .models import ExportCommandData, Transaction  # 🌟 Transaction 객체 임포트
from .validators import parse_and_validate_int  # 🌟 안전한 정수 변환기 임포트

CSV_FIELDNAMES = ["date", "type", "category", "amount", "memo", "tags"]


def parse_strs(strs: str, filter_empty=True) -> list[str]:
    result = []
    for s in strs.split(","):
        cleaned = s.strip()
        if not filter_empty or cleaned:
            result.append(cleaned)
    return result


class IOService:
    @staticmethod
    def export_csv(cmd_data: ExportCommandData) -> int:
        """조건에 맞는 거래 내역을 CSV 파일로 내보냅니다."""

        start_date, end_date = cmd_data.effective_date_range

        records = TransactionService.search(from_date=start_date, to_date=end_date)
        count = 0

        # 요구사항 완벽 충족: UTF-8 인코딩, newline="" 처리
        with open(cmd_data.out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()  # 필수 헤더 포함

            for tx in records:
                writer.writerow(
                    {
                        "date": tx.date,
                        "type": tx.type,
                        "category": tx.category,
                        "amount": tx.amount,
                        "memo": tx.memo or "",  # None일 경우 빈 문자열로 내보내기
                        "tags": ",".join(tx.tags) if tx.tags else "",  # 쉼표로 조인
                    }
                )
                count += 1

        return count

    @staticmethod
    def import_csv(from_path: str) -> Tuple[int, int]:
        """CSV 파일을 읽어 거래 내역을 일괄 등록합니다."""
        if not os.path.exists(from_path):
            raise ValueError(f"파일을 찾을 수 없습니다: {from_path}")

        valid_categories = CategoryService.get_all()
        imported_count = 0
        skipped_count = 0

        with open(from_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    category = row["category"].strip()
                    if category not in valid_categories:
                        raise ValueError("카테고리 없어서 스킵")
                        # CategoryService.add(category)
                        # valid_categories.append(category)

                    tags_raw = row.get("tags", "")
                    parse_strs(tags_raw, filter_empty=True)
                    tags = parse_strs(tags_raw, filter_empty=True) or None

                    memo_raw = row.get("memo", "").strip()
                    memo = memo_raw or None

                    amount = parse_and_validate_int(row["amount"], "CSV 금액")

                    tx = Transaction(
                        id="TX-000000",  # 임시 ID 주입
                        type=row["type"].strip(),
                        date=row["date"].strip(),
                        amount=amount,
                        category=category,
                        memo=memo,
                        tags=tags,
                    )

                    TransactionService.add(tx)

                    imported_count += 1
                except Exception as e:
                    skipped_count += 1

        return imported_count, skipped_count
