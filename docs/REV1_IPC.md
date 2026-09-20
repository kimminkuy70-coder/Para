# A1 stdio 계약 v1 — 메모리 분석 기반

상태: Python 측 기반 구현. Tauri launcher/React 연결, 실제 장비 수집 및 파일 출력은 미연결.
실행: 번들 Python에서 `-m param_manager.desktop_ipc`. 개발 테스트는 같은 모듈을 사용한다.
HTTP/TCP 포트를 열지 않는다. stdout은 UTF-8 NDJSON 전용이다.

## 요청

한 줄에 `{"version":1,"id":1,"method":"contract","params":{}}`.
id는 세션 안에서 증가하는 1~2^53-1 정수다. 재사용/역전/알 수 없는 필드는 거절한다.
요청/응답 한 줄 최대 4 MiB. 초과 요청은 오류 후 세션을 닫는다. JSON NaN/Infinity는 거절한다.

| method | params | 결과 |
|---|---|---|
| contract | 없음 | 메서드/프레임/페이지 제한 |
| analyze | records, 선택적 selected | accepted → progress → completed/error/cancelled |
| table_page | job, table, 선택적 offset/limit | 최대 200행, 전체 행 수 |
| cancel | job | 요청 접수; 진행 중이면 이후 cancelled |
| release | job | 종료된 작업 결과 메모리 해제 |
| shutdown | 없음 | 요청 차단, 취소 요청, worker 종료 대기 |

analyze 요청 id가 job id다. 다른 요청의 id는 별개이며 계속 증가한다.
한 세션에 보관하는 작업은 하나다. 완료/실패/취소 이후 release하고 다음 작업을 시작한다.
worker가 종료되기 직전 release는 거절될 수 있으므로 native dispatcher에서 직렬화/재시도를 처리한다.
summary와 테이블 목록만 완료 응답에 포함하고 실제 행은 table_page로 조회한다.
페이지 응답도 4 MiB를 넘으면 response_too_large를 반환하므로 limit을 줄여 재요청한다.

records 최대 2,000 Report, 100,000 Wafer이며 프레임 바이트 제한도 함께 적용한다.
각 record는 id, machine, report만 허용한다. report는 file_name, metadata(문자열 쌍 배열),
wafers(문자열 필드 사전 배열), 선택적 table_count다. file_name은 표시 데이터이며 열지 않는다.
selected는 기존 M01~M11이다. 현재 분석 설정은 엔진 기본값이며 설정 전달은 A2에서 추가한다.

## 보안/생명주기 한계

- 파일/네트워크/자격증명/임의 코드 API 없음. 문자열은 HTML로 실행하지 않아야 한다.
- Python 스레드가 계산하며 입력 수신은 계속한다. 계산 내부 취소 지점은 아직 없다.
  취소 요청이 접수되어도 현재 compute가 반환할 때까지 시간이 걸릴 수 있다.
- EOF/shutdown에서 협력 취소 후 join한다. 강제 종료나 공유 파일 쓰기는 하지 않는다.
- 엔진 예외는 analysis_failed로 가린다. 원문/경로/비밀번호를 오류 응답에 넣지 않는다.
- 메모리 상한은 입력 제한일 뿐 전체 RSS 보장이 아니다. 실자료 대용량 성능 검증이 필요하다.
- shutdown 응답은 요청 접수 의미이며 프로세스 종료 완료는 native 측에서 별도 감시해야 한다.
- 실제 native 연결 시 고정된 번들 실행파일만 시작하고 사용자 지정 executable/인자/경로를 받지 않는다.
  stdin/stdout backpressure, 종료 감시, 이벤트 크기 제한, CSP 및 command allowlist를 함께 검증한다.

검증: `python tests/test_desktop_ipc.py`. Windows/네이티브 통합 성공을 의미하지 않는다.
