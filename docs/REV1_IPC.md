# Desktop stdio 계약 v1

React → 제한 Tauri command → 고정 sidecar → 기존 Python 엔진.
HTTP/TCP 서버 없음. stdout UTF-8 NDJSON. native 실제 Windows 실행은 미검증이다.

요청은 `{ "version":1, "id":1, "method":"contract", "params":{} }`.
id는 세션 내 증가하는 1..2^53−1 정수. 프레임 최대 4 MiB. NaN/Infinity/추가 필드는 거절.

| method | 입력/경계 | 결과 |
|---|---|---|
| contract | 없음 | 메서드·제한 |
| configuration | 없음 | 기존 설정에서 등록 호기·최신 조사 조건 |
| investigate | 등록 호기 ID·검색어·날짜·M01~11 설정 | accepted/progress/completed/error/cancelled |
| analyze | 최대 2,000 Report / 100,000 Wafer 메모리 데이터 | 기존 메모리 분석 |
| table_page | job/table/offset/limit | 최대 200행 |
| cancel / release / shutdown | job 또는 빈 입력 | 협력 취소 / 결과 해제 / 종료 대기 |
| recipe_open | 없음 | 최신 기존 취합의 snapshot/Recipe/호기 |
| recipe_page | snapshot/recipe/query/선택호기/offset/limit/호기 offset·limit | 최대 100행·비교 호기 12개 |
| recipe_edit | snapshot/row/kind/value | color 또는 note만; 파라미터 값 수정 금지 |
| form_catalog | 없음 | 저장폴더 레시피별 편집 가능한 원본(초안) 버전 목록 |
| form_open | recipe/stamp | 원본 초안을 열어 항목 grid snapshot(변형·사용·이름·변환) |
| form_page | snapshot/variant/query/used_only/offset/limit | 최대 100행 |
| form_edit | snapshot/row/kind/value | 사용(Y/N)·표시이름·변환(RAW/LINEAR/AREA)만 |
| form_confirm | snapshot/machine | worker: 확정 양식+편집용 원본을 저장폴더 새 회차에 기록 |
| document_open | ip/special/reference | 고정 공유 문서 snapshot |
| document_page | snapshot/offset/limit | 최대 100행 |
| document_edit | snapshot/row/column/value/color | 선택 셀만 잠금·변경 검사 후 저장 |
| document_append | snapshot/values | 기존 문서의 표시 열 개수와 일치하는 문자열 배열, 셀당 4000자, 빈 행 거절; 잠금·변경 검사 후 끝에 추가 |
| commonality_catalog | 없음 | 기존 로컬 수동/감시 결과의 opaque ID 목록, 최대 5000개 |
| commonality_compare | catalog/files | 등록 ID 1~100개, 파일 변경 검사, accepted/completed/error |
| commonality_page | snapshot/offset/limit/column/query/changed_only | 최대 100행·12파라미터, 상태·최빈값 이탈 |
| commonality_export | snapshot/changed_only | 고정 로컬 폴더의 새 Excel, accepted/completed/error |
| cmsurvey_config | 없음 | Scanresult 루트가 설정된 호기 목록(config commonality_roots) |
| cmsurvey_preflight | machine/plan | 계획(데이터 행)을 그 호기 Scanresult 루트에 해석 → 발견/없음 Lot |

Commonality 비교/내보내기는 worker에서 실행하며 다른 조사와 중복 실행을 거절한다.
별도 취소/진행률은 아직 없으며 종료 시 worker를 기다린다. 목록/페이지는 동기 작업이다.

임의 파일/실행파일/명령 문자열을 입력받지 않는다. Python도 경로 경계를 검증한다.
장비는 기존 설정 경로로 읽기만 한다. 배치 결과는 localdirs가 허용하는 로컬에 저장한다.
공유 문서는 기존 형식을 보존하고 명시적 편집 시 잠금/변경 확인/원자 교체한다.
IP 문서의 구 자격증명 열은 UI에 반환하지 않는다. 원문은 React 텍스트로 처리한다.

단일 배치 작업을 유지하며 완료 뒤 release한다. 완료 이벤트 직전 running을 해제한다.
취소는 파일/계산/출력 경계에서 처리하며 블로킹 SMB 호출을 강제 종료하지 않는다.
최종 결과 게시를 시작한 이후의 늦은 취소는 완료된 결과를 되돌리지 않는다.
Recipe/문서 작업은 다른 worker 실행 중 거절한다. Recipe는 동기 실행이다.
문서 open/edit/append는 accepted 후 단일 worker에서 처리하며 completed/error를 보낸다.
document_page는 동기 메모리 조회다. 문서 worker 중 중복 편집/조사를 거절하고 종료 시
저장이 끝날 때까지 기다린다. 문서 작업의 별도 진행률/취소는 아직 없다.

Native는 resources/sidecar의 고정 exe만 실행하고 PYTHONPATH/PYTHONHOME를 제거한다.
송신 큐 최대 8개, 프레임 제한 4 MiB. EOF에서 Python은 취소 후 worker를 기다린다.
Native 종료도 sidecar 종료를 기다린다. 응답 크기 초과 시 더 작은 페이지로 재요청해야 한다.

브라우저 통합 테스트는 native를 대체하고 실제 Python과 연결한다. Rust/WebView2 시험을
대체하지 않는다. 제한은 DOM/IPC 단위이며 전체 backend RSS 상한 보장은 아니다.
