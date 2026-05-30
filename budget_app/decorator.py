from functools import wraps
import time
import sys


def time_logger(func):
    """함수의 실행 시간을 측정하는 데코레이터입니다. (성능 모니터링)"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        # 필요시 아래 주석을 해제하면 모든 실행 시간을 로깅할 수 있습니다.
        # print(f"[{func.__name__} 실행 완료 : {end_time - start_time:.4f}초]")
        return result

    return wrapper


def error_handler(func):
    """
    [핵심 요구사항] 예외 발생 시 스택트레이스를 숨기고
    사용자 친화적인 메시지와 힌트를 출력한 뒤 에러 코드(1)로 종료합니다.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C 또는 Ctrl+D 입력 시 진입
            print(
                "\n\n[안내] 사용자에 의해 프로그램이 종료되었습니다. 이용해 주셔서 감사합니다."
            )
            sys.exit(0)  # 사용자가 직접 종료한 것이므로 정상 종료 코드(0) 반환
        except ValueError as e:
            print(f"\n[오류] 입력값이 올바르지 않거나 규칙에 위배됩니다.")
            print(f"[원인] {e}")
            print(f"[힌트] 명령어와 옵션, 데이터 형식을 다시 확인해 주세요.")
            sys.exit(1)
        except RuntimeError as e:
            print(str(e))
            sys.exit(1)
        except Exception as e:
            print(f"\n[오류] 시스템 처리 중 문제가 발생했습니다.")
            print(f"[원인] {e}")
            sys.exit(1)

    return wrapper
