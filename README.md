💰 콘솔 가계부 프로젝트 (Budget App)
**"작은 서비스"**란 기능이 많은 게 아니라 예외 상황에서도 데이터가 안전하고 시스템 자원을 효율적으로 쓰는 것을 말합니다. 단순한 유틸리티를 넘어 유지보수 가능한 아키텍처, 엄격한 데이터 무결성, 그리고 대용량 처리를 위한 극강의 자원 최적화를 목표로 설계된 파일 입출력 기반의 가계부 콘솔 프로그램입니다.

🏗️ 1. 아키텍처 및 모듈/클래스 책임 분리 (구조화)
본 프로젝트는 의존성이 한 방향으로만 흐르도록 설계된 계층형 구조를 따르며, 단일 책임 원칙(SRP)을 준수합니다.

1.1. 모듈 단위의 책임 분리
models.py (Domain & DTO): 가계부의 핵심 데이터 구조와 규칙을 정의합니다. CommandData 계열의 DTO를 도입해 비즈니스 로직 진입 전에 입력값을 완벽히 검증합니다.

validators.py (Validation): 시스템 전반에서 쓰이는 유효성 검사 로직을 중앙화하여 코드 중복과 모듈 간 순환 참조(Circular Import)를 방어합니다.

storage.py (Data Access): 파일 I/O 시스템과 직접 맞닿아 있으며, 데이터 스트리밍 및 원자적 쓰기(Atomic Rewrite), 백업/복구를 전담합니다.

services.py & io_service.py (Business Logic): CRUD 규칙 검증, 요약 통계 계산 등 핵심 비즈니스 로직을 담당합니다.

__main__.py (CLI Controller): 사용자의 입력을 파싱하여 DTO로 변환하고, 서비스를 호출한 뒤 결과를 화면에 렌더링하는 프레젠테이션 레이어입니다.

1.2. 최소 2개 이상의 클래스 책임 경계
데이터를 담는 상태(Model) 클래스와 로직을 실행하는 행동(Service) 클래스로 책임을 엄격히 분리했습니다.

Transaction 클래스 (데이터/상태): __post_init__ 매직 메서드를 통해 금액이 음수인지, 날짜 포맷이 올바른지 스스로 검증합니다. "데이터의 무결성 유지"가 유일한 책임입니다.

TransactionService 클래스 (행동/비즈니스): Transaction 객체의 생명주기를 관리합니다. 새 ID를 발급하고, 스토리지에 저장을 지시하며, 조건에 맞는 내역을 검색(search)하는 흐름을 제어합니다. 데이터 유효성 검증은 전적으로 Model과 DTO에게 위임합니다.

🛠️ 2. 핵심 기술 및 설계 의도 (Q&A)
Q1. 파일 기반 update/delete 작업을 "어떻게" 안전하게 처리했는가?
A. 선행 검증을 통한 Early Exit 패턴과 os.replace를 활용한 원자적 덮어쓰기(Atomic Rewrite)를 결합했습니다.
삭제 요청 시 존재하지 않는 ID이거나 데이터 상태 변화가 없는 경우, 무거운 디스크 I/O를 멈추고 즉시 리턴합니다. 실제 반영 시에는 임시 파일(*.tmp)에 기록 후 os.replace()로 덮어씌워 작업 도중 프로그램이 종료되어도 원본 파일이 절대 깨지지 않습니다.

Q2. 대용량 파일에서 list 기능을 "어떻게" 메모리 부하 없이 정렬 및 출력했는가?
A. heapq를 도입하여 'Sliding Window' 형태의 스트리밍 정렬을 구현했습니다.
전체 파일을 메모리에 올리지 않고 제너레이터(yield)로 한 줄씩 읽으며 --limit 개수만큼의 힙(Heap) 공간만 유지합니다. 데이터가 100만 건이어도 프로그램 메모리 사용량은 O(K)로 영구히 일정합니다.

Q3. JSONL과 CSV 중 선택한 저장 포맷과 "왜" 그것을 택했는가?
A. 핵심 스토리지 포맷으로 JSONL (JSON Lines)을 선택했습니다.
가계부 데이터는 단순 문자뿐 아니라 태그(tags)와 같은 배열 데이터가 포함됩니다. CSV는 배열을 담으려면 별도 파싱 로직이 필요하지만, JSONL은 파이썬의 list 타입을 네이티브하게 직렬화할 수 있어 데이터 무결성에 유리합니다. (단, 타 시스템 연동을 위해 import/export는 CSV 포맷을 지원하도록 분리 설계했습니다.)

Q4. 백업 및 복구(Restore) 기능의 무결성은 어떻게 보장하는가?
A. 다중 파일 ZIP 아카이브와 임시 격리 폴더를 활용한 트랜잭션 복구를 구현했습니다.
복구 시 현재 운영 중인 폴더에 파일들을 무작정 덮어쓰지 않습니다. tempfile.mkdtemp()로 만든 임시 폴더에 먼저 압축을 풀고, 필수 데이터 파일 3개가 모두 손상 없이 존재하는지 검증한 뒤에만 실 운영 경로로 원자적 덮어쓰기를 수행합니다. (All-or-Nothing)

Q5. 반복 내역(Recurring) 자동 기입 시 중복(Idempotency)은 어떻게 방지했는가?
A. 시스템 예약 태그를 활용한 Pre-check 메커니즘을 적용했습니다.
매월 1일을 기준으로 고정 내역을 기입할 때, 내부적으로 sys:REC-{id}:{month} 형태의 숨겨진 태그를 데이터에 주입합니다. 로직 실행 전 해당 월의 내역을 스캔하여 이 태그가 이미 존재한다면 기입을 건너뛰어(멱등성 보장) 앱을 여러 번 켜도 중복 생성되지 않습니다.

Q6. 자동화 기능(백업/반복 기입)으로 인한 시스템 I/O 낭비는 없는가?
A. 명령어의 성격(Read/Write)에 따른 '스마트 트리거'로 최적화했습니다.
단순 조회용 명령어(list, summary 등)에서는 무거운 디스크 백업을 생략(BACKUP_TRIGGERS 분리)하고, 데이터가 변조될 위험이 있는 명령어 수행 시에만 자동 백업(auto_backup.zip)이 백그라운드에서 조용히 실행되도록 제어하여 자원을 아꼈습니다.

🚀 3. 주요 기능 실행 증빙 (무결성 검증 테스트 로그)
통합 테스트 스크립트(test.py)를 통해 엣지 케이스 방어를 검증한 내역입니다.

✅ 3.1. 거래 내역 조회 및 무결성 제어 (빈 태그/중복 차단)
Bash
> python -m budget_app add
[입력 시뮬레이션] 2024-01-10 / income / salary / 3000000 / 월급 / work
[성공] 저장 완료 (id=TX-000001)

> python -m budget_app list --limit 2
----------------------------------------------------------------------
TX-000002  | 2024-01-15 | expense | food       |    15000원 | 점심< meal >
TX-000001  | 2024-01-10 | income  | salary     |  3000000원 | 월급< work >
----------------------------------------------------------------------

> python -m budget_app update --id TX-000002 --tags "edit, edit"
[오류] 입력값이 올바르지 않거나 규칙에 위배됩니다.
[원인] 태그 목록에 중복된 값이 존재합니다. 중복을 제거해 주세요.
✅ 3.2. 월별 요약(summary) 내 초과 경고
Bash
> python -m budget_app budget set --month 2024-01 --amount 10000
[성공] 2024-01 예산 10000원 설정 완료

> python -m budget_app summary --month 2024-01 --top 3
--- 2024-01월 요약 ---
총 수입: 3000000원
총 지출: 15000원
예산: 10000원 (사용률 150.0%) (초과 경고!)
✅ 3.3. CSV Export/Import (부분 성공 및 스킵 처리)
Bash
> python -m budget_app export --out test_export.csv --month 2024-01
[성공] [완료] test_export.csv (2 records)

# 데이터가 훼손된 CSV 파일을 의도적으로 밀어 넣을 경우 (Fault Tolerance)
> python -m budget_app import --from invalid_test.csv
[성공] [완료] imported=0, skipped=1 
✅ 3.4. 데이터 복구 (Restore) 및 확장자 방어
Bash
> python -m budget_app restore --from ./data/transactions.jsonl
[오류] 입력값이 올바르지 않거나 규칙에 위배됩니다.
[원인] 복구는 ZIP(.zip) 형태의 백업 파일만 지원합니다. (입력값: './data/transactions.jsonl')

> python -m budget_app restore --from ./data/auto_backup.zip
[성공] [복구 완료] ./data/auto_backup.zip 파일로부터 데이터를 덮어썼습니다.
✅ 3.5. 반복 내역(Recurring) 자동 기입 멱등성 검증
Bash
# 프로그램 재시작 시 (list 명령어 등으로 트리거됨) 자동으로 반복 내역이 기입됨
> python -m budget_app list --limit 1
TX-000003  | 2024-05-01 | expense | rent       |    50000원 | 자동기입 월세 테스트< monthly, sys:REC-001:2024-05 >

# 동일한 달에 재실행해도 중복 생성되지 않음 (멱등성 방어 성공)