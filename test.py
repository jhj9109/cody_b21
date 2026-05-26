import subprocess
import argparse
import time
import os
import shutil
import sys

def run_cmd(args_list, input_data=None):
    """CLI 명령어를 실행하고 결과를 출력하는 헬퍼 함수입니다."""
    cmd = [sys.executable, "-m", "budget_app"] + args_list
    print(f"\033[93m> {' '.join(cmd)}\033[0m")
    
    result = subprocess.run(
        cmd,
        input=input_data,
        text=True,
        capture_output=True,
        encoding='utf-8'
    )
    
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(f"\033[91m{result.stderr.strip()}\033[0m")
    print("-" * 50)
    return result

def wait_for_user(step_name, is_step_mode):
    """옵션에 따라 사용자의 엔터 입력을 기다리거나 바로 진행합니다."""
    if is_step_mode:
        input(f"\n\033[96m[엔터(Enter)를 누르면 '{step_name}' 단계를 진행합니다...]\033[0m")
    else:
        print(f"\n\033[96m=== {step_name} ===\033[0m")
        time.sleep(0.5)

def main():
    parser = argparse.ArgumentParser(description="가계부 앱 자동 테스트 스크립트")
    parser.add_argument('--step', action='store_true', help='단계별로 엔터 키 입력을 기다리며 진행합니다.')
    args = parser.parse_args()

    is_step = args.step

    print("🚀 가계부 앱(budget_app) 테스트를 시작합니다.")
    
    # 0. 테스트 환경 초기화 (기존 데이터 삭제)
    wait_for_user("0. 테스트 환경 초기화", is_step)
    if os.path.exists("./data"):
        shutil.rmtree("./data")
        print("기존 './data' 폴더를 삭제하여 깨끗한 상태에서 시작합니다.")
    if os.path.exists("test_export.csv"):
        os.remove("test_export.csv")

    # 1. 카테고리 등록 (필수 선행 조건)
    wait_for_user("1. 카테고리 등록 테스트", is_step)
    # 대화형 입력 흉내내기: "food\n"을 전달
    run_cmd(["category", "add"], input_data="food\n")
    run_cmd(["category", "add"], input_data="transport\n")
    run_cmd(["category", "add"], input_data="salary\n")

    # 2. 카테고리 목록 조회
    wait_for_user("2. 카테고리 목록 조회 테스트", is_step)
    run_cmd(["category", "list"])

    # 3. 예산 설정
    wait_for_user("3. 1월 예산 설정 테스트", is_step)
    run_cmd(["budget", "set", "--month", "2024-01", "--amount", "500000"])

    # 4. 수입/지출 내역 추가 (대화형 입력 시뮬레이션)
    wait_for_user("4. 거래 내역 추가 테스트", is_step)
    # 수입 추가 (날짜, 타입, 카테고리, 금액, 메모, 태그 순서대로 줄바꿈으로 구분)
    income_input = "2024-01-10\nincome\nsalary\n3000000\n1월 월급\nincome,salary\n"
    run_cmd(["add"], input_data=income_input)

    # 지출 추가 1
    expense_input1 = "2024-01-12\nexpense\ntransport\n20000\n택시비\ntaxi\n"
    run_cmd(["add"], input_data=expense_input1)

    # 지출 추가 2
    expense_input2 = "2024-01-15\nexpense\nfood\n15000\n점심 식사\nmeal\n"
    run_cmd(["add"], input_data=expense_input2)

    # 5. 거래 내역 목록 조회
    wait_for_user("5. 거래 내역 목록(list) 테스트", is_step)
    run_cmd(["list", "--limit", "10"])

    # 6. 월별 요약 조회 (예산 연동 확인)
    wait_for_user("6. 월별 요약(summary) 테스트", is_step)
    run_cmd(["summary", "--month", "2024-01", "--top", "3"])

    # 7. CSV로 내보내기 (Export)
    wait_for_user("7. 데이터 내보내기(export) 테스트", is_step)
    run_cmd(["export", "--out", "test_export.csv", "--month", "2024-01"])

    # 8. 거래 내역 삭제
    wait_for_user("8. 특정 거래 내역 삭제(delete) 테스트", is_step)
    # 초기화 후 첫 데이터이므로 ID는 무조건 TX-000001 입니다.
    run_cmd(["delete", "--id", "TX-000001"])
    run_cmd(["list", "--limit", "5"]) # 삭제 확인용 리스트 조회

    # 9. CSV에서 가져오기 (Import)
    wait_for_user("9. 데이터 가져오기(import) 테스트", is_step)
    run_cmd(["import", "--from", "test_export.csv"])
    run_cmd(["list", "--limit", "10"]) # 복구 확인용 리스트 조회

    print("\n🎉 모든 테스트가 완료되었습니다!")

if __name__ == '__main__':
    main()