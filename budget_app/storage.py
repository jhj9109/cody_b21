import os
import json
import tempfile
from typing import Iterator, Dict, Any
import zipfile
import shutil
import datetime

from budget_app.models import Transaction

# 기본 저장 폴더 및 파일명 설정
DEFAULT_DATA_DIR = "./data"
FILE_NAMES = {
    "transactions": "transactions.jsonl",
    "categories": "categories.jsonl",
    "budgets": "budgets.jsonl",
    "recurring": "recurring.jsonl",
}
DEFAULT_CATEGORIES = ["food", "transport", "rent", "etc"]
DEFAULT_RECURRING_RULE = {
    "id": "REC-001",
    "type": "expense",
    "amount": 50000,
    "category": "rent",
    "memo": "자동기입 월세 테스트",
    "tags": ["monthly"],
}
_current_data_dir = DEFAULT_DATA_DIR

BACKUP_TRIGGERS = ["add", "update", "delete", "import", "budget", "category"]
RECURRING_TRIGGERS = [
    "add",
    "update",
    "delete",
    "list",
    "summary",
    "search",
    "export",
    "budget",
]


def set_data_dir(path: str) -> None:
    """CLI 컨틀로러 계층에서 파싱된 경로를 저장소 엔진에 주입(Injection)하는 함수"""
    global _current_data_dir
    if path:
        _current_data_dir = path


def get_data_path(file_key: str) -> str:
    """설정된 저장 폴더 경로와 파일명을 결합하여 최종 절대/상대 경로를 반환"""
    return os.path.join(_current_data_dir, FILE_NAMES[file_key])


def process_recurring_transactions() -> None:
    """
    [간소화된 로직] 반복 내역 규칙을 읽어와 매월 1일 자 기준으로 자동 기입합니다.
    - 멱등성 보장: 이번 달에 이미 기입된 규칙은 건너뜁니다.
    """
    path = get_data_path("recurring")
    if not os.path.exists(path):
        return

    rules = list(read_stream("recurring"))
    if not rules:
        return

    # 말일(last_day)이나 현재 일자(current_day) 계산 로직 전체 삭제
    today = datetime.date.today()
    current_month = today.strftime("%Y-%m")

    applied_rules = set()
    max_id_num = 0

    # 1. 이번 달에 이미 적용된 규칙 식별자 수집 & ID 최댓값 찾기
    for tx_dict in read_stream("transactions"):
        tx = Transaction(**tx_dict)
        try:
            num = int(tx.id.split("-")[1])
            max_id_num = max(max_id_num, num)
        except (ValueError, IndexError, KeyError):
            pass

        # 멱등성: 이번 달 데이터 중 시스템 태그(sys:REC-)가 있는지 확인
        if tx.date.startswith(current_month) and tx.tags:
            for tag in tx.tags:
                if tag.startswith("sys:REC-"):
                    applied_rules.add(tag)

    new_records = []

    # 2. 규칙 평가 및 새 내역 생성 (조건 없이 1일 자로 고정)
    for rule in rules:
        rule_id = rule["id"]  # 예: REC-000001
        system_tag = f"sys:{rule_id}:{current_month}"

        # 엣지케이스 방어: 이미 이번 달에 기입된 규칙이면 패스 (멱등성 유지)
        if system_tag in applied_rules:
            continue

        # 날짜 비교(current_day >= target_day) 삭제. 루프에 진입하면 즉시 생성
        max_id_num += 1
        new_tx_id = f"TX-{max_id_num:06d}"

        tags = rule.get("tags", [])
        if system_tag not in tags:
            tags.append(system_tag)

        record = {
            "id": new_tx_id,
            "type": rule["type"],
            "date": f"{current_month}-01",  # 🌟 날짜를 매월 1일로 완벽히 고정
            "amount": rule["amount"],
            "category": rule["category"],
            "memo": rule.get("memo", ""),
            "tags": tags,
        }
        new_records.append(record)

    # 3. 새로 발생한 내역이 있다면 트랜잭션 파일에 일괄 추가
    for record in new_records:
        append_record("transactions", record)


def make_base_files(data_dir: str) -> None:
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    for file_key in FILE_NAMES.keys():
        path = get_data_path(file_key)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                pass


def set_default_category(path: str, categories: list[str] = DEFAULT_CATEGORIES) -> None:
    if os.path.exists(path) and os.path.getsize(path) == 0:
        with open(path, "w", encoding="utf-8") as f:
            for cat in categories:
                record = {"name": cat}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def set_default_recurring_rule(
    path: str, recurring_rule: Dict[str, Any] = DEFAULT_RECURRING_RULE
):
    if os.path.exists(path) and os.path.getsize(path) == 0:
        with open("./data/recurring.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps(recurring_rule, ensure_ascii=False) + "\n")


def run_auto_process(cmd: str, data_dir: str) -> None:
    if cmd in RECURRING_TRIGGERS:
        try:
            process_recurring_transactions()
        except Exception as e:
            print(f"자동작업 문제 발생:{e}")
    if cmd in BACKUP_TRIGGERS:
        try:
            backup_data(data_dir, is_auto=True)
        except Exception as e:
            print(f"자동백업과정에서 문제 발생:{e}")


def init_storage(cmd: str) -> None:
    """
    저장소 디렉토리와 필수 파일을 초기화하고,
    마지막에 조용히 자동 백업을 수행합니다.
    """
    data_dir = _current_data_dir
    make_base_files(data_dir)
    set_default_category(get_data_path("categories"))
    set_default_recurring_rule(get_data_path("recurring"))
    run_auto_process(cmd, data_dir)


def read_stream(file_key: str) -> Iterator[Dict[str, Any]]:
    """
    [핵심] 제너레이터(yield) 기반 스트리밍 읽기.
    파일 전체를 메모리에 올리지 않고 한 줄씩 읽어서 반환합니다.
    대용량 파일 조회(list, search) 시 메모리 부족을 방지합니다.
    """
    path = get_data_path(file_key)
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def append_record(file_key: str, record: Dict[str, Any]) -> None:
    """파일 끝에 단일 레코드를 추가합니다 (데이터 추가용)."""
    path = get_data_path(file_key)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def rewrite_records(file_key: str, records: Iterator[Dict[str, Any]]) -> None:
    """임시 파일을 활용한 원자적 덮어쓰기(Atomic Rewrite)."""

    path = get_data_path(file_key)

    temp_fd, temp_path = tempfile.mkstemp(dir=_current_data_dir, text=True)

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        os.replace(
            temp_path, path
        )  # 운영체제 단에서 원자적(Atomic)으로 원본 파일과 교체 (Rename)

    except Exception as e:
        # 예외가 터지면 디스크 청소를 위해 찌꺼기 임시 파일을 먼저 안전하게 삭제합니다.
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # 'from e' 구문을 붙여주면 원본 에러의 컨텍스트(디스크 풀, 권한 오류 등)를 유실하지 않아 디버깅에 유리합니다.
        raise RuntimeError(
            f"가계부 데이터 영구 저장(원자적 반영) 중 예측할 수 없는 디스크 또는 파일 IO 오류가 발생했습니다.\n"
            f"[대상 파일]: {file_key} ({os.path.basename(path)})\n"
            f"[상세 원인]: {str(e)}\n"
            f"[힌트]: 현재 저장 디렉토리의 쓰기 권한이 유효한지, 혹은 디스크 용량이 가득 차지 않았는지 확인해 주세요."
        ) from e


def backup_data(out_dir: str, is_auto: bool = False) -> str:
    """데이터 파일 3개를 ZIP으로 압축하여 백업합니다."""
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if is_auto:
        filename = "auto_backup.zip"
    else:
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"budget_backup_{now}.zip"

    final_path = os.path.join(out_dir, filename)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".zip")
    os.close(temp_fd)

    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_key, real_filename in FILE_NAMES.items():
                source_path = get_data_path(file_key)
                if os.path.exists(source_path):
                    zf.write(source_path, arcname=real_filename)
        os.replace(temp_path, final_path)
        return final_path
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"백업 생성 중 디스크 오류가 발생했습니다: {e}")


def restore_data(from_path: str) -> None:
    """지정된 백업(ZIP) 파일에서 데이터를 복구합니다."""
    temp_dir = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(from_path, "r") as zf:
            zf.extractall(temp_dir)

        for file_key, filename in FILE_NAMES.items():
            extracted_path = os.path.join(temp_dir, filename)
            if not os.path.exists(extracted_path):
                raise ValueError(f"손상된 백업입니다. 필수 데이터 '{filename}' 누락.")

        for file_key, filename in FILE_NAMES.items():
            extracted_path = os.path.join(temp_dir, filename)
            target_path = get_data_path(file_key)
            os.replace(extracted_path, target_path)
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
