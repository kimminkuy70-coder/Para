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
| document_open | ip/special/reference | 고정 공유 문서 snapshot |
| document_page | snapshot/offset/limit | 최대 100행 |
| document_edit | snapshot/row/column/value/color | 선택 셀만 잠금·변경 검사 후 저장 |
| commonality_catalog | 없음 | 기존 로컬 수동/감시 결과의 opaque ID 목록, 최대 5000개 |
| commonality_compare | catalog/files | 등록 ID 1~100개, 파일 변경 검사, accepted/completed/error |
| commonality_page | snapshot/offset/limit/column/query/changed_only | 최대 100행·12파라미터, 상태·최빈값 이탈 |
| commonality_export | snapshot/changed_only | 고정 로컬 폴더의 새 Excel, accepted/completed/error |

Commonality 비교/내보내기는 worker에서 실행하며 다른 조사와 중복 실행을 거절한다.
별도 취소/진행률은 아직 없으며 종료 시 worker를 기다린다. 목록/페이지는 동기 작업이다.

임의 파일/실행파일/명령 문자열을 입력받지 않는다. Python도 경로 경계를 검증한다.
장비는 기존 설정 경로로 읽기만 한다. 배치 결과는 localdirs가 허용하는 로컬에 저장한다.
공유 문서는 기존 형식을 보존하고 명시적 편집 시 잠금/변경 확인/원자 교체한다.
IP 문서의 구 자격증명 열은 UI에 반환하지 않는다. 원문은 React 텍스트로 처리한다.

단일 배치 작업을 유지하며 완료 뒤 release한다. 완료 이벤트 직전 running을 해제한다.
취소는 파일/계산/출력 경계에서 처리하며 블로킹 SMB 호출을 강제 종료하지 않는다.
최종 결과 게시를 시작한 이후의 늦은 취소는 완료된 결과를 되돌리지 않는다.
Recipe/문서 작업은 배치 실행 중 거절한다. 이 작업은 동기 실행으로 별도 진행/취소는 아직 없다.

Native는 resources/sidecar의 고정 exe만 실행하고 PYTHONPATH/PYTHONHOME를 제거한다.
송신 큐 최대 8개, 프레임 제한 4 MiB. EOF에서 Python은 취소 후 worker를 기다린다.
Native 종료도 sidecar 종료를 기다린다. 응답 크기 초과 시 더 작은 페이지로 재요청해야 한다.

브라우저 통합 테스트는 native를 대체하고 실제 Python과 연결한다. Rust/WebView2 시험을
대체하지 않는다. 제한은 DOM/IPC 단위이며 전체 backend RSS 상한 보장은 아니다.
