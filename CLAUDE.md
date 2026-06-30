# Para — 장비 파라미터 관리 프로그램

Camtek AOI 장비의 PI/RDL 코어 파라미터를 호기별로 관리하는 한국어 오프라인 데스크톱
프로그램(Python/tkinter). 기존 Excel(.xlsm)+VBA 도구를 대체. 현재 작업 브랜치: `para-auto`
(장비 폴더에서 받은 파라미터 파일을 자동 임포트 → 파라미터 양식 생성).

## 이미 확정된 결정 (재질문 금지)

아래는 사용자와 이미 합의가 끝난 사항이다. 같은 내용을 AskUserQuestion으로 **다시 묻지 말 것**.
세션이 새로 시작돼 맥락이 리셋돼도 이 파일을 신뢰하고 그대로 진행한다.

- **스키마**: 새 컬럼 추가 안 함. 기존 META_FIELDS = `[PI, Recipe, Zone, Alg, Parameter,
  초기 추천값, 비고]` 유지.
  - `PI` 컬럼 = 레시피 레벨(PI2/PI3/PI4, RDL1~RDL4)
  - `Recipe` 컬럼 = 변형(variant): PI계열은 `PI` / `PI-bubble`, RDL계열은 `x5` / `x20`
- **변형 라벨 표기**: 버블은 하이픈 `PI-bubble`로 통일(언더스코어 `PI_bubble` 아님).
  기존 양식이 하이픈을 쓰므로 신규 파싱도 하이픈으로 맞춰 합쳐짐.
- **파일 분리 저장**: PI 계열 → `{stem}_PI.xlsx`(시트 PI_ALL), RDL 계열 → `{stem}_RDL.xlsx`
  (시트 RDL_ALL). 하나로 섞지 않음.
- **취사선택 UI**: "기존 양식 유지" 병합 옵션은 폐기됨. 대신 2개 섹션 —
  위=기존 항목(기본 선택), 아래=신규 불러온 항목(기본 미선택). 섹션별 전체선택/전체해제.
- **폴더 구조 인식**:
  - RDL: `레시피/x5|x20/{Zones, RTP.txt, OpticPreset.ini}` (Scan2d Mag 또는 폴더명으로 판정)
  - PI: `PI레시피/PI|PI_bubble/{파일들}` — 사람이 PI/PI_bubble 하위폴더로 만들어 줘야 인식.
    그 형태 아니면 불러오지 않고 오류 메시지(인식된 것만 확인창 후 로드).
- **파싱 소스 우선순위**: RTP.txt = 1차(화면 양식과 동일). OpticPreset.ini = LIGHT Zone +
  x5/x20 판정. Zones/*.ini = 내부 디테일, 사용 안 함.
- **OpticPreset 잡키 필터**: GUID/per-scan float/빈값/`OPTIC_NOISE_KEYS` 자동 제외.

## 보안/환경 제약 (반드시 준수)

- **Anaconda/conda 금지** — 회사 과금 + 경고받음. venv/시스템 파이썬만.
- **런타임 외부 네트워크 금지** — 완전 오프라인. OneDrive 동기화된 로컬 파일만.
- **의존성**: `openpyxl` + `tksheet`만. 추가 패키지 금지.
- **downloader 읽기 전용**: 원본 파일을 수정/삭제/이름변경 금지(sha256로 무변경 검증).
- 지정 브랜치에서만 작업, 허락 없이 다른 브랜치 push 금지. 요청 없이 PR 생성 금지.

## 테스트

```
/tmp/tkvenv/bin/python tests/test_rtp_parser.py   # 7
/tmp/tkvenv/bin/python tests/test_engine.py       # 12
/tmp/tkvenv/bin/python tests/test_downloader.py   # 8
```

## 핵심 파일

- `param_manager/rtp_parser.py` — RTP/OpticPreset 파싱, `detect_meta`/`config_valid`/
  `scan_tree`/`build_pivot`/`recommend`/`refresh_values`.
- `param_manager/equip_app.py` — tkinter GUI. 취사선택 다이얼로그(`_curate_dialog`,
  `_cur_*`), 폴더 분석/값 갱신/다운로드 메뉴.
- `param_manager/engine.py` — `create_from_records`(PI_ALL/RDL_ALL 시트 기록), MACHINES 34개.
- `param_manager/data/rtp_template.json` — 추천 이름 + 한글 설명 통일안(1928 항목).
- `param_manager/downloader.py` — 장비 폴더 → 로컬 복사(읽기 전용 안전).
