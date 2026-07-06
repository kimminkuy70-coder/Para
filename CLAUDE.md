# Para — 장비 파라미터 관리 프로그램

Camtek AOI 장비의 PI/RDL 코어 파라미터를 호기별로 관리하는 한국어 오프라인 데스크톱
프로그램(Python/tkinter). 기존 Excel(.xlsm)+VBA 도구를 대체.
현재 작업 브랜치: `claude/program-load-feature-overhaul-bc4xbf`
(불러오기 기능 대개편 — extractor 통합. 설계·인수인계: `docs/불러오기_통합_설계.md`).

## 이미 확정된 결정 (재질문 금지)

아래는 사용자와 이미 합의가 끝난 사항이다. 같은 내용을 AskUserQuestion으로 **다시 묻지 말 것**.
세션이 새로 시작돼 맥락이 리셋돼도 이 파일을 신뢰하고 그대로 진행한다.

- **스키마**: 새 컬럼 추가 안 함. 기존 META_FIELDS = `[PI, Recipe, Zone, Alg, Parameter,
  초기 추천값, 비고]` 유지.
  - `PI` 컬럼 = 레시피 레벨(PI2/PI3/PI4, RDL1~RDL4)
  - `Recipe` 컬럼 = 변형(variant): PI계열은 `PI` / `PI-bubble`, RDL계열은 `x5` / `x20`
- **변형 라벨 표기**: 버블은 하이픈 `PI-bubble`로 통일(언더스코어 `PI_bubble` 아님).
- **파일 분리 저장**: PI 계열 → `{stem}_PI.xlsx`(시트 PI_ALL), RDL 계열 → `{stem}_RDL.xlsx`
  (시트 RDL_ALL). 하나로 섞지 않음.
- **취사선택 UI**: 2개 섹션 — 위=기존 항목(기본 선택), 아래=신규 불러온 항목(기본 미선택).
  섹션별 전체선택/전체해제.
- **파싱 소스 (2026-07 변경 확정)**: `GlobalRTP.ini` + `OpticPreset.ini` + `Zones/*.ini`
  기준(extractor 방식). **RTP.txt 는 사용하지 않는다.**
  `rtp_parser.py`의 RTP.txt 파싱은 레거시로 남아 있으나 새 불러오기 경로에서는 미사용.
- **변형 인식**: 폴더명 기준 — `BUBBLE` 포함=PI-bubble, `PI`/`PI3` 형=PI,
  `x5`/`x20`(또는 OpticPreset Scan2d Mag)=RDL 배율. 미인식 폴더는 불러오지 않고 안내.
- **네트워크 수집 GUI 포함 (확정)**: `\\IP\c$\Job` 접속을 프로그램에서 수행.
  비밀번호는 메모리에만(실행 후 즉시 소거), 장비 1대씩 접속→즉시 net use 해제,
  `\Job` 하위만 접근, 복사 간 0.1s 지연, 원본은 읽기/복사만.
  탐색기로 미리 연결해 두고 net use 체크를 끄는 모드도 제공(수동 접속과 동일).
- **폴더 배치 (확정)**: 공용 파일과 같은 폴더 아래
  `initial/{PI#|RDL#}/{AOI-호기}/{일시}/`(staging+01_초안),
  `final/{…}/`(02_확정), `백업/`(값 갱신 전 자동 백업). 규칙은 `workdirs.py` 한 곳.
- **initial/final 양식 통일 (확정)**: extractor 의 양식이 아니라 기존 공용 파일
  양식(PI_ALL/RDL_ALL)을 따른다. 재추출 메타는 `_EXTRACT_MAP` 숨김 시트에 보존.
- **기존 메뉴 대체 (확정)**: '폴더 분석→취사선택'과 '값 갱신(구조 유지)' 메뉴는
  '파라미터 불러오기(통합)' 마법사로 즉시 대체됨(병행 없음).
- **값 갱신 안전장치 (확정)**: 적용 전 변경 셀 미리보기 → 공용 파일 자동 백업 →
  적용. 매칭 실패 행은 건드리지 않음. 빈 값은 덮어쓰지 않음.
- **OpticPreset 잡키 필터**: GUID/per-scan float/빈값/`OPTIC_NOISE_KEYS` 자동 제외(레거시 경로).

## 보안/환경 제약 (반드시 준수)

- **Anaconda/conda 금지** — 회사 과금 + 경고받음. venv/시스템 파이썬만.
- **런타임 외부(인터넷) 네트워크 금지** — 사내 장비망(`\\IP\c$`) 읽기전용 수집만 예외
  (사용자 확정). OneDrive 동기화된 로컬 파일 + 장비 공유폴더 읽기.
- **의존성**: `openpyxl` + `tksheet`만. 추가 패키지 금지.
- **장비/원본 읽기 전용**: 원본 파일을 수정/삭제/이름변경/이동 금지.
- 지정 브랜치에서만 작업, 허락 없이 다른 브랜치 push 금지. 요청 없이 PR 생성 금지.

## 테스트 (venv 없으면 시스템 python3 + openpyxl 로도 동작)

```
python3 tests/test_rtp_parser.py   # 7  (레거시 RTP 파서)
python3 tests/test_ini_parser.py   # 6  (ini 파서/수집/경로/백업/스냅샷/값갱신)
python3 tests/test_engine.py       # 12 (샘플 .xlsm 업로드 필요 — 없으면 일부 실패)
python3 tests/test_downloader.py   # 8
```

## 핵심 파일

- `param_manager/ini_parser.py` — **새 1차 파서**: GlobalRTP/OpticPreset/Zones ini →
  Para 스키마(Zone/Alg/Parameter) 정규화, KNOWN_DISPLAY_MAP·SCALE(0.8452) 변환, 피벗.
- `param_manager/collector.py` — 장비 네트워크 읽기전용 수집(net use, plan 자동 재사용).
- `param_manager/workdirs.py` — initial/final/백업 폴더 규칙 + 백업 생성.
- `param_manager/extract_io.py` — 01_초안/02_확정 스냅샷(공용 양식 + `_EXTRACT_MAP`).
- `param_manager/refresh.py` — 값 갱신 미리보기(plan)/적용(apply) 분리.
- `param_manager/equip_app.py` — tkinter GUI. 통합 마법사(`_curate_dialog`, `_cur_*`),
  수집 다이얼로그(`_cur_collect_dialog`), 값 갱신(`_cur_update_values`), 다운로드 메뉴.
- `param_manager/engine.py` — `create_from_records`(PI_ALL/RDL_ALL 시트 기록), 잠금/병합/이력.
- `param_manager/rtp_parser.py` — 레거시 RTP.txt 파서(새 경로 미사용) + `config_valid`/
  `recommend`/`norm_key` 는 공용 유틸로 계속 사용.
- `param_manager/data/rtp_template.json` — 추천 이름 + 한글 설명 통일안(1928 항목).
- `param_manager/downloader.py` — ScanResult 폴더 다운로드(별도 메뉴, 읽기 전용).
