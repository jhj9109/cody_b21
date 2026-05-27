import csv
import os
from typing import Optional, Tuple

from .services import TransactionService, CategoryService

CSV_FIELDNAMES = ['date', 'type', 'category', 'amount', 'memo', 'tags']

class IOService:
    @staticmethod
    def export_csv(out_path: str, month: Optional[str] = None, 
                   from_date: Optional[str] = None, to_date: Optional[str] = None) -> int:
        """조건에 맞는 거래 내역을 CSV 파일로 내보냅니다."""
        if not (month or from_date or to_date):
            raise ValueError("export 명령은 --month 또는 --from / --to 조건 중 하나 이상이 필수입니다.")

        # month 옵션이 들어오면 문자열 비교를 위해 from/to 날짜를 임의로 설정
        if month:
            from_date = f"{month}-01"
            to_date = f"{month}-31" 

        records = TransactionService.search(from_date=from_date, to_date=to_date)
        count = 0
        
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            
            for tx in records:
                writer.writerow({
                    'date': tx.date,
                    'type': tx.type,
                    'category': tx.category,
                    'amount': tx.amount,
                    'memo': tx.memo or '',
                    'tags': ",".join(tx.tags)
                })
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
        
        with open(from_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    category = row['category'].strip()
                    # 카테고리가 없으면 자동 생성하여 연결 오류 방지
                    if category not in valid_categories:
                        CategoryService.add(category)
                        valid_categories.append(category)
                        
                    tags_raw = row.get('tags', '')
                    tags = [t.strip() for t in tags_raw.split(',')] if tags_raw else []
                    memo = row.get('memo', '').strip() or None
                    
                    TransactionService.add(
                        date=row['date'].strip(),
                        t_type=row['type'].strip(),
                        category=category,
                        amount=int(row['amount']),
                        memo=memo,
                        tags=tags
                    )
                    imported_count += 1
                except Exception:
                    skipped_count += 1
                    
        return imported_count, skipped_count