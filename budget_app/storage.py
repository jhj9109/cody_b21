import os
import json
import tempfile
from typing import Iterator, Dict, Any
import zipfile
import shutil
import datetime

# 기본 저장 폴더 및 파일명 설정
DEFAULT_DATA_DIR = "./data"
FILE_NAMES = {
    "transactions": "transactions.jsonl",
    "categories": "categories.jsonl",
    "budgets": "budgets.jsonl",
}
_current_data_dir = DEFAULT_DATA_DIR


def set_data_dir(path: str) -> None:
    """CLI 컨틀로러 계층에서 파싱된 경로를 저장소 엔진에 주입(Injection)하는 함수"""
    global _current_data_dir
    if path:
        _current_data_dir = path


def get_data_path(file_key: str) -> str:
    """설정된 저장 폴더 경로와 파일명을 결합하여 최종 절대/상대 경로를 반환"""
    return os.path.join(_current_data_dir, FILE_NAMES[file_key])


def init_storage(cmd: str) -> None:
    """
    저장소 디렉토리와 필수 파일을 초기화하고,
    마지막에 조용히 자동 백업을 수행합니다.
    """
    data_dir = _current_data_dir
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    for file_key in FILE_NAMES.keys():
        path = get_data_path(file_key)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                pass

    cat_path = get_data_path("categories")
    if os.path.exists(cat_path) and os.path.getsize(cat_path) == 0:
        default_categories = ["food", "transport", "rent", "etc"]
        with open(cat_path, "w", encoding="utf-8") as f:
            for cat in default_categories:
                record = {"name": cat}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 🌟 제안해주신 의견 반영: 초기화가 모두 끝난 직후 자동 백업 트리거
    try:
        if cmd not in ["backup", "restore"]:
            backup_data(data_dir, is_auto=True)
    except Exception:
        pass  # 자동 백업 실패는 메인 로직에 영향을 주지 않도록 조용히 넘김


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
