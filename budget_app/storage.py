import os
import json
import tempfile
from typing import Iterator, Dict, Any

# 기본 저장 폴더 및 파일명 설정
DEFAULT_DATA_DIR = "./data"
FILE_NAMES = {
    "transactions": "transactions.jsonl",
    "categories": "categories.jsonl",
    "budgets": "budgets.jsonl"
}

def init_storage(data_dir: str = DEFAULT_DATA_DIR) -> None:
    """
    저장소 디렉토리와 필수 파일(3개)이 없으면 초기화하여 생성합니다.
    """
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    for file_key, file_name in FILE_NAMES.items():
        path = os.path.join(data_dir, file_name)
        if not os.path.exists(path):
            # 빈 파일 생성
            with open(path, 'w', encoding='utf-8') as f:
                pass
    
    # [저장 정책] 카테고리 파일이 비어있으면 기본값 자동 주입
    cat_path = os.path.join(data_dir, FILE_NAMES["categories"])
    
    # 파일 크기가 0이거나 내용이 없으면 실행
    if os.path.exists(cat_path) and os.path.getsize(cat_path) == 0:
        default_categories = ["food", "transport", "rent", "etc"]
        
        # append_record 함수를 재사용하지 않고, 초기 생성 시 한 번에 쓰기
        with open(cat_path, 'w', encoding='utf-8') as f:
            for cat in default_categories:
                record = {"name": cat}
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

def read_stream(file_key: str, data_dir: str = DEFAULT_DATA_DIR) -> Iterator[Dict[str, Any]]:
    """
    [핵심] 제너레이터(yield) 기반 스트리밍 읽기.
    파일 전체를 메모리에 올리지 않고 한 줄씩 읽어서 반환합니다.
    대용량 파일 조회(list, search) 시 메모리 부족을 방지합니다.
    """
    path = os.path.join(data_dir, FILE_NAMES[file_key])
    if not os.path.exists(path):
        return

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def append_record(file_key: str, record: Dict[str, Any], data_dir: str = DEFAULT_DATA_DIR) -> None:
    """
    파일 끝에 단일 레코드를 추가합니다 (데이터 추가용).
    """
    path = os.path.join(data_dir, FILE_NAMES[file_key])
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

def rewrite_records(file_key: str, records: Iterator[Dict[str, Any]], data_dir: str = DEFAULT_DATA_DIR) -> None:
    """
    [보너스 기능 적용] 임시 파일을 활용한 원자적 덮어쓰기(Atomic Rewrite).
    수정(update)이나 삭제(delete) 시 사용합니다. 
    작업 도중 프로그램이 강제 종료되어도 원본 파일이 날아가지 않도록 보호합니다.
    """
    path = os.path.join(data_dir, FILE_NAMES[file_key])
    
    # 임시 파일 생성
    temp_fd, temp_path = tempfile.mkstemp(dir=data_dir, text=True)
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                
        # 운영체제 단에서 원자적(Atomic)으로 원본 파일과 교체 (Rename)
        os.replace(temp_path, path)
    except Exception as e:
        # 에러 발생 시 찌꺼기 임시 파일 삭제 후 에러 전파
        os.remove(temp_path)
        raise e