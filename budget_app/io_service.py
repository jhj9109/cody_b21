import csv
import os
from typing import Optional, Tuple

from .services import TransactionService, CategoryService
from .models import ExportCommandData, Transaction  # 🌟 Transaction 객체 임포트
from .validators import parse_and_validate_int  # 🌟 안전한 정수 변환기 임포트


import zipfile
import tempfile
import shutil
import datetime
from .storage import FILE_NAMES, get_data_path

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

    @staticmethod
    def backup_data(out_dir: str, is_auto: bool = False) -> str:
        """
        데이터 파일 3개를 ZIP으로 압축하여 백업합니다.
        is_auto=True 이면 고정된 이름(auto_backup.zip)으로 덮어쓰고, False이면 타임스탬프를 부여합니다.
        """
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        if is_auto:
            filename = "auto_backup.zip"
        else:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"budget_backup_{now}.zip"

        final_path = os.path.join(out_dir, filename)

        # 🌟 [안전장치 1] 임시 파일에 ZIP을 먼저 생성합니다. (도중 실패 시 찌꺼기 방지)
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
        os.close(temp_fd)

        try:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_key, real_filename in FILE_NAMES.items():
                    source_path = get_data_path(file_key)
                    if os.path.exists(source_path):
                        # 아카이브 내부에 저장될 이름은 폴더 경로를 뺀 순수 파일명으로 지정
                        zf.write(source_path, arcname=real_filename)

            # 완성된 ZIP 파일을 최종 목적지로 원자적 교체
            os.replace(temp_path, final_path)
            return final_path
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise RuntimeError(f"백업 생성 중 디스크 입출력 오류가 발생했습니다: {e}")

    @staticmethod
    def restore_data(from_path: str) -> None:
        """지정된 백업(ZIP) 파일에서 데이터를 복구합니다."""

        # 🌟 [안전장치 2] 라이브 폴더에 바로 풀지 않고, 임시 폴더에 먼저 압축을 풉니다.
        temp_dir = tempfile.mkdtemp()

        try:
            with zipfile.ZipFile(from_path, "r") as zf:
                zf.extractall(temp_dir)

            # 🌟 [안전장치 3] 무결성 검증: 압축을 푼 임시 폴더에 필수 파일 3개가 모두 존재하는지 확인
            for file_key, filename in FILE_NAMES.items():
                extracted_path = os.path.join(temp_dir, filename)
                if not os.path.exists(extracted_path):
                    raise ValueError(
                        f"손상된 백업 파일입니다. 필수 데이터 '{filename}'가 누락되었습니다."
                    )

            # 모든 유효성 검사가 끝났으므로, 실제 운영 환경 경로로 원자적 덮어쓰기 수행
            for file_key, filename in FILE_NAMES.items():
                extracted_path = os.path.join(temp_dir, filename)
                target_path = get_data_path(file_key)
                os.replace(extracted_path, target_path)

        finally:
            # 작업이 끝난 후 임시 폴더는 깔끔하게 메모리/디스크에서 청소
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
