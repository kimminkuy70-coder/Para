# Para — 장비 파라미터 관리 프로그램

Camtek AOI 장비의 PI/RDL 코어 파라미터를 호기별로 관리하는 한국어 오프라인 데스크톱
프로그램(Python/tkinter). 기존 Excel(.xlsm)+VBA 도구를 대체.
현재 작업 브랜치: `claude/program-dev-prompt-file-f2oept`
(**3차 재설계: 저장 폴더 기준 구조**. 설계/인수인계: `docs/재설계_저장폴더_구조.md`.
이전 단계: `docs/AOI_구현_진행.md`).

## 3차 재설계(2026-07, 확정) — 저장 폴더 모델

- **첫 실행에 저장 폴더 1곳 지정**(config `save_dir`). 이후 모든 산출물이 그 안에.
- **초기 3개 독립 파일**(저장폴더 안, 없으면 생성/선택 → `refdata.py`):
  `장비 IP 주소.xlsx`[호기,IP] · `참고자료.xlsx`(자유 메모 그리드) · `특이사항.xlsx`.
- **호기 목록 = 장비 IP 주소 파일 기준**(고정 34호기 폐기). 호기 추가 = 이름+IP → 그 파일 기록.
  참고자료는 순수 메모, 특이사항/참고자료는 **셀 색상 저장** 지원. 탭에 '장비 IP' 추가.
- 폴더: `{저장폴더}/양식/{레시피}/{생성시간}/{레시피}_{호기}호기_참조_{시간}.xlsx`(확정),
  그 아래 `관련파일/`(원본ini·`_원본_`·`_수정본_`). `{저장폴더}/파라미터 값 취합/
  파라미터 값 취합_{시간}.xlsx`(레시피별 시트, 참고자료 전체 호기 열). 규칙은 `workdirs.py`.
- 탭: **파라미터 값 확인 / 양식 만들기 / 특이사항 / 참고자료**.
- '값 확인' = **최신 취합 자동 로드**(멀티시트 병합, 읽기전용). 액션바: 값 업데이트 /
  이력 확인 / 최신 취합 새로고침. ⋯파일 = 저장폴더 변경 / 다시 읽기 / 장비 다운로드.
- **양식 만들기**: 레시피(PI2·3·4/RDL1~4/**기타 직접입력**) → 신규(장비/로컬) →
  **변형별 계수: RTP.txt(표시값)↔ini(원본값)로 자동 추정 후 추천**(`coef_detector`;
  사용자가 확정/수정). `ini_parser.transform_value(raw,transform,scale)`, 확정 계수는
  양식 `추출_요약`에 저장(값 업데이트가 재적용) → `formbuilder`
  수정본 생성 → **실제 Excel** 편집 → **[편집 완료]** → 확정. 원본(편집 전) 별도 보존.
  "이전 버전 불러오기" = 생성시간 폴더 선택.
- **값 업데이트**: 레시피 선택 알림 → **IP↔호기 매칭창**(IP로 새 열 만들지 않음) →
  `collate.build_collation`(설정키 매칭, **직전 취합본 이어받기**, 불일치 검출) →
  `파라미터 값 취합_{시간}.xlsx`.
- **이력 확인**: 취합 폴더 파일 2개 선택 → `history.diff_files`(멀티시트) → **다른 부분만**
  새 창(Treeview) + 변경내역 엑셀(비고 메모).
- 오래 걸리는 작업은 `_run_busy` 로딩 모달 + 백그라운드 스레드.

헤드리스 모듈(모두 테스트됨): `refdata.py`, `workdirs.py`, `formbuilder.py`, `collate.py`,
`history.py`. 매칭 정규화는 **한글 보존**. (`versioning.py`는 폴더 버전으로 대체·삭제됨.)

## Commonality 조사 (브랜치 `claude/commonality-survey`, 설계: `docs/commonality_조사_설계.md`)

Scanresult 아래 여러 **Lot**의 파라미터 변경/공통성 조사. 탭 'Commonality 조사'.
경로 `{루트}/{호기}/Scanresult/{2D@디바이스_레시피}/{공정번호}/{S/M}/{웨이퍼}/`(이름순 첫 웨이퍼).
호기 1대씩: ① 호기 선택(호기 폴더 config 저장, 그 아래 Scanresult 백업본 전부 자동 탐색) → ② Lot 계획 엑셀(디바이스명/공정번호/S·M/AOI호기)
업로드→호기 필터→폴더 실재 확인 → ③ 안전 복사(downloader, 원본 read-only) → ④ 양식 만들기
(제목 지정, 양식 만들기와 동일: OpticPreset 추림·계수·추천, **Lot 구조 diff 확인**) →
⑤ Lot별 값 조사(collate 재사용)→호기 결과 엑셀 → ⑥ 호기 취합·비교(행=S/M/호기, Zone그룹 정렬, 과반수
이탈 색칠, fail여부=Y S/M 노란색) + ⑦ tksheet 뷰어(변경열만 필터·이탈 요약). S/M 변형(CFG X20 등)
다중 후보는 선택 모드(기본 전체). 헤드리스=`commonality.py`(테스트됨),
경로=`workdirs.commonality_*`, GUI=`equip_app._view_commonality`/`_cm_*`.
**다중 레시피(2개+) 자동 처리(2026-07 확정)**: 스캔 폴더에 `RecipesInfo.ini`(각 [Recipe-N]
Name=PI/PI_Bubble…) + 무접두=Recipe-1, `RecipeN-` 접두(Recipe N: OpticPreset/
ActiveScenarioOptics/Zones) 파일이 있으면 **레시피별로 값이 다르므로 분리**. `_cm_make_form`
이 `commonality.detect_recipes` 로 자동 감지→알림창→**레시피별 순차**(편집기→값 조사) 진행,
레시피마다 양식 엑셀·조사 결과 따로. 파서는 `recipe_prefix` 로 해당 레시피 파일만 파싱
(`ini_parser.read_recipes_info`/`scan_tree(recipe_prefix=)`/`config_ini_files(prefix)`/
`read_optic_mag(_,prefix)`/`read_active_scan2d(_,prefix)`). 안전복사는 Recipe*-Zones/
및 접두 설정파일·RecipesInfo·ActiveScenarioOptics 까지 **상대구조 보존 복사**
(`downloader.collect_target_items`).

## 이미 확정된 결정 (재질문 금지)

아래는 사용자와 이미 합의가 끝난 사항이다. 같은 내용을 AskUserQuestion으로 **다시 묻지 말 것**.
세션이 새로 시작돼 맥락이 리셋돼도 이 파일을 신뢰하고 그대로 진행한다.

> **주의**: 아래 항목 중 폴더 배치(initial/final/백업)·파일 분리 저장(_PI/_RDL)·취사선택 UI·
> 통합 마법사·값 갱신 안전장치·네트워크 수집 다이얼로그 세부는 **위 '3차 재설계'가 우선**하며
> 일부는 대체·삭제됐다. 스키마/계수/보안 제약은 유효.

- **스키마**: META_FIELDS = `[PI, Recipe, Zone, Alg, Parameter, 비고]`.
  - **`초기 추천값` 열은 2차 수정안으로 제거**(파일에서도). 구 파일은 `engine.LEGACY_META`로
    하위호환(호기열 오인 방지, 저장 시 자연 제거).
  - `PI` 컬럼 = 레시피 레벨(PI2/PI3/PI4, RDL1~RDL4, **기타 커스텀 레벨 허용**)
  - `Recipe` 컬럼 = 변형(variant): PI계열은 `PI` / `PI-bubble`, RDL계열은 `x5` / `x20`
- **변환 계수(scale)**: 단일 하드코딩 금지. `ini_parser.transform_value(raw, transform, scale)`.
  **장비 렌즈 특성 → 계수는 (호기 + MAG)마다 다름(2026-07 확정)**. 같은 호기·같은 MAG면
  레시피 달라도 동일. MAG = OpticPreset 최신 Scan2d 의 `Mag`(예 3.14, `ini_parser.read_optic_mag`).
  저장 = 저장폴더 `변환계수.xlsx`[호기,MAG,변형,계수,비고](`coefstore.py`, 사람 관리 + 수집 시
  RTP.txt 자동추정 upsert). 적용 = `scan_tree(coef_lookup=)`가 (호기,MAG)로 조회(없으면 자동
  추정→저장, 그래도 없으면 구 `scales`/기본). 값확인 화면 `AOI-xx : PI` 옆에 변형별 계수 표시.
  구 방식(변형별 `추출_요약`)은 폴백으로 유지. 정확값 `0.8456665875666588`/`0.7696441409644141`.
- **IP↔호기**: 값 업데이트 수집 시 IP를 **호기(AOI-xx)에 매칭**(IP-파생 열 생성 금지).
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
python3 tests/test_refdata.py      # 3  (참고자료/특이사항 독립 파일 I/O·호기·IP)
python3 tests/test_coef_detector.py # 2 (RTP.txt↔ini 계수 역추정·near-1 제외)
python3 tests/test_ini_parser.py   # 15 (ini 파서/수집/경로/백업/계수/config폴더/ActiveScenarioOptics/다중레시피)
python3 tests/test_formbuilder.py  # 3  (초안 생성·편집→확정 양식·계수 저장)
python3 tests/test_collate.py      # 2  (레시피별 시트·전체 호기·직전 이어받기·불일치)
python3 tests/test_history.py      # 1  (멀티시트 비교·변경내역 엑셀)
python3 tests/test_pipeline.py     # 1  (참고자료→양식→취합→최신자동→이력 통합)
python3 tests/test_commonality.py  # 16 (Lot계획·폴더해석·폴더/SM변형·다중레시피/중간폴더·Scanresult백업다중·fail색칠·안전복사·구조diff·취합·이탈색칠·Zone정렬)
python3 tests/test_coefstore.py    # 3  (변환계수.xlsx (호기+MAG) I/O·lookup·OpticPreset MAG·장비별 계수 적용)
python3 tests/test_collector_safety.py # 3 (원본 read-only 보호·UNC 거부·dest≠src)
python3 tests/test_editor_model.py # 10 (편집기 GUI비의존: 사용규칙·격자계층·확정레코드·표시값 무예외·실파서왕복)
python3 tests/test_errlog.py       # 5  (오류 코드+traceback 로그·사용자 메시지·쓰기불가 방어)
python3 tests/test_tray.py         # 4  (트레이 상주 판단·비Windows 안전 no-op·메뉴 ID)
python3 tests/test_locking.py      # 11 (편집잠금 획득/타인읽기전용/만료인수/자기잠금회수·저장전재검증·전역잠금·접속자세션)
python3 tests/test_watcher.py      # 24 (주기/시간대/backoff·찢어진읽기제외·변경보고서·무변경무알림·연결점검 타임아웃/취소·대상 장비·레시피 선택·**미선택 호기 값 유지**·수집계획 왕복·보고서목록·공유상태·Job매칭 레벨별폴백·감시폴더 지정)
python3 tests/test_rtp_parser.py   # 7  (레거시 RTP 파서)
python3 tests/test_engine.py       # 12 (샘플 .xlsm 업로드 필요 — 없으면 일부 실패)
python3 tests/test_downloader.py   # 8
```
※ GUI(tkinter/tksheet)·Windows(net use)·Excel 은 개발환경 미지원 → GUI 는
`python3 -m py_compile param_manager/*.py` 정적검증. 실기 확인은 Windows 필요.

## v3.0 — 동시 접속 제어 + 자동 감시 (브랜치 `version_v3.0`, 2026-08 확정)

**저장폴더는 OneDrive 사용으로 확정**(사용자 결정). 동기화 지연 때문에 잠금은
상호배제를 **보장하지 못하므로**, 저장 직전 재검증이 최후 방어선이다.

- **동시 접속**: 수정 문서(장비IP/특이사항/참고자료)는 1명만 편집, 나머지는 **읽기 전용**
  (편집 바인딩 미부착 + 🔒 배너 '누가 언제부터'). 화면 이탈 시 즉시 잠금 반납.
  `_make_table(read_only=)` 가 force_edit 보다 우선. 값 확인은 원래 읽기전용이라 잠금 없음.
- **전역 작업 잠금**: 값 업데이트·양식 만들기(레시피별)·**자동 감시**.
  감시 중복 실행은 장비에 배수 접속이므로 반드시 단일. 앱 재시작 시 조용히 재획득.
- **접속자 목록**: 헤더 '👥 현재 접속: …'(클릭=상세), ⋯파일>현재 접속자 보기.
  60초 하트비트(`_presence_tick`)로 세션 갱신 + 내 잠금 갱신 + 만료 세션 정리.
- **취합 열은 항상 전체 호기(중요)**: 감시 대상으로 고른 장비는 '어디서 새로 읽을지'만
  정한다. `build_collation`/`write_collation` 에 **선택분만 넘기면 나머지 호기의 기존
  값이 빠져 변경보고서에 '삭제'로 오탐**된다(`collate_recipe` 의 직전값 이어받기가
  `machines_all` 로 제한되기 때문). 반드시 `_all_machines()` 를 넘길 것.
- **감시 폴더 직접 지정(권장·2026-08)**: 설정창 '📁 감시 폴더 지정…' → '장비에서 선택…'
  이 **양식 만들기와 같은 방식으로 장비를 훑어** 장비→Job→Setup→Recipe 목록을 차례로
  보여준다(`_browse_equipment_recipe`, `_pick_list_chooser` 재사용 — 경로 직접 입력
  없음, 실재하는 폴더만 표시, 설정파일 없는 폴더는 표시·확인). 고르면 `watcher.job_relative` 가 **`\Job\` 뒤 상대경로만**
  저장한다(`감시설정.json` `recipe_paths`). IP 가 빠지므로 `machine_recipe_dir(ip, rel)`
  로 **모든 장비에 그대로 적용**된다. 지정된 레시피는 이름 유추(plan/느슨매칭)를
  하지 않고 그 경로만 읽으므로 '자동 매칭 실패'가 없다(`_collect_fixed_dir`).
  미지정 레시피만 아래 계획/매칭 폴백을 탄다.
- **무인 수집 계획(폴백)**: 무인 회차는 선택창을 띄울 수 없으므로 사람이 '값 업데이트'를 1회
  수동 실행할 때 확정된 `CollectPlan`(Job/Setup/Recipe 폴더)을 `감시설정.json` `plan` 에
  저장해 재사용한다(`watcher.plan_to_dict/plan_from_dict`). 계획이 없으면 회차를
  실패시키고 안내한다 — **추측해서 엉뚱한 폴더를 읽지 않는다**. 자동 매칭이 안 되는
  장비는 건너뛰고 로그에 남긴다(`_watch_collect`). **레벨별로 되는 것만 수집**한다 —
  collector 의 plan 재사용 분기는 레벨 하나만 실패해도 전체를 포기하므로,
  `_watch_collect.auto_match` 가 레벨 단위로 ①계획의 Job 폴더명 ②레시피 이름으로
  Job 폴더 찾기(후보 1개일 때만) 순으로 재시도하고 실패 사유를 로그에 남긴다. **레시피 폴더명이 장비마다 조금씩
  달라도** `collector.match_recipes_by_names` 가 정확일치→느슨매칭(`norm_match`: 소문자
  +영숫자/한글만, 양방향 포함)으로 찾아준다. 후보가 0개거나 2개 이상이면 매칭 실패로
  건너뛴다. **주의**: `collect_equipment` 에 `target_levels`/`match_recipes` 를 넘겨야
  recipe_map 재사용 경로를 탄다(안 넘기면 job_keyword 가 빈 계획에서 선택창을 요구해
  전 장비가 건너뛰어진다).
- **결과는 모두가 공유**: 감시 설정은 저장폴더에 있으므로 **누가 켰든 모든 사람의
  버튼이 ON**(잠금 보유자 이름 표기). 수집은 잠금을 쥔 1대만 돌지만, 각 앱이
  `_watch_poll_shared` 로 `state.last_run` 변화를 감지해 **모두 같은 알림**을 받는다
  (본 회차는 로컬 config `watch_seen:` 에 기록 — 중복 알림 방지). 알림 내용은
  '변경 있음/없음 + 요약'만, 클릭하면 `_watch_reports_window` 가 열려 보고서 확인.
  트레이 풍선 클릭도 같은 창으로 연결(`NIN_BALLOONUSERCLICK`).
- **즉시 확인**: 설정창 '▶ 즉시 확인' — 주기를 기다리지 않고 1회 실행. 사람이 눌렀으므로
  진행 모달을 띄우고 **변경이 없어도 결과를 알린다**. 주기 회차와 로직 공유
  (`_watch_cycle_work`/`_watch_finish`).
- **자동 감시**: 설정창에서 **① 감시할 장비 ② 감시할 레시피(둘 다 필수)** → ③ 접속 방식 →
  주기(기본 6h)·시간대 창. 선택은 `감시설정.json` 의 `machines`/`recipes` 에 저장되고
  **연결 점검·수집·취합 모두 선택분만** 대상으로 한다(미선택이면 켜지지 않음. 저장 뒤
  삭제된 항목은 실행 시 자동 제외). 선택 UI 는 공용 `_pick_list`. 이후 조용히 수집·취합 →
  `history.diff_files` 로 직전과 비교 → **변경 있을 때만** 알림 + `자동감시/변경보고서_{시간}.xlsx`.
  무인이라 모달 금지(`_run_bg`). 설정=`감시설정.json`, 로그=`자동감시/감시로그.txt`.
- **트레이 상주(`tray.py`)**: 감시 ON 상태로 창을 닫으면(X) **종료하지 않고 창만 숨겨**
  감시를 계속한다(tkinter `after` 가 계속 도는 구조라 가능). 알림영역 아이콘 좌클릭/
  더블클릭=창 열기, 우클릭=메뉴(프로그램 열기 / 자동 감시 종료). 숨김 중 변경 감지는
  모달 대신 **풍선 알림**(숨은 창의 모달은 볼 수 없으므로). 숨길 때 문서 편집 잠금은
  반납하고 감시 전역 잠금만 유지. 감시 OFF 면 그냥 종료.
  **추가 패키지 금지 제약 때문에 pystray 대신 stdlib `ctypes` + Win32 `Shell_NotifyIconW`**
  를 직접 호출(별도 스레드에서 숨은 창+메시지 루프, 콜백은 `root.after` 로 GUI 스레드에
  위임, WNDPROC 참조 유지 필수). 비Windows 는 `available()=False` 로 전부 no-op.
- **장비 비방해(최우선)**: 원본 읽기전용(collector 3중 안전장치 유지) · 복사 전후
  (mtime,size) 비교로 **쓰는 중이던 파일 제외**(거짓 변경 방지) · 연속 실패 시
  backoff(1/2/4/8배)로 **재시도 몰아치기 금지** · 순차 접속 유지.
- **무인 접속 기본 = `CONN_SESSION`(net use 없이, 권장)** — 비밀번호를 디스크에 저장하지
  않는다. 사용자가 탐색기로 대상 장비를 **미리 모두 연결**해 두어야 하며,
  `check_connections`/`connection_guide` 가 미연결 장비를 사전 안내. `CONN_NETUSE` 선택 가능
  (비밀번호는 메모리에만, 앱 종료 시 소멸).
- 오류 코드: 잠금 E150~E154, 감시 E155~E158, 트레이 E159~E160.

- **프로그램 아이콘**: `param_manager/data/para_icon.ico`(16~256, 투명 배경).
  생성기 `tools/make_icon.py` — **추가 패키지 금지**라 Pillow 없이 stdlib `zlib` 로
  PNG/ICO 를 직접 만든다. 웨이퍼+AOI 카메라+파라미터 슬라이더, 파랑→청록.
  ≤24px 는 글자를 빼고 실루엣만(뭉개짐 방지), ≥32px 는 'AOI' 표기.
  적용 = `equip_app.icon_path()` → 창(`iconbitmap`)·트레이(`tray.TrayIcon(icon_path=)`).

## 핵심 파일

- `param_manager/ini_parser.py` — **새 1차 파서**: GlobalRTP/OpticPreset/Zones ini →
  Para 스키마(Zone/Alg/Parameter) 정규화, KNOWN_DISPLAY_MAP·계수 변환, 피벗.
  **OpticPreset LIGHT/Scan2d 통일**(`_parse_optic`): Scan2d(target) 섹션만
  alg=`Scan2d`로 통일, `OPTIC_SCAN2D_KEEP`(9개)만 사용=Y, `Scan2d 최신 항목 이름` 합성행 추가,
  나머지·오래된 Scan2d는 사용=N(검토용). `ExtractRow.use_default`→피벗 `use`→formbuilder.
  **target(현재 스캔 optic) 선택(`_pick_optic_target`)**: 신 SW = 같은 폴더 `ActiveScenarioOptics.ini`
  의 `ScenarioName=Scan2d` 항목 `OpticsName`/`OpticId` 로 OpticPreset 섹션 매칭(`read_active_scan2d`).
  없으면(구 SW) 기존 방식 = CameraName=TDI·광원키 가진 **마지막** 섹션. `read_optic_mag` 도 동일 경로.
  (`collector.FIXED_FILES` 에 ActiveScenarioOptics.ini 포함 — 있을 때만 복사.)
  **변환 판정(`resolve_transform`)**: 표시명에 **µ(마이크로) 있으면 변환**(area→AREA,else LINEAR),
  **없으면 RAW**(예: 'Min Defect Width'는 변환 안 함). BOOL/REGION/CLASSIFY는 유지.
  **GlobalRTP**(`GLOBALRTP_KEEP`): `Max Defects Per Wafer/Die`만 기본 사용=Y, 나머지 N.
  변환방식 라벨은 실제 계수 반영(`label_transform`).
  **config 폴더 파싱 대상(`config_ini_files`)**: 폴더 바로 아래는 **GlobalRTP.ini/
  OpticPreset.ini 만**(그 외 .ini 제외 — 쓸데없는 항목 방지, _N 접미사 인식) + **Zones/*.ini 전부**.
- `param_manager/collector.py` — 장비 네트워크 읽기전용 수집(net use, plan 자동 재사용).
  `FIXED_FILES`에 **RTP.txt 포함**(계수 자동 추정용). RTP.txt는 recipe 폴더에 위치.
  **Zones/ 하위구조 보존 복사**(staging 에 `Zones/*.ini` 그대로 — 파서 규칙과 일치).
- `param_manager/coef_detector.py` — **변환 계수 자동 추정**: RTP.txt(표시값)↔Zone ini(원본값)
  known 쌍 비교(LINEAR=disp/raw, AREA=√). 1.0 근처(직접단위) 제외, 군집·신뢰도. `detect_from_dir`.
- `param_manager/refdata.py` — **참고자료/특이사항 독립 파일 I/O**: `REF_HEADERS=[호기,IP,비고]`,
  load/save/create_blank, `machines()`/`ip_for()`/`add_machine()`.
- `param_manager/coefstore.py` — **변환계수.xlsx (호기+MAG) 저장소**: `[호기,MAG,변형,계수,비고]`
  load/save/create_blank, `lookup(rows,호기,MAG)`(숫자 근사), `upsert`(사람값 우선),
  `machine_coefs`(표시), `make_lookup`(scan_tree 콜백). MAG 는 OpticPreset Scan2d Mag.
- `param_manager/workdirs.py` — **저장폴더 기준 경로**: `form_run_dir/form_final_path/
  form_original_path/form_draft_path/related_dir/list_form_versions/collate_path/
  latest_collate/list_collate_files`. (구 initial/final/백업 함수는 레거시.)
- `param_manager/extract_io.py` — 스냅샷(공용 양식 + `_EXTRACT_MAP`) + `write_snapshot(scales=)`/
  `read_scales`(변형별 계수 저장/판독).
- `param_manager/formbuilder.py` — **양식 만들기**: `build_initial_workbook`(수정본, '사용'/
  '최종 Parameter')·`build_final_from_initial`(→확정 양식+`_EXTRACT_MAP`+계수).
- `param_manager/locking.py` — **동시 접속 제어**(v3.0): `acquire/refresh/release/status`
  (free/mine/**self**/stale/other — self=같은 사람·같은 PC의 죽은 프로세스는 자동 회수),
  `holder_message`(안내문), `check_before_save`(**저장 직전 재검증** — 외부 변경·잠금 탈취·
  OneDrive 충돌본), `acquire_global/release_global`(작업 단위), 세션
  `touch_session/list_sessions/prune_sessions/end_session/others_message`.
  engine 의 `.editlock`·`LOCK_STALE_MINUTES`·`find_conflict_copies` 재사용.
- `param_manager/watcher.py` — **자동 감시**(v3.0): `WatchSettings/WatchState`(감시설정.json),
  `should_run/next_run_at`(주기·backoff, now 인자로 결정적)·`in_window`(시간대, 자정넘김),
  `file_sig/unstable_files/drop_unstable`(**찢어진 읽기 제외**), `compare_and_report`
  (diff_files→변경보고서, 무변경이면 보고서 없음), `record_run`, `check_connections/
  connection_guide`(net use 없는 기본 모드 사전 점검), `append_log`.
- `param_manager/errlog.py` — **오류 코드·로그**(v1.1): 발생 지점마다 고유 코드 `E###`
  부여. `log_path`/`write_log`(전체 traceback 를 `저장폴더/오류_로그.txt` 에 append)·
  `user_message`(코드 포함 안내). equip_app `_err`(팝업+로그)/`_logerr`(로그만·비치명)/
  `_write_log` 가 위임. **코드는 소스에 그대로 있어 grep 가능** → 사용자가 화면의 코드를
  알려주면 발생 지점 즉시 특정. 편집기 열기/격자/표생성/확정 = E200~E205, 스타일 폴백 =
  E210~E216, 나머지 실패 지점 = E101~E144. `tests/test_errlog.py` 검증.
- `param_manager/editor_model.py` — **화면 편집기 GUI비의존 로직**(v1.1, tksheet 편집기가 호출):
  `build_entries`(사용규칙: base_keys/default_use/파서플래그)·`build_grid`(평면 격자+변형/Zone/Alg
  헤더행+계층 매핑)·`build_records`(선택→저장 records/extracts/계수, 기존 confirm 규칙)·
  `safe_display`(**어떤 원본값에도 예외 없음** — NaN/inf/문자 대비)·`method_of`/`label_of`.
  파일 종류가 달라도 깨지지 않게 `tests/test_editor_model.py` 로 검증.
- `param_manager/collate.py` — **값 취합(멀티시트)**: `build_collation`(레시피별 시트, 참고자료
  전체 호기, 직전본 이어받기, 설정키 매칭·불일치), `write_collation`/`load_collation`/
  `load_as_repo`(값 확인 병합). **값은 양식의 변환방식(_EXTRACT_MAP transform)을 수집 raw 에
  재적용**(사람이 양식에서 고친 변환방식·계수 반영). 계수 우선순위: `coef_lookup(호기,MAG)`
  → 라벨 계수(`ini_parser.scale_from_label`) → 기본. commonality 도 같은 경로 재사용.
- `param_manager/history.py` — **이력 확인**: `diff_files`(멀티시트 값변경/추가/삭제)·
  `write_diff_excel`(변경내역+비고 메모).
- `param_manager/equip_app.py` — tkinter GUI(저장폴더 모델). `_startup`/`_choose_save_dir`/
  `_load_refdata`/`_load_latest_collate`, 호기 그리드=참고자료, `_view_special`/`_view_reference`
  (독립 파일), `_view_form`/`_form_new`/`_form_build_and_edit`/`_form_finalize`(실제 Excel),
  `_load_previous_form`, `_ask_scales`(변형별 계수), `_map_ips_to_machines`(IP↔호기),
  `_update_values_dialog`/`_update_collate_flow`/`_update_write_results`, `_history_dialog`/
  `_show_diff_window`, `_run_busy`(로딩), `_file_menu`(저장폴더/다시읽기/다운로드).
- `param_manager/engine.py` — `create_from_records`(PI_ALL/RDL_ALL 기록), `ParamRow`/`ParamRepository`,
  `LEGACY_META`(구파일 초기추천값 무시). 잠금/병합/이력은 새 경로에서 미사용.
- `param_manager/rtp_parser.py` — 레거시 RTP.txt 파서(새 경로 미사용) + `config_valid`/
  `recommend`/`norm_key` 는 공용 유틸로 계속 사용.
- `param_manager/data/rtp_template.json` — 추천 이름 + 한글 설명 통일안(1928 항목).
- `param_manager/downloader.py` — ScanResult 폴더 다운로드(별도 메뉴, 읽기 전용).
  Commonality 가 경로 파싱/안전복사를 재사용(`parse_scanresult_path`/`copy_one_file`/
  `collect_target_items`/`TARGET_FOLDER_NAME`/`TARGET_FILES`).
- `param_manager/commonality.py` — **Commonality 조사 헤드리스**: Lot 계획 엑셀
  (`create_plan_template`/`read_plan`/`filter_plan_for_machine`), 폴더 해석
  (`scanresult_root`/`resolve_lot`/`resolve_plan`, 디바이스명+LOT+S/M, 이름순 첫 웨이퍼),
  안전복사(`copy_lot`), Lot 파싱→통합 피벗(`parse_lots`)·구조 diff(`structure_diff`),
  값 취합(`collate_lots`/`write_lot_result`/`read_lot_result`), 호기 비교
  (`build_comparison`/`write_comparison`, 과반수 이탈 색칠 `MISMATCH_FILL`).
