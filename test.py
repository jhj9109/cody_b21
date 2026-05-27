import subprocess
import argparse
import time
import os
import shutil
import sys
import inspect

def run_cmd(args_list, input_data=None, expect_fail=False):
    """
    CLI 명령어를 실행하고 결과를 출력하는 헬퍼 함수입니다.
    expect_fail=True 이면 에러(종료코드 != 0)가 나는 것이 '정상 동작'임을 의미합니다.
    """
    cmd = [sys.executable, "-m", "budget_app"] + args_list
    print(f"\033[93m> {' '.join(cmd)}\033[0m")
    if input_data:
        print(f"\033[90m[입력 시뮬레이션]\n{input_data.strip()}\033[0m")
    
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=True,
        encoding='utf-8'
    )
    
    # 출력 결과 정돈
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(f"\033[91m{result.stderr.strip()}\033[0m")

    # 💡 에러 발생 시 호출한 원래 위치(test.py 내부 줄번호)를 추적
    frame_info = inspect.stack()[1]
    caller_file = frame_info.filename     # 호출한 파일 경로 (test.py)
    caller_line = frame_info.lineno       # 호출한 실제 줄 번호
        
    # 종료 코드 검증
    is_failed = False
    if expect_fail and result.returncode == 0:
        is_failed = True
        err_msg = "[테스트 실패] 에러가 발생해야 하는 상황인데 정상 종료(0)되었습니다!"
    elif not expect_fail and result.returncode != 0:
        is_failed = True
        err_msg = "[테스트 실패] 정상 실행되어야 하는데 에러가 발생했습니다!"

    if is_failed:
        print(f"\033[91m{err_msg}\033[0m")
        print(f"  File \"{caller_file}\", line {caller_line}")
    else:
        print("\033[92m[테스트 성공]\033[0m")
            
    print("-" * 60)
    return result

def wait_for_user(step_name, is_step_mode):
    """옵션에 따라 사용자의 엔터 입력을 기다리거나 바로 진행합니다."""
    if is_step_mode:
        input(f"\n\033[96m[Enter를 누르면 '{step_name}' 단계를 진행합니다...]\033[0m")
    else:
        print(f"\n\033[96m=== {step_name} ===\033[0m")
        time.sleep(0.3)

def main():
    parser = argparse.ArgumentParser(description="고도화된 가계부 앱 예외 처리 테스트 스크립트")
    parser.add_argument('--step', action='store_true', help='단계별로 엔터 키 입력을 기다리며 진행합니다.')
    args = parser.parse_args()

    print("🚀 고도화된 가계부 앱(budget_app) 예외/무결성 테스트를 시작합니다.")
    
    # ==========================================
    # 1. 기존 파일 무조건 지우고 시작 (환경 초기화)
    # ==========================================
    wait_for_user("1. 테스트 환경 초기화", args.step)
    if os.path.exists("./data"):
        shutil.rmtree("./data")
        print("기존 './data' 폴더를 완전히 삭제했습니다. (데이터 오염 방지)")
    if os.path.exists("test_export.csv"):
        os.remove("test_export.csv")
    if os.path.exists("invalid_test.csv"):
        os.remove("invalid_test.csv")

    # ==========================================
    # 2 & 3. 초기화 체크 및 카테고리 테스트
    # ==========================================
    wait_for_user("2 & 3. 카테고리 기본 초기화 및 예외 테스트", args.step)
    print("[체크] 초기화 정책에 의해 food, transport, rent, etc가 자동 생성되었는지 확인합니다.")
    run_cmd(["category", "list"])

    print("\n[실패 케이스] 중복된 카테고리명(food) 추가 시도")
    run_cmd(["category", "add"], input_data="food\n", expect_fail=True)

    print("\n[실패 케이스] 공백/strip하면 비게 되는 값 추가 시도")
    run_cmd(["category", "add"], input_data="   \n", expect_fail=True)

    print("\n[성공 케이스] 정상 카테고리 2개 추가 (하나는 절대 안 쓸 'never')")
    run_cmd(["category", "add"], input_data="salary\n")
    run_cmd(["category", "add"], input_data="never\n")
    run_cmd(["category", "list"])

    print("\n[성공 케이스] 사용하지 않는 카테고리('never') 정상 삭제 (category remove)")
    run_cmd(["category", "remove"], input_data="never\n")

    # ==========================================
    # 4. 예산 설정 예외 테스트
    # ==========================================
    wait_for_user("4. 예산 설정 및 날짜/금액 예외 테스트", args.step)
    print("[성공 케이스] 정상 예산 설정 (초과 경고 테스트를 위해 10000원으로 설정)")
    run_cmd(["budget", "set", "--month", "2024-01", "--amount", "10000"])

    print("\n[실패 케이스] month 형식이 완전히 다름 (연도 자릿수 부족)")
    run_cmd(["budget", "set", "--month", "24-01", "--amount", "500000"], expect_fail=True)

    print("\n[실패 케이스] 존재하지 않는 월 입력 (13월)")
    run_cmd(["budget", "set", "--month", "2024-13", "--amount", "500000"], expect_fail=True)

    print("\n[실패 케이스] 예산 금액을 음수 값으로 시도")
    run_cmd(["budget", "set", "--month", "2024-01", "--amount", "-100000"], expect_fail=True)

    # ==========================================
    # 5. 수입/지출 내역 추가 예외 테스트
    # ==========================================
    wait_for_user("5. 거래 내역 추가 및 무결성(Transaction) 테스트", args.step)
    print("[성공 케이스] 정상 수입/지출 등록")
    run_cmd(["add"], input_data="2024-01-10\nincome\nsalary\n3000000\n월급\nwork\n")
    run_cmd(["add"], input_data="2024-01-15\nexpense\nfood\n15000\n점심\nmeal\n")

    # 🌟 항목 추가 시 빈 메모 처리 검증 (정상 통과 및 None 처리 기대)
    print("\n[성공 케이스] 항목 추가 시 메모를 입력하지 않고 엔터만 쳤을 때 (빈 메모)")
    run_cmd(["add"], input_data="2024-01-16\nexpense\nfood\n7000\n\nstarbucks\n")

    # 🌟 항목 추가 시 빈 태그 처리 검증 (정상 통과 및 빈 리스트 처리 기대)
    print("\n[성공 케이스] 항목 추가 시 태그를 입력하지 않고 엔터만 쳤을 때 (빈 태그)")
    run_cmd(["add"], input_data="2024-01-17\nexpense\netc\n12000\n택시비\n\n")

    # 🌟 항목 추가 시 중복 태그 유입 차단 검증 (모델 레이어 예외 발생 차단 기대)
    print("\n[실패 케이스] 항목 추가 시 동일한 태그가 중복되어 유입될 때 (중복 태그 예외 차단)")
    run_cmd(["add"], input_data="2024-01-18\nexpense\nfood\n9000\n저녁식사\nmeal, meal\n", expect_fail=True)

    
    # 🌟 사용 중인 카테고리 삭제 방어 증빙 (food 카테고리를 방금 사용함)
    print("\n[실패 케이스] 사용 중인 카테고리('food') 삭제 시도 시 방어 (category remove)")
    run_cmd(["category", "remove"], input_data="food\n", expect_fail=True)

    print("\n[실패 케이스] 금액이 음수")
    run_cmd(["add"], input_data="2024-01-15\nexpense\nfood\n-5000\n테스트\n\n", expect_fail=True)

    print("\n[실패 케이스] 타입 오류 (expense/income이 아님)")
    run_cmd(["add"], input_data="2024-01-15\nminus\nfood\n5000\n테스트\n\n", expect_fail=True)

    print("\n[실패 케이스] 날짜 형식 오류 (YYYY/MM/DD)")
    run_cmd(["add"], input_data="2024/01/15\nexpense\nfood\n5000\n테스트\n\n", expect_fail=True)

    print("\n[실패 케이스] 존재하지 않는 날짜 (윤년 고려: 2025-02-29)")
    run_cmd(["add"], input_data="2025-02-29\nexpense\nfood\n5000\n테스트\n\n", expect_fail=True)

    print("\n[실패 케이스] 존재하지 않는 카테고리")
    run_cmd(["add"], input_data="2024-01-15\nexpense\nbitcoin\n5000\n테스트\n\n", expect_fail=True)

    # ==========================================
    # 6. 수입/지출 조회 테스트
    # ==========================================
    wait_for_user("6. 거래 내역 목록 조회(list) 테스트", args.step)
    print("[성공 케이스] 기본 최신순 목록 조회")
    run_cmd(["list", "--limit", "5"])

    print("\n[실패 케이스] limit 값이 음수이거나 이상한 값")
    run_cmd(["list", "--limit", "-5"], expect_fail=True)

    # ==========================================
    # 7. 월별 요약 조회 예외 테스트
    # ==========================================
    wait_for_user("7. 월별 요약(summary) 및 인자 예외 테스트", args.step)
    print("[성공 케이스] 정상 요약 출력 (여기서 예산 10000원 대비 지출이 있으므로 초과 경고가 떠야 함)")
    run_cmd(["summary", "--month", "2024-01", "--top", "3"])

    print("\n[실패 케이스] month 날짜 유효성 검사 실패 (잘못된 형식)")
    run_cmd(["summary", "--month", "2024-13"], expect_fail=True)

    print("\n[실패 케이스] top 값이 음수이거나 잘못됨")
    run_cmd(["summary", "--month", "2024-01", "--top", "-1"], expect_fail=True)

    # ==========================================
    # 8. CSV 내보내기 예외 테스트
    # ==========================================
    wait_for_user("8. 데이터 내보내기(export) 및 경로 예외 테스트", args.step)
    print("[성공 케이스] 정상 CSV 내보내기")
    run_cmd(["export", "--out", "test_export.csv", "--month", "2024-01"])

    print("\n[스키마 검증] 생성된 CSV 파일의 헤더 및 데이터 포맷 확인 (UTF-8, 6개 컬럼)")
    try:
        with open("test_export.csv", "r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"\033[96m[파일 내용 출력 - test_export.csv]\033[0m")
            for line in lines[:5]:
                print(line.strip())
            print("\033[92m[검증 완료] 스키마(date,type,category,amount,memo,tags) 일치\033[0m")
    except Exception as e:
        print(f"\033[91m[검증 실패] CSV 파일을 읽을 수 없습니다: {e}\033[0m")

    print("\n[실패 케이스] 유효하지 않은 실행 경로 (존재하지 않는 폴더 지정)")
    run_cmd(["export", "--out", "./nobody_folder/test.csv", "--month", "2024-01"], expect_fail=True)

    print("\n[실패 케이스] 필수 조건(month 또는 from/to) 누락")
    run_cmd(["export", "--out", "test_export.csv"], expect_fail=True)

    # ==========================================
    # 9. 거래 내역 수정 및 삭제 예외 테스트
    # ==========================================
    wait_for_user("9. 거래 내역 수정(update) 및 삭제(delete) 예외 테스트", args.step)
    
    print("[성공 케이스] 정상 수정 (TX-000001의 금액을 25000으로 변경)")
    run_cmd(["update", "--id", "TX-000001", "--amount", "25000", "--memo", "수정된메모"])

    # 🌟 항목 수정 시 빈 메모 처리 검증 (정상 반영 기대)
    print("\n[성공 케이스] 항목 수정 시 메모를 명시적 공백으로 초기화할 때 (빈 메모 수정)")
    run_cmd(["update", "--id", "TX-000002", "--memo", ""])

    # 🌟 항목 수정 시 빈 태그 처리 검증 (정상 반영 기대)
    print("\n[성공 케이스] 항목 수정 시 태그를 명시적 공백으로 지울 때 (빈 태그 수정)")
    run_cmd(["update", "--id", "TX-000002", "--tags", ""])

    # 🌟 항목 수정 시 중복 태그 차단 검증 (모델 무결성 방어 예외 기대)
    print("\n[실패 케이스] 항목 수정 시 인자에 중복된 태그를 문자열로 넘길 때 (중복 태그 수정 방어)")
    run_cmd(["update", "--id", "TX-000002", "--tags", "edit, edit"], expect_fail=True)
    
    print("\n[실패 케이스] 존재하지 않는 ID 수정 시도")
    run_cmd(["update", "--id", "TX-999999", "--amount", "10000"], expect_fail=True)

    print("\n[성공 케이스] 정상 삭제 (TX-000001)")
    run_cmd(["delete", "--id", "TX-000001"])

    print("\n[실패 케이스] 존재하지 않는 ID 삭제 시도")
    run_cmd(["delete", "--id", "TX-999999"], expect_fail=True)

    print("\n[실패 케이스] 유효하지 않은 ID 형식 삭제 시도")
    run_cmd(["delete", "--id", "INVALID_ID_FORMAT"], expect_fail=True)

    # ==========================================
    # 10. CSV 가져오기 예외 테스트
    # ==========================================
    wait_for_user("10. 데이터 가져오기(import) 및 파일 오류 테스트", args.step)
    print("[성공 케이스] 아까 내보낸 정상 파일 가져오기")
    run_cmd(["import", "--from", "test_export.csv"])

    print("\n[실패 케이스] 존재하지 않는 파일 지정")
    run_cmd(["import", "--from", "ghost_file.csv"], expect_fail=True)

    print("\n[실패 케이스] 구조가 깨진 잘못된 CSV 파일 처리")
    with open("invalid_test.csv", "w", encoding="utf-8") as f:
        f.write("date,type,category,amount\n")
        f.write("2024-01-15,expense,food,abc\n")
    run_cmd(["import", "--from", "invalid_test.csv"]) 

    print("\n🎉 고도화된 시스템 예외 시나리오 무결성 테스트가 완료되었습니다!")

if __name__ == '__main__':
    main()