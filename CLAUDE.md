# Para — 장비 파라미터 관리 프로그램

Camtek AOI 장비의 PI/RDL 코어 파라미터를 호기별로 관리하는 한국어 오프라인 데스크톱
프로그램(Python/tkinter). 기존 Excel(.xlsm)+VBA 도구를 대체.
현재 작업 브랜치: `claude/program-dev-prompt-file-f2oept`
(**3차 재설계: 저장 폴더 기준 구조**. 설계/인수인계: `docs/재설계_저장폴더_구조.md`.
이전 단계: `docs/AOI_구현_진행.md`).

## 3차 재설계(2026-07, 확정) — 저장 폴더 모델

- **첫 실행에 저장 폴더 1곳 지정**(config `save_dir`). 이후 모든 산출물이 그 안에.
- **초기 3개 독립 파일**(저장폴더 안, 없으면 생성/선택 → `refdata.py`):
  `장비 IP 주소.xlsx`[호기,IP,접속ID] · `참고자료.xlsx`(자유 메모 그리드) · `특이사항.xlsx`.
- **호기 목록 = 장비 IP 주소 파일 기준**(고정 34호기 폐기). 호기 추가 = 이름+IP → 그 파일 기록.
  참고자료는 순수 메모, 특이사항/참고자료는 **셀 색상 저장** 지원. 탭에 '장비 IP' 추가.
- 폴더: `{저장폴더}/양식/{레시피}/{생성시간}/{레시피}_{호기}호기_참조_{시간}.xlsx`(확정),
  그 아래 `관련파일/`(`_원본_`·`_수정본_` 엑셀만 — **원본 ini 는 로컬**). `{저장폴더}/파라미터 값 취합/
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
- **기존 양식 수정하기 = 초안('원본') 기준(2026-08 확정)**: 확정 양식에는 **체크한
  항목만** 들어 있어 그것만 읽으면 파라미터를 **빼는 것만** 됐다. 그래서 회차 폴더의
  `관련파일/…_원본_….xlsx`(전체 후보 목록)를 찾아 그것으로 편집기를 연다
  (`workdirs.form_candidate_path` — `_원본_` 우선, 없으면 `_수정본_`).
  `formbuilder.initial_to_pivot`(사용=N 포함 전체 복원) +
  `merge_form_into_candidates`(확정본을 덮어써 사용 항목 체크·사람이 고친 이름/
  변환방식 유지). **매칭은 이름이 아니라 설정키**(`formbuilder.ext_key` =
  변형+설정파일+Section+설정Parameter, `collate._ext_key` 와 같은 원칙) — 이름으로
  맞추면 사람이 바꾼 이름이 '새 항목'으로 튄다. 확정본에만 있는 행은 덧붙여 보존.
  · **후보 유무를 미리 안내**: `workdirs.form_version_status` 로 레시피/버전 목록에
    `✔ 항목 추가 가능` / `⚠ 원본 없음` 을 붙인다.
  · **무엇을 기준으로 열지 항상 고른다**(`_ask_edit_source`) — ①저장된 원본(있을
    때·기본) 또는 다른 회차 원본 빌려오기(`any_candidate_for`) ②🖥 장비에서 다시
    읽어 합치기 ③📁 로컬에서 다시 읽어 합치기 ④확정본만으로 열기.
    **②③은 원본이 있어도 항상 노출**한다(2026-08) — 저장된 원본은 그때의
    스냅샷이라 **파서 규칙이 바뀌어도 반영되지 않는다**. 항목 구성까지 최신으로
    맞추려면 다시 읽어야 한다. `_recollect_for_edit(source=)` 가 고른 소스로
    수집→`merge_form_into_candidates`(기존 선택 유지, 새 항목만 추가).
    수집 staging 은 **반드시 로컬**(`localdirs.new_temp_run`).
  · **값은 스냅샷과 무관하게 최신 파서로 갱신된다**: `collate` 의 1차 키
    (`_ext_key`)에는 OpticPreset 섹션명이 들어가 target 이 바뀌면 깨지지만,
    target 의 `alg` 가 항상 `Scan2d` 로 통일돼 있어 2차 이름 키(`_name_key`)가
    붙는다. 그래서 **양식은 그대로여도 값 업데이트는 올바른 optic 값으로 채워진다**
    (양식의 항목 구성만 다시 읽기가 필요).
  · **원본은 항상 남긴다**: 종전에는 '엑셀에서 편집하기'를 거친 회차에만 초안이
    생겨 화면 편집기로 바로 확정한 회차는 되살릴 수 없었다. 이제
    `_form_param_editor.confirm()` 이 확정과 함께 원본을 쓴다
    (`_save_candidate_snapshot` / 기본 경로는 `work()` 안에서). 저장 실패는
    확정을 막지 않는다(E116/E119 로그만).
- **값 업데이트**: 레시피 선택 알림 → **IP↔호기 매칭창**(IP로 새 열 만들지 않음) →
  **하위 레시피(변형) 이름 매칭창**(양식에 없는 이름이 있을 때만) →
  `collate.build_collation`(설정키 매칭, **직전 취합본 이어받기**, 불일치 검출) →
  `파라미터 값 취합_{시간}.xlsx`.
  · 하위 레시피 이름은 장비마다 다를 수 있고(`2D+3D_CAMTEK` vs `2D+3D CAMTEK`)
    변형은 행 키의 일부라 다르면 값이 안 채워진다. **취합 전에**
    `collate.unmatched_variants`(비교는 `norm_key` — 대소문자·구분자 차이는 무시)로
    찾아 `_variant_match_dialog` 로 양식의 이름에 붙이고(또는 '제외'),
    `collate.apply_variant_map` 이 피벗의 `mag` 를 바꾼다. GUI=`_match_variants`.
- **레시피 삭제(2026-08 확정 — 범위 고정)**: 양식 만들기 탭 `🗑 레시피 삭제`
  (값 확인 카드 우클릭도 같은 창). `_delete_recipe_dialog`/`_delete_recipe_run`.
  · **지움** ①`양식/{레시피}/` 전체 — 지우지 않고 **로컬 `CamtekAOI/삭제보관/
    {레시피}_{시각}/` 으로 이동**(`workdirs.move_recipe_dir` +
    `localdirs.new_deleted_slot`, 되돌리기 가능) ②**최신** 취합본의 그 시트
    (`collate.delete_recipe`) ③`감시설정.json` 의 그 레시피(`watcher.drop_recipe`
    — 호기별 폴더 지정·목록·plan.recipe_map. 안 지우면 무인 회차가 없는 폴더를
    계속 찾아 실패 로그만 쌓인다).
  · **안 지움** 과거 취합본(이력 확인의 비교 대상) · `변환계수.xlsx`(레시피 키가
    없다 — 호기+변형 기준이라 여러 레시피가 공용) · 변경보고서 등 과거 기록.
  · **보관은 반드시 로컬**: 저장폴더 안에 백업을 만들면 지운 파일이 그대로 다시
    동기화된다(`move_recipe_dir` 이 저장폴더 안 경로면 ValueError).
  · 안전장치: 전역 잠금 `양식_{레시피}` · 미리보기(`recipe_delete_preview` —
    버전/파일/용량) · **레시피 이름 직접 입력**해야 버튼 활성 · 엑셀이 그 폴더
    파일을 열고 있으면 거부(파일이 양쪽에 걸쳐 남는 것 방지).
  · **되돌리는 법을 삭제 전·후 둘 다에서 안내**한다 — 지운 게 아니라 옮긴 것이라
    어디에 있는지 모르면 되돌릴 수 없다. 문구는 `_recipe_restore_text` 한 곳에서
    만들어 확인창과 완료창(`_recipe_deleted_window`, '📂 보관 폴더 열기' 버튼)이
    같은 내용을 쓴다. 절차 = 보관 폴더를 `{저장폴더}/양식/` 으로 옮기고 이름에서
    `_{시각}` 을 지운 뒤 ⋯파일 > 다시 읽기.
- **이력 확인**: 취합 폴더 파일 2개 선택 → `history.diff_files`(멀티시트) → **다른 부분만**
  새 창(Treeview) + 변경내역 엑셀(비고 메모).
- 오래 걸리는 작업은 `_run_busy` 로딩 모달 + 백그라운드 스레드.

헤드리스 모듈(모두 테스트됨): `refdata.py`, `workdirs.py`, `formbuilder.py`, `collate.py`,
`history.py`. 매칭 정규화는 **한글 보존**. (`versioning.py`는 폴더 버전으로 대체·삭제됨.)

## Commonality 조사 (브랜치 `claude/commonality-survey`, 설계: `docs/commonality_조사_설계.md`)

Scanresult 아래 여러 **Lot**의 파라미터 변경/공통성 조사. 탭 'Commonality 조사'.
경로 `{루트}/{호기}/Scanresult/{2D@디바이스_레시피}/{공정번호}/{S/M}/{슬롯}/`.
**조사할 슬롯(웨이퍼) 폴더는 S/M 선택창에서 고른다 — 다중 선택**(기본=이름순 첫 번째).
행 오른쪽 `슬롯 n/N ▾` 버튼 → `_cm_pick_slots`(체크박스 다중) · 하단 '슬롯 일괄:
첫 슬롯만/전체 슬롯'. 여러 개 고르면 `commonality.expand_wafers`/`expand_all` 이
**슬롯마다 별도 조사 대상**으로 펼치고 라벨에 `·{슬롯}` 을 붙인다(1개면 라벨 유지 =
이전 결과와 열 이름 연속). 관련 = `list_wafers`/`set_wafer`/LotFolder
`wafer_choices`·`wafer_picks`.
**S/M 폴더 매칭은 3단계까지만(2026-08 확정)**: ①정확일치 → ②포함(양방향) →
③**토큰 겹침**(`_tokens`, 'SUA RERURN PG8E10'·'PG8G17 NFN RETURN 2D+3D 100' 같은
오타·군더더기 흡수). **그래도 못 찾으면 '폴더 없음'** — 관계없는 폴더를 후보로
올리지 않는다(4단계 폴백 금지).
**①과 ②는 합쳐서 돌려준다(2026-08 수정)** — 종전에는 정확일치가 하나라도 있으면
거기서 끝내서 `ASD` 를 찾으면 `ASD` 만 나오고 `ASD X20`·`ASD REWORK` 같은 **변형이
통째로 숨었다**. 어느 것을 조사할지는 사람이 고르므로 후보를 다 올린다(정확일치가
맨 앞 = 기본 선택). ③은 ①②가 **둘 다** 빈 경우에만(느슨해서 노이즈가 된다).
공정번호는 `contains=False` 라 여전히 정확일치만(6412 ≠ 64120). 선택창에 **S/M 폴더 수정시각**(`folder_mtime` → `LotFolder.scan_time`)을 표시해 언제
스캔된 자료인지 보고 고르게 한다. 이 값이 **Scan 일자**로 조사 결과 엑셀의
**파라미터 첫 행**(헤더 1행 바로 아래 2행, Parameter=`SCAN_ROW_LABEL`, 각 S/M 열
밑에 시각)과 비교표 3번째 열에 들어간다. `read_lot_result` 는 그 행을 파라미터가
아니라 `scan_times` 로 빼서 돌려준다(비교표 파라미터 열에 중복되지 않게).
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
`read_optic_mag(_,prefix)`/`read_active_scan2d(_,prefix)`).
**접두 불일치 = '양식에 GlobalRTP 만' 증상(2026-08)**: `config_ini_files(prefix)` 는
GlobalRTP 만 공유본으로 폴백하고 OpticPreset/Zones 는 폴백이 없다. 그래서
RecipesInfo.ini 가 레시피를 2개로 선언했는데 폴더에 `RecipeN-OpticPreset.ini`/
`RecipeN-Zones/` 가 없으면 그 레시피는 GlobalRTP 만 읽혀 양식이 텅 빈다.
`form_preflight` 가 레시피마다 실제 파싱될 파일을 세어(`files[…]={global,optic,
zones,count,thin}`) `thin` 이면 진행 전에 경고한다(GUI `_cm_make_form`). 안전복사는 Recipe*-Zones/
및 접두 설정파일·RecipesInfo·ActiveScenarioOptics 까지 **상대구조 보존 복사**
(`downloader.collect_target_items`).

## Commonality 자동 감시 (2026-08 — 헤드리스 완료, **GUI 연결 남음**)

새로 생긴 **S/M 폴더**를 찾아 조사 계획에 넣는다. 헤드리스=`cmwatcher.py`(테스트됨).

- **감시 범위 = '감시 대상 Lot 계획'의 (디바이스, 공정번호)**(사용자 확정). 트리 전체를
  훑으면 호기당 폴더 수천 개를 매 회차 stat 해야 한다. 계획 조합만 보면 회차당 접근이
  **계획 행 수**로 끝난다. 경로 해석은 commonality 의 `_find_children`/`_bfs_exact` 재사용.
- **파일 이름을 구분한다**: `감시대상_Lot계획.xlsx`(무엇을 감시할지 — S/M 칸 없음, 그
  공정 아래 전부가 대상) vs `Commonality_Lot계획.xlsx`(무엇을 조사할지).
- **기억 키 = (디바이스, 공정, S/M) 정규화**(`sm_key`) — 경로로 기억하면 백업본
  (`Scanresult_260402` …)이 하나 생길 때마다 그 안 S/M 수백 개가 전부 '신규'로 잡힌다.
- **첫 회차는 기준선만**(`apply_scan` 이 `baseline` 을 보고 빈 목록 반환 — GUI 에 맡기면
  틀리기 쉬워 모듈에서 처리).
- **안정화 대기**: 폴더 수정시각이 `settle_minutes`(기본 10분) 이내거나 슬롯에 설정파일이
  없으면 미룬다(스캔이 끝나기 전에 폴더가 먼저 생긴다).
- **공정 폴더 mtime 이 그대로면 건너뛴다** — 디렉터리 mtime 은 자식 추가/삭제 시 바뀐다.
- 찾으면 알림 + **조사 계획에 행 추가**(`append_cm_plan`) — **생성일자**(`folder_created`,
  Windows=`st_ctime`)를 함께 적고, 사람이 관리하는 파일이라 **쓰기 전 백업 1부**.
  `생성일자` 열이 없는 구 파일에는 열을 만들어 채운다.
- 설정·상태는 **로컬** `CamtekAOI/Cache/commonality_감시.json`(Scanresult 루트 자체가
  로컬 설정이고 commonality 산출물도 로컬이라 그쪽에 맞춤). 장비 감시(`감시설정.json`)와
  **파일·잠금 분리** — 하는 일이 달라 한쪽 실패가 다른 쪽을 막으면 안 된다.
  주기/시간대/backoff 는 `watcher` 것을 재사용(복제 금지).
- **자동 조사까지 한다(2026-08 확정)**: 감지 → 계획 추가 → **안전복사 → 저장된
  양식으로 값 조사 → 결과 누적**(`cmwatcher.survey_items`).
  · **양식은 감시 대상마다**(`survey_key` = 호기+디바이스+공정. `set_forms`/`forms_for`/
    `missing_forms`). 감시를 켤 때 **대표 S/M 을 사람이 고르고** 그것으로 양식을
    만든다 — 후보는 `sm_candidates` 가 **생성일자 최신순**으로 준다(백업본 중복 제거).
    commonality 양식과 양식 만들기 양식은 **따로 관리**한다(형식은 같지만 섞지 않음).
  · **다중 레시피(RecipesInfo.ini)면 레시피마다 양식·조사가 따로다(2026-08 확정)**:
    `survey_key` 하나에 양식을 **목록**으로 묶는다(`set_forms`/`forms_for`, 각 항목
    `{form, recipe, prefix, sm}`. 구 단일 dict 는 1개 목록으로 정규화 — 하위호환).
    `_cmw_build_form` 이 `cm.detect_recipes` 로 감지→레시피별 순차 편집(접두 `RecipeN-`
    으로 그 레시피 파일만 파싱, 수동 조사 `_cm_process_recipe` 와 같은 원칙). 회차
    (`run_cycle`)는 `forms_for` 의 **모든 양식**을 돌며 `survey_items(recipe_prefix=)`
    로 각각 조사→레시피별 결과 파일. 예전엔 대상당 양식이 하나뿐이라 **2번째 레시피가
    조사에서 통째로 빠졌다**(접두 없이 base 파일만 읽어 Recipe-1 만 반영).
  · **결과는 (호기,레시피)마다 파일 하나에 누적**(`commonality.merge_lot_result`,
    `cmwatcher.result_path`). 회차마다 새 파일을 만들면 파일이 불어나고
    `build_comparison` 이 중복을 안 걸러 **같은 S/M 이 여러 행**으로 나온다.
    이미 있는 S/M 은 값 갱신, 파라미터 행은 기존과 합집합.
  · **슬롯은 이름순 첫 하나**(무인이라 못 고름) — 단 **내용이 있는 슬롯 중** 첫째다
    (`usable_slots`/`slot_has_config`). 빈 슬롯이 이름순 앞에 있으면 그걸 읽고 0건이
    된다. 어느 슬롯을 읽었는지 결과에 남긴다.
  · 결과 엑셀 정보 행 = **Scan일자 → 생성일자 → 조사슬롯**(헤더 바로 밑, 그 아래가
    파라미터). `read_lot_result` 가 셋 다 빼서 돌려주므로 비교표 파라미터 열에
    섞이지 않는다. 수동 조사에는 생성일자·조사슬롯이 없어 행도 안 생긴다(구 파일 호환).
  · **양식 매칭이 `min_match`(기본 0.5) 미만이면 열은 남기고 색으로 표시**한다
    (`LOWMATCH_FILL` 연한 빨강 — 사용자 확정 2026-08). 빼 버리면 그런 S/M 이
    있었다는 사실 자체가 사라져 왜 비었는지 알 수 없다. 표시는 결과 엑셀 헤더와
    비교표 식별칸(`build_comparison` 의 `low_rows`)에 함께 들어가고, `_정보` 시트의
    `LowMatch` 행으로 회차를 넘어 유지된다. 다시 조사해 제대로 맞으면 자동 해제.
- **GUI(2026-08 연결 완료, 2026-08 위치 이동)**: Commonality 탭 **최상단 배너**
  `🔔 자동 감시 (여러 호기 무인)`(`_cm_watch_banner`). 종전엔 조사 단계 맨 끝 7번
  카드라 **초기 화면(호기 미선택)에서 안 보였다** — 조사는 호기 1대씩이라 `if not
  (machine and root): return` 위쪽에서 걸러졌기 때문. 감시는 여러 호기를 한 번에 도는
  별개 기능이라 **저장폴더 확인 직후·조사 단계보다 먼저** 그려 진입 즉시 보이게 했다.
  · `_cmw_dialog` — ON/OFF · 주기(watcher 프리셋 재사용) · 시간대 · 안정화 대기 ·
    **계획 파일 2개**(감시 대상/조사) · 호기 체크 + 호기별 `📋 양식 지정…`.
  · `_cmw_forms_dialog` → `_cmw_make_form` → `_cmw_build_form`: 대상마다
    **대표 S/M 을 최신순 목록에서 고르고**(`sm_candidates`) 그 슬롯으로
    `_form_param_editor` 를 열어 확정 → `set_form` 으로 대상에 묶는다.
  · **회차 로직은 헤드리스**(`cmwatcher.run_cycle` — 스캔→계획추가→조사→저장).
    `_cmw_cycle_work` 는 로컬 루트·변환계수만 넘기는 얇은 래퍼다. 오케스트레이션을
    GUI 밖에 둬야 tkinter 없이 테스트가 잡는다(`should_run` 인자 실수처럼 회차
    전체가 죽는 버그를 예전엔 못 잡았다).
  · `_cmw_tick`(1분마다, 시작 40초 뒤 등록 — 장비 감시 10초와 **엇갈리게**) →
    `watcher.should_run(now, s, st)` → `run_cycle` → `_cmw_report`.
    무인이라 `_run_bg`(모달 금지), 트레이 숨김 중이면 풍선 알림.
  · 오류 코드 E180~E189.

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
  **장비 렌즈 특성 → 계수는 호기별·변형별로 관리한다(2026-08 확정, 키 = (호기, 변형))**.
  변형(PI/PI-bubble/x5/x20)이 곧 배율이라 같은 호기·같은 변형이면 레시피가 달라도 동일.
  · **키를 MAG 에서 변형으로 바꾼 이유(재발 금지)**: 종전 키는 (호기 + MAG)였는데(구
    2026-07 안), MAG(OpticPreset 최신 Scan2d 의 `Mag`)은 **target optic 이 바뀌면
    흔들려** 값 업데이트마다 계수가 달라졌다(실제 사고). 이제 매칭은 흔들리지 않는
    변형으로 하고, **MAG 열은 어떤 렌즈였는지 사람이 알아보는 참고열로만** 남긴다
    (`ini_parser.read_optic_mag` 로 계속 뽑아 기록하되 매칭엔 안 씀).
  저장 = 저장폴더 `변환계수.xlsx`[호기,MAG,변형,계수,비고](`coefstore.py`) — **오직 사람이
  관리한다**. 변형이 빈 행은 그 호기의 **공통 폴백**(변형 매칭이 안 될 때만).
  · **값을 읽는 작업은 이 파일을 절대 고치지 않는다(2026-08 확정, 재발 금지)**.
    종전에는 `_coef_lookup_cb` 가 조회 실패 시 RTP.txt 로 계수를 **자동 추정해 파일에
    써 넣었다**. 이제 조회는 읽기 전용이고, 못 찾으면 `None` → `scales`/기본으로
    폴백하며 **못 찾은 (호기,변형)을 상태바로 알린다**(`_coef_report_missing`).
  · 파일을 쓰는 곳은 **`_coef_from_form` 하나뿐** — 사람이 양식에서 계수를 확정할
    때만(`coefstore.apply_form_scales`, 사람 확정이므로 (호기,변형) 행을 덮어씀. MAG 는
    편집기 피벗의 `mags` 에서 알면 참고열로 함께 기록. **새 변형 행은 MAG 를 알 때만
    만든다** — 오타 변형 방지).
  · `coef_detector` 는 **양식 만들기 계수 입력창의 추천값**으로만 쓴다(사람이 확정).
  적용 = `scan_tree`·`collate` 의 `coef_lookup(호기, 변형)` 이 **조회만**(없으면 구
  `scales`/기본). 콜백 계약은 전부 **2-인자 `(호기, 변형)`** 로 통일. 값확인 화면
  `AOI-xx : PI` 옆에 변형별 계수 표시.
  구 방식(변형별 `추출_요약`)은 폴백으로 유지. 정확값 `0.8456665875666588`/`0.7696441409644141`.
- **IP↔호기**: 값 업데이트 수집 시 IP를 **호기(AOI-xx)에 매칭**(IP-파생 열 생성 금지).
- **변형 라벨 표기**: 버블은 하이픈 `PI-bubble`로 통일(언더스코어 `PI_bubble` 아님).
- **파일 분리 저장**: PI 계열 → `{stem}_PI.xlsx`(시트 PI_ALL), RDL 계열 → `{stem}_RDL.xlsx`
  (시트 RDL_ALL). 하나로 섞지 않음.
- **취사선택 UI**: 2개 섹션 — 위=기존 항목(기본 선택), 아래=신규 불러온 항목(기본 미선택).
  섹션별 전체선택/전체해제.
- **파싱 소스 (2026-07 변경 확정)**: `GlobalRTP.ini` + `OpticPreset.ini` + `Zones/*.ini`
  기준(extractor 방식). **RTP.txt 는 사용하지 않는다.**
  · **`ManReClassify.ini` 추가(2026-08)** — Classification Editor 설정.
    장비 `\\{IP}\c$\Bis\data\dds\` 에 있는 **장비 공용 파일**(레시피 폴더 아님).
    `collector.manre_path(ip)` 로 가져와 레시피마다 staging 에 함께 복사한다
    (`plan_files(manre=)`, 없으면 조용히 건너뜀 — 나머지 수집을 막지 않는다).
  · **commonality 는 Max Count 를 조사하지 않는다(2026-08 확정, 재발 금지)**:
    ManReClassify 는 장비 C드라이브 공용 파일이라 **Scanresult 슬롯에는 없다**.
    그런데 `config_ini_files` 의 고정 파일 집합에 `manreclassify.ini` 가 들어 있어,
    슬롯에 어쩌다 끼어 있으면(장비가 저장했거나 잘못 복사됐거나) commonality 파싱이
    Max Count 행을 만들어 조사에 섞였다. → `config_ini_files(include_manre=False)` /
    `scan_tree(include_manre=False)` 로 **commonality 경로에서만 제외**한다
    (`commonality._lot_configs`·`form_preflight`). 양식 만들기(장비 수집)는 그대로 포함.
  `rtp_parser.py`의 RTP.txt 파싱은 레거시로 남아 있으나 새 불러오기 경로에서는 미사용.
- **변형 인식 (2026-08 완화)**: 익숙한 이름은 그대로 — `BUBBLE` 포함=PI-bubble,
  `PI`/`PI3` 형=PI, `x5`/`x20`(또는 OpticPreset Scan2d Mag)=RDL 배율.
  **그 외에는 폴더 이름을 변형 라벨로 쓴다**(`_folder_label`). 장비 레시피 폴더가
  `2D+3D_CAMTEK`·`2D+3D_CAMTEK_BUMP`·`DUMMY` 처럼 규칙과 무관해서, 이름이 안 맞는다고
  버리면 구조가 멀쩡한 폴더를 통째로 못 읽었다("인식된 설정(config) 폴더가 없습니다").
  유효성 판정도 이름이 아니라 **내용**으로 — `ini_parser.config_valid`(파싱된 행이
  있으면 유효)를 쓰고, 구 `rtp_parser.config_valid`(이름 규칙)는 레거시로만 남긴다.
  **단 commonality 는 `scan_tree(folder_variant=False)`** — 거기서 config 폴더는 Lot 의
  슬롯 폴더(CX01…)라 폴더명을 변형으로 쓰면 Lot 마다 변형이 달라져 값이 한 줄로
  모이지 않는다.
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
- **OpticPreset 잡키도 남긴다 (2026-08 확정, 종전 필터 폐지)**: `Id`/`ZWafer`/
  `FocusPosAboveChuck`/`CreationMeasureDistance1,2`/`CreationMeasureIntensity1,2`/
  GUID 값도 **파서가 지우지 않는다** — 양식에서 체크박스로 고를 수 있어야 하므로.
  대신 기본 `사용=N`(광원 KEEP 9개 + 합성행만 Y). `rtp_parser._is_optic_noise` 는
  레거시 경로에만 남는다. 양식 만들기·commonality·값 업데이트 **모두 같은 파서**라
  한 번에 적용된다.
- **OpticPreset 행 변환방식 = 기본 계수 미적용(RAW, 사용자 확정)**: 표시명에 µ 가
  있을 때만 변환하는 공통 규칙(`resolve_transform`)을 그대로 쓰므로 OpticPreset 키는
  전부 RAW 다. 필요하면 **사람이** 편집기 '변환' 열에서 LINEAR/AREA 로 바꾸고, 그
  방식이 `_EXTRACT_MAP` 에 저장돼 **값 업데이트·commonality 결과·비교표 전부
  계수 적용값**으로 채워진다(`collate.collate_recipe`). commonality 결과 `_정보`
  시트에 적용 계수를 기록한다.
- **엑셀 편집 후 창 복귀 (2026-08)**: 양식 만들기·commonality 모두 '엑셀에서
  편집하기' → 엑셀을 닫으면 프로그램 확정 창이 자동으로 앞으로 나온다.
  `_file_in_use`(쓰기 열기로 잠금 판정) + `_watch_excel_close`(0.7초 폴링,
  '열림을 본 뒤 닫힘'일 때만) + `_return_from_excel`(창 복귀·안내 갱신).
  잠금 개념이 없는 OS 에서는 조용히 비활성(종전 동작 유지).

## 사내 보안 모니터링 오탐 방지 (2026-08 전수 검토 — `tests/test_network_manners.py`)

장비 접속은 `\\IP\c$`(관리공유)라 EDR/SIEM 이 원래 지켜본다. 기능은 그대로 두되
**패턴이 공격처럼 보이지 않게** 한다. IT 설명 자료 = `docs/IT보안_검토자료.md`.

- **빈 비밀번호로 net use 시도 금지(중대)**: 무인 회차가
  `connect_admin_share(ip, "amkor", "")` 를 장비마다 호출하고 있었다 —
  동작하지도 않으면서 로그온 실패(4625)를 장비 수 × 레시피 수 × 하루 4회 쌓아
  **무차별 대입 탐지 + 공용 계정 잠금**을 부르는 코드였다. → 접속 정보는
  `equip_app._watch_cred`(메모리 전용, 감시 설정창에서 입력)에만 두고,
  **없으면 net use 를 아예 켜지 않고** 기존 세션으로만 시도 + 로그 안내.
- **포트 스캔처럼 보이지 않기**: 연결 점검의 TCP 445 확인은 호스트 사이
  `watcher.PROBE_GAP_SEC`(0.4s) 간격.
- **측면 이동처럼 보이지 않기**: 무인 수집은 장비 사이 `equip_app.HOST_GAP_SEC`
  (2s) 간격 + 순차 접속 유지(6시간 주기라 영향 없음).
- **비밀번호는 디스크에 쓰지 않는다**: `감시설정.json`·config 어디에도 저장 금지.
- **자동 업데이트에 '직접 설치' 선택지**: 실행 중 exe 를 배치스크립트로 바꿔치기하는
  것은 백신 행위기반 탐지 대상이라, 확인창에서 [아니오]=게시 폴더만 열어 주는
  경로(`_open_program_dir`)를 제공한다.

## 보안/환경 제약 (반드시 준수)

- **Anaconda/conda 금지** — 회사 과금 + 경고받음. venv/시스템 파이썬만.
- **런타임 외부(인터넷) 네트워크 금지** — 사내 장비망(`\\IP\c$`) 읽기전용 수집만 예외
  (사용자 확정). OneDrive 동기화된 로컬 파일 + 장비 공유폴더 읽기.
- **의존성**: `openpyxl` + `tksheet`만. 추가 패키지 금지.
- **장비/원본 읽기 전용**: 원본 파일을 수정/삭제/이름변경/이동 금지.
- 지정 브랜치에서만 작업, 허락 없이 다른 브랜치 push 금지. 요청 없이 PR 생성 금지.

## 테스트 (venv 없으면 시스템 python3 + openpyxl 로도 동작)

```
python3 tests/test_refdata.py      # 4  (참고자료/특이사항 독립 파일 I/O·호기·IP·호기별 접속ID 공유)
python3 tests/test_coef_detector.py # 2 (RTP.txt↔ini 계수 역추정·near-1 제외)
python3 tests/test_ini_parser.py   # 20 (ini 파서/수집/경로/백업/계수/config폴더/ActiveScenarioOptics/복사금지optic제외/비선택optic표시/다중레시피)
python3 tests/test_formbuilder.py  # 10 (초안 생성·편집→확정 양식·계수 저장·초안→전체후보 복원·설정키 매칭)
python3 tests/test_form_candidates.py # 6 (원본 탐색/버전별 안내·다른회차 빌려오기·확정 시 원본 항상 저장·다시읽기 항상 선택)
python3 tests/test_collate.py      # 9  (레시피별 시트·전체 호기·직전 이어받기·불일치·하위레시피 이름매칭)
python3 tests/test_history.py      # 1  (멀티시트 비교·변경내역 엑셀)
python3 tests/test_pipeline.py     # 1  (참고자료→양식→취합→최신자동→이력 통합)
python3 tests/test_cmwatcher.py    # 20 (다중레시피 양식목록/하위호환·회차 레시피별 전부조사 포함) (새 S/M 감지·자동조사: 계획 이름구분·기준선 무알림·백업본 중복무시·안정화대기·mtime건너뜀·생성일자/계획추가·로컬설정·대표S/M최신순·대상별양식·첫슬롯(빈슬롯제외)·한파일누적·양식불일치 표시유지·GUI연결·회차 헤드리스(기준선/감지+조사/양식없음/루트없음/계수)
python3 tests/test_commonality.py  # 25 (Lot계획·폴더해석(느슨매칭·변형후보전부·Scan일자)·슬롯 다중선택·폴더/SM변형·다중레시피/중간폴더·접두불일치사전감지·Scanresult백업다중·fail색칠·안전복사·구조diff·취합·이탈색칠·Zone정렬)
python3 tests/test_coefstore.py    # 6  (변환계수.xlsx (호기+변형) I/O·lookup 읽기전용/공통폴백·OpticPreset MAG·양식 확정만 저장·값업데이트 무기록)
python3 tests/test_collector_safety.py # 3 (원본 read-only 보호·UNC 거부·dest≠src)
python3 tests/test_editor_model.py # 12 (편집기 GUI비의존: 사용규칙·격자계층·확정레코드·표시값 무예외·실파서왕복)
python3 tests/test_errlog.py       # 5  (오류 코드+traceback 로그·사용자 메시지·쓰기불가 방어)
python3 tests/test_updater.py      # 28 (버전비교·버전파일명·구버전정리·구매니페스트호환·동기화중단검증·로컬다운로드·교체스크립트 함정회피/cp949·롤백용 2개유지·게시폴더 형제위치/구위치이관·onedir감지·버전동일판정)
python3 tests/test_localdirs.py    # 9  (로컬 임시/로그 폴더·OneDrive 판정·Temp밖 삭제거부·정리)
python3 tests/test_recipe_delete.py # 8 (레시피 삭제 범위 고정: 미리보기·로컬보관 이동/되돌리기·저장폴더 백업 거부·최신취합만·감시설정 정리·되돌리기 안내)
python3 tests/test_onedrive_writes.py # 5 (저장폴더 쓰기 최소화: 폴더 지연생성·잠금 재기록 없음·수집 staging 로컬·무변경 시 취합 미생성)
python3 tests/test_network_manners.py # 7 (빈 비밀번호 net use 금지(무인·수동 둘 다)·장비별 자격증명·포트/장비 간 간격·직접 설치 경로)
python3 tests/test_tray.py         # 4  (트레이 상주 판단·비Windows 안전 no-op·메뉴 ID)
python3 tests/test_locking.py      # 11 (편집잠금 획득/타인읽기전용/만료인수/자기잠금회수·저장전재검증·전역잠금·접속자세션)
python3 tests/test_watcher.py      # 29 (주기 프리셋·시작=끝 첫실행·호기별 감시 레시피·주기/시간대/backoff·찢어진읽기제외·변경보고서·무변경무알림·연결점검 타임아웃/취소·대상 장비·레시피 선택·**미선택 호기 값 유지**·수집계획 왕복·보고서목록·공유상태·Job매칭 레벨별폴백·감시폴더 지정)
python3 tests/test_manreclassify.py # 10 (ManReClassify: index11 MaxCount·빈필드보존·0유효·Internal Bin/고객순서·줄중간';'·양식연결·commonality제외·dds수집/원본무변경)
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
  이 **양식 만들기와 같은 방식으로 장비를 훑어** Job 폴더 목록을 보여준다
  (`_browse_equipment_recipe`, `_pick_list_chooser` 재사용 — 경로 직접 입력 없음).
  **선택은 Job 폴더에서 끝난다** — 그 아래 Setup/Recipes/레시피는 `_collect_fixed_dir`
  이 `find_setup_candidates` 로 자동 스캔해 전부 읽는다(지정 단계가 Job/Setup/Recipes/
  Recipe 어디든 동작). 지정 직후 발견된 레시피 목록을 확인창으로 보여준다.
  **지정은 호기별**(`{호기: {레시피: 상대경로}}`) — 장비마다 Job 구조가 다르기 때문.
  좌측 호기 목록 + 우측 레시피별 경로, '이 호기 경로를 다른 호기에 복사' 제공.
  조회는 `watcher.path_for(rp, 호기, 레시피)`(구 버전 공통지정 `*` 폴백 유지). 고르면 `watcher.job_relative` 가 **`\Job\` 뒤 상대경로만**
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
- **자동 감시 설정창 UX (2026-08 재설계 — 사용자 지정)**: `_watch_dialog` 는 위에서부터
  **① 큰 ON/OFF 토글**(`paint_toggle` — 켜짐=초록 '● 켜짐', 꺼짐=회색) → **② 주기
  프리셋**(`watcher.INTERVAL_CHOICES` = 30분/1/2/4/6/8/12/24시간, 라벨↔값은
  `interval_label`/`interval_from_label`)·**실행 시간대** → **③ 장비별 표** →
  **④ 접속 방식**. 창 전체가 스크롤(Canvas)이고 버튼줄은 하단 고정.
  · **시간대 시작=끝(예 9시~9시) = '매일 그 시각에 시작'**(`watcher.first_run_at`) —
    0~0 만 '제한 없음'. 첫 회차는 다음 9시, 이후 주기 반복. 콤보 밑 `upd_wnote` 가
    지금 설정이 무슨 뜻인지 한 줄로 설명한다.
  · **감시 대상 = 호기별 레시피**(`watcher.machine_recipes` → `{호기: [레시피]}`).
    장비마다 감시할 레시피가 다르므로 전역 목록으로 묶지 않는다. 표의 각 행에서
    '레시피…'(`_pick_dialog`)로 고르고 '📁 폴더…'(`_watch_paths_dialog`)로 Job 폴더를
    지정하며, **폴더 지정은 필수**다(`collect_settings(require=True)` 가 미지정
    (호기/레시피)를 모두 나열하고 막는다 — 지정 없이 돌면 이름을 유추하다 엉뚱한
    폴더를 읽는다). 행 오른쪽에 `폴더 n/N ✓` 현황 표시(`refresh_row`).
    구 전역 목록 `machines`/`recipes` 는 `watcher.sync_selection` 이 지정에 맞춰
    자동으로 채워 하위호환을 유지한다.
  · 표 행은 **오른쪽 위젯을 먼저 pack** — expand=True 라벨을 먼저 붙이면 뒤 위젯이
    안 보인다(슬롯 선택창에서 겪은 것과 같은 함정).
  이후 조용히 수집·취합 → `history.diff_files` 로 직전과 비교 → **변경 있을 때만**
  알림 + `자동감시/변경보고서_{시간}.xlsx`. 무인이라 모달 금지(`_run_bg`).
  설정=`감시설정.json`, 로그=`자동감시/감시로그.txt`.
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
- **접속 계정은 장비마다 다르다(2026-08 확정)**: net use 를 고르면 설정창이
  **감시 대상 장비마다** ID·비밀번호 칸을 만든다(`build_creds`/`_keep_cred`).
  · **ID = 공유 파일** `장비 IP 주소.xlsx` 의 '접속ID' 열(`refdata.IP_HEADERS`,
    비면 `DEFAULT_LOGIN_ID`='amkor'). `login_id_for`/`set_login_id` + `save_ip` 로
    저장해 **다른 사람도 같은 값**을 쓴다(구 2열 파일도 그대로 읽힘).
  · **비밀번호 = 메모리 전용** `self._watch_cred = {호기: (ID, PW)}` — dict 다.
    한 벌로 묶으면 계정이 다른 장비마다 로그온 실패가 쌓인다.
    `_watch_collect` 는 장비마다 `all_creds.get(m)` 을 보고, **그 장비의 비밀번호가
    없으면 net use 를 켜지 않고** 기존 연결로만 시도한다(빈 비밀번호 접속 금지).
- **양식 만들기 장비 수집(`_collect_dialog`) — 2026-08 정리**: 호기별 접속 ID 를
  **고칠 수 있고 고치면 공유 엑셀에 저장**된다(`refdata.set_login_id`+`save_ip`).
  **공통 ID/비밀번호와 IP 직접입력은 삭제**(사용자 지정) — 장비마다 계정이 달라
  한 벌로 묶으면 실패가 쌓이고, 호기가 정해진 목록에서만 고르면 IP↔호기 매칭이
  필요 없다(`_map_ips_to_machines` 는 남겨두되 평소 미사용).
  net use 인데 비밀번호가 빈 장비가 있으면 **묻지 않고 막는다**(종전에는
  '빈 비밀번호로 시도할까요?'를 물어봤다).
- 오류 코드: 잠금 E150~E154, 감시 E155~E158, 트레이 E159~E160.

- **프로그램 아이콘**: `param_manager/data/para_icon.ico`(16~256, 투명 배경).
  생성기 `tools/make_icon.py` — **추가 패키지 금지**라 Pillow 없이 stdlib `zlib` 로
  PNG/ICO 를 직접 만든다. 웨이퍼+AOI 카메라+파라미터 슬라이더, 파랑→청록.
  ≤24px 는 글자를 빼고 실루엣만(뭉개짐 방지), ≥32px 는 'AOI' 표기.
  적용 = `equip_app.icon_path()` → 창(`iconbitmap`)·트레이(`tray.TrayIcon(icon_path=)`).

## OneDrive 동기화 폭주 대응 (2026-08 보안 경고 — 반드시 유지)

저장폴더(OneDrive) **안에 임시파일을 만들면** 파일마다 전원 PC로 동기화돼
'Unusual High-Volume Directory Access' 경고가 발생한다(실제 사고). 규칙:

- **OneDrive(저장폴더) = 결과물만**: 취합/양식/변경보고서 엑셀, 장비IP·특이사항·
  참고자료·변환계수, 감시설정, 잠금·접속자(공유가 목적이라 예외).
- **로컬(`localdirs.py`) = 중간 산물 + Commonality**: 수집 staging(원본 ini 복사본),
  로그, 캐시, **Commonality 조사 산출물**(Lot 안전복사본이 많아 공유 부적합).
  **삭제한 레시피 양식 보관**(`삭제보관/` — 되돌리기용, 저장폴더에 백업 금지).
  기본 = **프로그램 옆 `CamtekAOI/` 폴더 하나**(사용자 지정 2026-08). 단 프로그램이
  OneDrive 안이면 사고가 재발하므로 `%LOCALAPPDATA%` 로 자동 대체하고 첫 실행에
  경고한다. 첫 실행 때 변경 가능(config `local_dir`).
  구조는 `Temp/ Logs/ Cache/ Commonality/ 삭제보관/` 으로 고정. `set_root` 로 모듈 공유.
  Commonality GUI 는 `equip_app._cm_root()` 로만 경로를 만든다(save_dir 금지).
- **임시는 반드시 지운다**: `new_temp_run` → 작업 후 `drop()`, 시작 시 `cleanup_temp`
  (6시간 지난 잔재). `drop()` 은 **Temp 아래가 아니면 거부**(저장폴더 오삭제 방지).
- **잦은 쓰기 금지**: 세션 하트비트 60초→**300초**, 만료 5→15분, `touch_session` 은
  화면이 그대로면 **쓰지 않음**. 잠금 `refresh` 도 만료 절반 전에는 재기록 안 함.
- **로그는 저장폴더에 쓰지 않는다**: `errlog.log_path` 가 로컬 `Logs/` 로 간다
  (사용자는 화면의 오류 코드로 문의). 실패해도 예외 없이 bool 반환.
- 새 기능을 넣을 때 **저장폴더에 반복 쓰기를 추가하지 말 것** — 회차당 1개 결과
  파일이면 정상, 파일 수십~수백 개나 초/분 단위 갱신이면 로컬로 보낼 것.

### 2026-08 전수 재검토에서 고친 것 (재발 금지 — `tests/test_onedrive_writes.py`)

- **양식 만들기의 장비 수집본이 저장폴더로 갔다(가장 컸음)**: `_form_new` 가
  `_collect_dialog(related, …)` 로 `{저장폴더}/양식/…/관련파일/` 을 staging 으로 썼다.
  collector 는 레시피마다 `Zones/*.ini` 를 **전부** 복사하므로 호기 몇 대만 골라도
  수백 개 파일이 OneDrive 에 바로 생성된다(사고와 정확히 같은 패턴).
  → `localdirs.new_temp_run(local_dir, "양식수집")` 으로 변경. **`_collect_dialog`
  의 staging 인자는 언제나 로컬이어야 한다**(소스 수준 회귀 테스트로 고정).
- **취소해도 빈 폴더가 쌓였다**: `form_run_dir`/`related_dir` 가 경로 계산만 해도
  폴더를 만들었다. → `create=False` 인자 추가, 실제 파일을 쓸 때만 생성.
- **무인 회차가 변경이 없어도 취합 엑셀을 매번 만들었다**(6시간 주기면 하루 4개,
  1년 1400여 개). → 회차 취합본은 **로컬에 먼저 쓰고 비교**, `has_change` 이거나
  첫 취합일 때만 저장폴더로 옮긴다.
- **화면을 다시 그릴 때마다 `.editlock` 을 다시 썼다**: `locking.acquire` 의
  `mine` 분기가 무조건 `write_lock`. → `refresh`(만료 절반 전이면 쓰기 생략) 사용.

### 저장폴더에 남는 것(전수) — 이 목록 밖의 것을 늘리지 말 것

`장비 IP 주소/참고자료/특이사항/변환계수.xlsx`(4) · `감시설정.json` ·
`양식/{레시피}/{시간}/`(확정 1 + 관련파일 원본·수정본 2 = 회차당 3) ·
`파라미터 값 취합/`(수동 실행 1개, 무인은 변경 시에만 1개) ·
`자동감시/`(변경보고서 = 변경 시에만, `감시로그.txt` 1개에 append) ·
`_세션/`(접속자 json·전역 잠금, 300초 하트비트 + 내용 같으면 쓰기 생략) ·
문서 옆 `.editlock`(편집 중에만) · 형제 `프로그램/`(exe 2개 + 버전정보.json).
**Commonality 산출물·수집 staging·로그·캐시는 전부 로컬**(`localdirs`).

## 자동 업데이트 (2026-08 확정 A안 — OneDrive만, 인터넷 미사용)

GitHub 직접 폴링/다운로드는 기각(런타임 외부 네트워크 금지 위반 + exe 를 인터넷에서
받으면 MOTW 로 Defender/SmartScreen 경고가 오히려 늘어남 — OneDrive 배포 사고와
같은 유형). 이미 전원이 쓰는 **OneDrive 저장폴더를 배포 통로**로 쓴다.

- **게시 폴더 위치 = 저장폴더의 '옆'(형제, 2026-08 사용자 지정)**: 저장폴더를 `…\docs`
  같은 문서용 하위 폴더로 쓰기 때문에 안에 만들면 배포 exe 가 묻힌다. 그래서
  `{저장폴더의 부모}/프로그램/` 에 만든다(`updater.resolve_program_dir`). 부모를 못 쓰면
  (드라이브 루트·부모 없음) 예전처럼 저장폴더 안(`legacy_program_dir`). 구 위치에 게시된
  버전은 `active_program_dir` 로 **계속 읽히고**, 다시 게시할 때
  `migrate_legacy_program_dir` 가 롤백용 구버전까지 새 폴더로 옮긴다(두 곳 분산 방지).
- **게시(개발자)**: ⋯파일 > `새 버전 배포…(개발자용)` — build_exe.bat 로 만든 exe 선택
  + 버전·변경내용 입력 → `프로그램/버전정보.json`(배포 창에 실제 경로 표시) +
  **`Camtek_AOI_Parameter_manage_v{버전}.exe`**(파일명에 버전 포함, 사용자 지정).
  파일명이 매번 달라지므로 `publish` 가 게시 후 `prune_old_exes` 로 정리하되
  **최신 2개(신버전 + 직전 구버전)는 남긴다**(`KEEP_VERSIONS`) — 새 버전이 잘못되면
  `프로그램/` 폴더의 구버전 exe 를 그대로 실행해 되돌릴 수 있어야 하기 때문.
  '어느 것이 직전 버전인가'는 파일 시각이 아니라 **버전 번호**로 판단한다
  (`version_of_filename` — OneDrive 동기화로 파일 시각은 뒤바뀔 수 있음).
  우리 게시물(`EXE_PREFIX`/구 고정명)만 지우고 남의 파일은 둔다.
  업데이트하면 **로컬 exe 이름도 새 버전으로 바뀐다**(`local_target_path`) — 확인창에서
  이름 변경을 미리 알리고, 교체 스크립트가 구파일을 지운다(바로가기는 다시 만들어야 함).
- **확인(전원)**: 시작 0.5초 후 조용히 확인(`_check_update_prompt(manual=False)`),
  새 버전이면만 "새 버전 N 있습니다. 업데이트할까요?"(변경내용 포함). `⋯파일 >
  지금 업데이트 확인…` 은 '나중에' 기억을 무시하고 항상 확인 + 최신이어도 알려줌.
  소스 실행(`updater.is_frozen()==False`) 이면 자동 업데이트 자체를 건너뛴다.
- **적용**: 게시된 exe 를 **로컬 Temp** 로 복사(OneDrive 에 쓰지 않음) →
  `verify_download`(크기+SHA-256, **동기화 덜 끝난 파일 거부**) → 통과하면 교체용
  `.bat` 생성(`build_swap_script`: 현재 PID 종료 대기 → 기존 exe 를 로컬에 백업
  1개만 → 새 exe 로 교체 → 재실행 → 자기 삭제) → detached 로 실행하고 앱 종료.
  **사용자는 확인 한 번만, 재시작은 전부 자동.** 실행 중인 exe 는 자기 자신을 못
  지우므로 별도 프로세스(cmd)가 교체를 맡는다 — Windows 전용, 실기 검증 필요.
- 버전 비교(`updater.is_newer`)는 길이 다른 버전("3.1" vs "3.1.0")도 0으로 채워
  비교, 숫자 크기 비교(문자열 사전식 비교 함정 회피: "3.10.0" > "3.9.0").
- **교체 배치스크립트(`build_swap_script`) 3대 함정 — 반드시 유지**:
  ① cmd.exe 는 .bat 을 UTF-8 이 아니라 **시스템 ANSI(한국어=cp949)** 로 읽는다.
     UTF-8 로 쓰면 한글 경로가 깨져 엉뚱한 파일을 지운다. `_write_bat` 이 cp949 로
     쓰고, **문구는 전부 ASCII**(한 글자라도 cp949 밖이면 UTF-8 로 물러나 사고).
     실제로 주석의 em-dash(—) 때문에 깨졌었다 — `body.isascii()` 로 가드.
  ② **`timeout` 금지** — detached 실행은 콘솔이 없어 즉시 실패한다. `ping` 으로 대기.
  ③ **PID 문자열 매칭 금지** — `tasklist | find "1234"` 는 메모리 열("1,234 K")에도
     걸려 무한 대기. **복사 재시도**를 종료 판정으로 쓴다(잠금 풀림 = 종료, 로케일 무관).
  · 교체가 끝내 실패하면 **기존 exe 를 다시 실행**한다(사용자가 빈손으로 남지 않게).
  ④ **종료 판정 = 구 exe 삭제**(2026-08 실사고): 파일명에 버전이 들어가므로 새 이름은
     아무도 잠그지 않아 `copy → 새이름` 이 앱 실행 중에도 성공한다. 그걸 종료 판정으로
     쓰면 **앱이 살아 있는 채로 새 프로그램이 떠 2개가 동시 실행**되고, 실행 중이라
     못 지운 구 exe 가 남아 다음 실행 때 또 업데이트 알림이 뜬다. 실행 중인 exe 는
     삭제가 안 되므로 `del /q "%OLD%"` 성공을 종료 신호로 쓰고, 그 뒤에만 복사·실행한다.
- **중복 실행 방지(`singleinst.py`)**: 감시가 켜져 창을 트레이로 내린 상태에서 아이콘을
  다시 누르면 인스턴스가 2개가 됐다(감시도 두 벌 = 장비 배수 접속). Win32 명명 뮤텍스
  (`Local\CamtekAOI_Para_SingleInstance`)로 막고 `activate_existing(APP_TITLE)` 로
  **숨은 창을 복원**한다. 업데이트 직후 구 프로세스 종료를 기다려야 하므로
  `acquire(wait_sec=12)`. 비Windows 는 항상 획득 성공(no-op).
- **업데이트 알림 무한 반복 차단**: 교체 직전 config 에 `update_applied_version` 을
  기록하고, 재시작 후에도 버전이 그대로면 자동 알림 대신 상태바 경고만 띄운다
  (수동 확인에서는 사유를 알리고 재시도 여부를 묻는다).
- 수집(`_watch_busy`) 중에는 업데이트를 미룬다 — 앱을 종료시키므로 그 회차가 날아간다.
- **빌드(`build_exe.bat`) — "Failed to load Python DLL" 대책(2026-08 실사고)**:
  onefile exe 는 매 실행마다 `%TEMP%\_MEIxxxx` 에 python3xx.dll 을 풀어 로드하는데,
  백신 격리·세션별 임시폴더(`\Temp\1\`)·임시폴더 정리로 그 DLL 이 사라지면 실행 자체가
  실패한다. → **`--runtime-tmpdir %LOCALAPPDATA%\CamtekAOI\runtime`** 로 %TEMP% 를 피한다
  (부트로더가 `ExpandEnvironmentStringsW` 로 확장 — PyInstaller 6.x 필요, 그래서 pip 설치를
  `pyinstaller>=6.0` 으로 고정). 또 `--add-data "param_manager\data;param_manager\data"`
  가 없어 `rtp_template.json`·`para_icon.ico` 가 exe 에 안 들어가던 문제도 함께 수정,
  `--icon` 적용. 특정 PC 가 계속 실패하면 `build_exe.bat onedir`(폴더 배포, 추출 없음)로
  진단. **onedir exe 를 게시하면 전원이 실행 불가**이므로 배포 창이
  `updater.looks_like_onedir_build`(`_internal/`·python3xx.dll 형제 감지)로 막는다.
- **버전은 반드시 `build_exe.bat <버전>` 으로 찍는다(2026-08 실사고)**: 게시 파일명·
  매니페스트 버전은 **배포 창에 타이핑한 값**이지만, 실행 중인 프로그램이 보고하는
  버전은 exe 안의 `param_manager.__version__` 이다. 빌드 전에 그 값을 안 올리면
  파일 이름만 새 버전(`..._v4.0.2.exe`)이고 내용은 옛 버전이라 **업데이트해도 계속
  '새 버전 있음'** 이 뜬다(실제 발생 — 파일 교체는 정상이었고 버전만 안 올라갔다).
  → **버전을 타이핑하는 곳은 `build_exe.bat` 한 곳뿐**(인자를 안 주면 물어본다).
  `tools/set_version.py` 가 `__init__.py` 의 `__version__` 과 PyInstaller
  `--version-file`(exe 파일 속성)에 **같은 값**을 찍는다. **배포 창은 버전을 묻지
  않고** 고른 exe 에서 `updater.exe_file_version`(ctypes VERSIONINFO)로 읽어
  표시하며(`display_version` 이 '4.0.3.0'→'4.0.3'), 사람은 **파일 경로와 변경 내용만**
  입력한다. 버전 리소스가 없는 구 빌드일 때만 직접 입력(확인창).
  `--version-file` 은 **`build/` 에 두면 안 된다** — `--clean` 이 workpath 를 통째로
  비워 빌드가 실패한다(→ dist 에 반쪽 exe 가 남아 'Failed to load Python DLL').
  그래서 `tools/version_info.txt` 에 만들고, bat 은 빌드 전 dist 의 이전 exe 를 지우고
  빌드 후 산출물 존재를 확인한다.
  ⋯파일 > **프로그램 정보…**(`_about_dialog`)에서 실행 중인 exe 경로·게시 폴더의
  exe 목록과 각 파일 버전을 볼 수 있다(어느 파일이 도는지 확인용).

## 핵심 파일

- `param_manager/ini_parser.py` — **새 1차 파서**: GlobalRTP/OpticPreset/Zones ini →
  Para 스키마(Zone/Alg/Parameter) 정규화, KNOWN_DISPLAY_MAP·계수 변환, 피벗.
  **OpticPreset LIGHT/Scan2d 통일**(`_parse_optic`): target 섹션만 alg=`Scan2d` 로
  통일, `OPTIC_SCAN2D_KEEP`(9개)만 사용=Y, `Scan2d 최신 항목 이름` 합성행 추가.
  **target 이 아닌 optic 도 목록에는 전부 남긴다(사용=N, 2026-08 확정)** — 종전에는
  이름이 `Scan2dN` 형인 섹션만 통째로 버려서 `[Align optic]` 은 보이고 `[Scan2d1]` 만
  사라지는 비일관이 있었다. '보이는 것'과 '기본 체크'를 분리한다. 비선택 섹션 이름이
  하필 `Scan2d` 면 target 과 Alg 가 겹쳐 피벗에서 한 줄로 합쳐지므로
  `_other_optic_alg` 가 `OPTIC_OTHER_SUFFIX`(' (미선택)')를 붙여 갈라 놓는다. `ExtractRow.use_default`→피벗 `use`→formbuilder.
  **target(현재 스캔 optic) 선택(`_pick_optic_target`)**: **①'복사 금지' optic 을 먼저 제외**
  (2026-08 — 이름 **끝**이 `_@NEVER COPY THIS!!!!!` 면 후보에서 뺀다. `optic_excluded`,
  느낌표 수·대소문자·뒤 공백 무시, 섹션명뿐 아니라 `Alg`/`OpticsName`/`Name` 키도 본다.
  OpticPreset 에는 리뷰·얼라인·clean reference 옵틱이 순서와 무관하게 섞여 있어, 안 빼면
  '마지막 광원 섹션' 규칙에 리뷰 옵틱이 걸려 **엉뚱한 값이 clean reference 값인 척**
  취합된다). ② 그 뒤는 종전 그대로 — 신 SW = 같은 폴더 `ActiveScenarioOptics.ini`
  의 `ScenarioName=Scan2d` 항목 `OpticsName`/`OpticId` 로 OpticPreset 섹션 매칭(`read_active_scan2d`).
  없으면(구 SW) 기존 방식 = CameraName=TDI·광원키 가진 **마지막** 섹션. `read_optic_mag` 도 동일 경로
  (제외본의 Mag 를 계수 키로 쓰지 않는다). 전부 제외되면 target 없음(예외 없이 진행).
  (`collector.FIXED_FILES` 에 ActiveScenarioOptics.ini 포함 — 있을 때만 복사.)
  **변환 판정(`resolve_transform`)**: 표시명에 **µ(마이크로) 있으면 변환**(area→AREA,else LINEAR),
  **없으면 RAW**(예: 'Min Defect Width'는 변환 안 함). BOOL/REGION/CLASSIFY는 유지.
  **GlobalRTP**(`GLOBALRTP_KEEP`): `Max Defects Per Wafer/Die`만 기본 사용=Y, 나머지 N.
  변환방식 라벨은 실제 계수 반영(`label_transform`).
  **config 폴더 파싱 대상(`config_ini_files`)**: 폴더 바로 아래는 **GlobalRTP.ini/
  OpticPreset.ini 만**(그 외 .ini 제외 — 쓸데없는 항목 방지, _N 접미사 인식) + **Zones/*.ini 전부**.
- `param_manager/manreclassify.py` — **ManReClassify.ini 전용 파서**(Classification
  Editor). `[General]` 각 행 = `Code=Desc,Status,Priority,Color,KeyCode,KeyModifier,
  Intern,Display,GrabImage,Verify,Extended,MaxCount,CustomerBin0,…`.
  · **Max Count = 쉼표 분리 0-based index 11**, Internal Bin = index 12(고객 Bin 0번),
    고객 Bin 순서 = `[Customers]` 순서(`read_customers` — 정렬 금지, 순서가 의미).
  · **빈 필드 보존**(연속 쉼표를 합치거나 당기면 열이 통째로 밀린다) ·
    **MaxCount 0 은 유효**(빈 문자열만 결측) · 주석은 **줄 맨 앞 `;`** 만.
  · **공용 `parse_ini_sections` 를 쓰면 안 된다** — `strip_comment` 가 줄 중간 `;` 를
    자르고 `\_` 치환·형변환까지 해서 Desc/열이 깨진다. 그래서 전용 리더(`_read_sections`).
  · 양식에 넣는 건 **Max Count 뿐**(사용자 확정) — `ini_parser._parse_manre` 가
    Zone=`Classification`/Alg=`Max Count`/Parameter=`{코드} {분류명}`/설정키=코드로
    ExtractRow 를 만든다. 코드가 수십 개라 **기본 사용=N**, 변환은 **RAW**(개수라
    픽셀→µ 계수 적용 금지). 나머지 필드의 뜻은 `manreclassify.py` 상단에 적혀 있다.
- `param_manager/collector.py` — 장비 네트워크 읽기전용 수집(net use, plan 자동 재사용).
  `FIXED_FILES`에 **RTP.txt 포함**(계수 자동 추정용). RTP.txt는 recipe 폴더에 위치.
  **Zones/ 하위구조 보존 복사**(staging 에 `Zones/*.ini` 그대로 — 파서 규칙과 일치).
- `param_manager/coef_detector.py` — **변환 계수 자동 추정**: RTP.txt(표시값)↔Zone ini(원본값)
  known 쌍 비교(LINEAR=disp/raw, AREA=√). 1.0 근처(직접단위) 제외, 군집·신뢰도. `detect_from_dir`.
- `param_manager/refdata.py` — **참고자료/특이사항 독립 파일 I/O**: `REF_HEADERS=[호기,IP,비고]`,
  `IP_HEADERS=[호기,IP,접속ID]`·`login_id_for`/`set_login_id`(장비 접속 계정 공유),
  load/save/create_blank, `machines()`/`ip_for()`/`add_machine()`.
- `param_manager/coefstore.py` — **변환계수.xlsx (호기+변형) 저장소**: `[호기,MAG,변형,계수,비고]`
  load/save/create_blank, `lookup(rows,호기,변형)`(대소문자·구분자 무시·변형 빈 행=공통 폴백),
  `upsert`(사람값 우선), `machine_coefs`(표시), `make_lookup`(scan_tree/collate 공용 콜백
  `(호기,변형)`), `apply_form_scales`(양식 확정 계수 반영). MAG 열은 참고용(매칭 안 함).
- `param_manager/workdirs.py` — **저장폴더 기준 경로**: `form_run_dir/form_final_path/
  form_original_path/form_draft_path/related_dir/list_form_versions/collate_path/
  latest_collate/list_collate_files` + `form_candidate_path`/`form_version_status`/
  `any_candidate_for`(기존 양식 수정용 '원본' 탐색·안내) +
  `recipe_delete_preview`/`move_recipe_dir`(레시피 삭제 — 저장폴더 안 보관 거부).
  (구 initial/final/백업 함수는 레거시.)
- `param_manager/extract_io.py` — 스냅샷(공용 양식 + `_EXTRACT_MAP`) + `write_snapshot(scales=)`/
  `read_scales`(변형별 계수 저장/판독).
- `param_manager/formbuilder.py` — **양식 만들기**: `build_initial_workbook`(수정본, '사용'/
  '최종 Parameter')·`build_final_from_initial`(→확정 양식+`_EXTRACT_MAP`+계수).
  **기존 양식 수정용**: `initial_to_pivot`(초안→전체 후보, 사용=N 포함)·`ext_key`/
  `form_ext_keys`/`form_overlay`/`merge_form_into_candidates`(확정본을 후보 위에 덮기).
- `param_manager/updater.py` — **자동 업데이트**(v3.0, A안): 위 섹션 참고.
- `param_manager/localdirs.py` — **로컬 작업 폴더**(OneDrive 밖): `default_root`
  (`%LOCALAPPDATA%\CamtekAOI`)·`set_root/active_root`·`ensure`(Temp/Logs/Cache)·
  `new_temp_run`/`drop`(Temp 밖 거부)/`cleanup_temp`·`is_under_onedrive`·`describe`·
  `deleted_dir`/`new_deleted_slot`(삭제한 레시피 양식 보관 — 되돌리기용).
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
- `param_manager/collate.py` — **값 취합(멀티시트)**: `delete_recipe`(시트 제거) + `build_collation`(레시피별 시트, 참고자료
  전체 호기, 직전본 이어받기, 설정키 매칭·불일치), `write_collation`/`load_collation`/
  `load_as_repo`(값 확인 병합). **값은 양식의 변환방식(_EXTRACT_MAP transform)을 수집 raw 에
  재적용**(사람이 양식에서 고친 변환방식·계수 반영). 계수 우선순위: `coef_lookup(호기,변형)`
  → 라벨 계수(`ini_parser.scale_from_label`) → 기본. commonality 도 같은 경로 재사용.
- `param_manager/history.py` — **이력 확인**: `diff_files`(멀티시트 값변경/추가/삭제)·
  `write_diff_excel`(변경내역+비고 메모).
- `param_manager/equip_app.py` — tkinter GUI(저장폴더 모델). `_startup`/`_choose_save_dir`/
  `_load_refdata`/`_load_latest_collate`, 호기 그리드=참고자료, `_view_special`/`_view_reference`
  (독립 파일), `_view_form`/`_form_new`/`_form_build_and_edit`/`_form_finalize`(실제 Excel),
  `_load_previous_form`, `_ask_scales`(변형별 계수), `_map_ips_to_machines`(IP↔호기),
  `_update_values_dialog`/`_update_collate_flow`/`_update_write_results`, `_history_dialog`/
  `_show_diff_window`, `_run_busy`(로딩), `_file_menu`(저장폴더/다시읽기/다운로드).
  하단 상태바 = `_set_status(msg, warn=)` — 문구가 있을 때만 **✕(닫기) 버튼**이 붙고
  (`clear_status`), warn=True 면 빨강. 경고문이 화면에 계속 남지 않게 한다.
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
  (`scanresult_root`/`resolve_lot`/`resolve_plan`, 디바이스명+LOT+S/M, `list_wafers`/
  `set_wafer` 로 슬롯 선택·기본은 이름순 첫),
  안전복사(`copy_lot`), Lot 파싱→통합 피벗(`parse_lots`)·구조 diff(`structure_diff`),
  값 취합(`collate_lots`/`write_lot_result`/`read_lot_result`), 호기 비교
  (`build_comparison`/`write_comparison`, 과반수 이탈 색칠 `MISMATCH_FILL`).
