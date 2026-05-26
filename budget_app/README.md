# 💰 콘솔 가계부 프로젝트 (Budget App)

파일 입출력 기반으로 동작하는 콘솔 가계부 서비스입니다. 
제너레이터를 활용한 대용량 데이터 스트리밍 처리와 데코레이터를 이용한 안전한 예외 처리가 적용되어 있습니다.

## 🚀 실행 방법

이 프로그램은 Python 모듈 형태로 실행됩니다. (Python 3.10 이상 필요)

```bash
# 도움말 및 전체 명령어 확인
python -m budget_app --help
```

주요 명령어 예시거래 추가: python -m budget_app add (대화형 입력 진행)목록 조회: python -m budget_app list --limit 10카테고리 추가: python -m budget_app category add예산 설정: python -m budget_app budget set --month 2024-01 --amount 500000월별 요약: python -m budget_app summary --month 2024-01 --top 3데이터 내보내기: python -m budget_app export --out backup.csv --month 2024-01📂 저장 파일 위치 및 형식모든 데이터는 애플리케이션 실행 시 ./data 폴더가 자동 생성되며, JSONL(JSON Lines) 형식으로 영구 저장됩니다.수정 및 삭제 시에는 원본 보호를 위해 임시 파일을 이용한 원자적 교체(Atomic Rename) 방식을 사용합니다.transactions.jsonl : 전체 수입/지출 거래 내역categories.jsonl : 카테고리 목록budgets.jsonl : 월별 예산 데이터📊 Import/Export CSV 스키마import와 export 기능 사용 시 CSV 파일은 아래의 규격을 따릅니다. (UTF-8, 헤더 포함)columnrequired설명dateYYYYY-MM-DDtypeYincome / expensecategoryY등록된 카테고리amountY양수 정수memoN문자열tagsN쉼표(,) 구분 문자열
---

🎉 **축하합니다!** 이제 요구사항의 모든 조건을 충족하는 견고한 아키텍처의 콘솔 애플리케이션이 완성되었습니다. 터미널을 열고 `python -m budget_app add`부터 하나씩 테스트해 보시길 바랍니다. 

실행 시 발생하는 에러나 추가로 구현해 보고 싶은 보너스 기능이 있다면 언제든지 질문해 주세요!