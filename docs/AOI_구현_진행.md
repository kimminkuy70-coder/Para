# AOI 스펙 구현 — 진행/인수인계 (모델 교대용)

> 이 문서는 **세션이 끊겨도(예: Fable→Opus 교대) 맥락 없이 이어받아** 구현을
> 계속할 수 있도록 쓴다. 작업 시작 전 이 문서 + `CLAUDE.md` +
> `docs/불러오기_통합_설계.md`(기존 기계장치 설계)를 먼저 읽을 것.
>
> - 작업 브랜치: `claude/program-dev-prompt-file-f2oept`
> - 베이스: `claude/program-load-feature-overhaul-bc4xbf`(가장 완성도 높은 기존 구현)
> - 원 스펙: 업로드된 `AOI_____________________.md`(요약은 §1)
> - 참조 코드: 업로드된 `recipe_param_extractor_network_v4.py`(터미널 extractor, 이미 이식됨)

## 0. 사용자 확정 결정 (2026-07-06, 재질문 금지)

1. **구현 베이스**: 기존 `bc4xbf`의 엔진·헤드리스 모듈(수집·파싱·양식·값갱신)을
   **그대로 재사용**하고, UI만 AOI 스펙대로 재편한다. 처음부터 새로 쓰지 않는다.
2. **양식 만들기 편집 방식**: initial 엑셀을 **실제 Excel로 열어** 사람이 편집·저장 →
   프로그램의 **'편집 완료' 버튼**을 누르면 그 파일을 다시 읽어 final(양식) 생성.
   (창 닫힘 자동감지는 불안정하므로 명시적 버튼 방식 채택. 실제 Excel은 그대로 사용.)
3. **범위**: AOI 4개 기능 전부 구현하되 **기능 단위로 커밋**하고 이 문서 체크리스트를
   갱신해 언제든 이어받게 한다.

## 1. AOI 스펙 요약(원문 구조)

- **⋯파일 메뉴 단순화**: '특이사항 엑셀 불러오기', '참고자료 엑셀 불러오기'만 남긴다.
- **'파라미터' 탭 → '파라미터 값 확인'** 으로 이름 변경. 화면에서 **값 직접 수정 기능 제거**
  (읽기 전용). 나머지 UX(트리 탐색·색/비고 등 보기)는 유지.
  - 그 안에 **'파라미터 값 업데이트'** 기능 추가: 여러 장비 IP 입력 → extractor 방식으로
    값 수집 → **양식 파일 기준 호기별 값 열 추가**한 취합 엑셀을 **레시피마다 각각** 생성.
    - 어떤 레시피(PI#/RDL#)를 할지 **선택 알림창**.
    - 양식 ↔ 실제 파일 파라미터 **불일치 시** 어느 항목이 안 맞는지 알림 + **불일치로 표기** +
      **그래도 생성할지 물어보기**.
    - **항상 새 버전으로 저장**(이전 버전 보존 → 엑셀로 열람 가능).
    - 호기별 값 확인은 엑셀이 아니라 **기존 UX 프로그램 화면**으로 본다.
  - **'파라미터 이력 확인'** 기능 추가: 저장된 취합 엑셀들 비교 → 바뀐 부분/특이사항/히스토리.
    - 달라진 부분을 **엑셀로** 만들고, **비고로 사람이 메모**.
- **'양식 만들기'** 새 기능(파라미터/특이사항/참고자료 외):
  - 버튼 → **PI#/RDL# 레시피 선택**(PI2/PI3/PI4, RDL1~RDL4).
  - 선택 → 해당 레시피 **양식 파일 창(실제 Excel)** 열림.
    - **신규(장비 폴더에서)** or **기존 저장 엑셀** 선택.
      - 기존: **어떤 버전** 열지 선택창.
      - 저장 후 닫으면 **덮어쓰기 / 새 버전** 선택창.
      - 신규: extractor 방식으로 **initial 엑셀** 생성→실제 Excel로 열기→사람 수정→'편집 완료'
        누르면 **final(양식)** 생성. **원형 initial은 따로 보존**.
- **응답없음 방지**: 오래 걸리는 동작에 **'로딩 중' 알림창** + 백그라운드 처리.

## 2. 기존 재사용 자산(이미 있음)

- `ini_parser.py` — `scan_tree()`, `build_pivot()`, `ExtractRow`, `KNOWN_DISPLAY_MAP`,
  `transform_value`(SCALE 0.8452). 파싱 소스 = GlobalRTP/OpticPreset/Zones ini.
- `collector.py` — `collect_equipment(ip, staging, chooser, …)` 읽기전용 수집, `CollectPlan`
  자동 재사용, `split_ips`, `is_windows`.
- `workdirs.py` — `initial_run_dir/final_run_dir/staging_dir/backup_shared_file`.
- `extract_io.py` — `write_snapshot()`(공용 양식 + `_EXTRACT_MAP` 숨김시트 + 요약),
  `read_extract_map()`.
- `refresh.py` — `plan_refresh()/apply_refresh()`(값 갱신 미리보기/적용).
- `engine.py` — `create_from_records()`, `ParamRepository`, 저장/이력/병합, `_s`, `norm_key`.

## 3. 신규 헤드리스 모듈(이번 작업 — 테스트 가능, 우선 구현)

- [x] `versioning.py` — "항상 새 버전 저장" 파일명 규칙 + 버전 목록/최신. (테스트)
- [x] `formbuilder.py` — 양식 만들기: `build_initial_workbook()`(편집용 initial, 사용/최종
      Parameter 열 + `_EXTRACT_MAP`), `build_final_from_initial()`(편집된 initial→final 양식).
      (테스트)
- [x] `history.py` — 취합 엑셀 2개 비교 → 변경 레코드 + 비고 메모, diff 엑셀 출력. (테스트)
- [x] `collate.py` — 양식 파일 + 파싱 피벗 → **호기별 값 열 추가 취합**(레시피별) + **불일치
      항목 목록**. `refresh.plan_refresh` 재사용. (테스트)

## 4. GUI 재편(equip_app.py — 정적검증만; Windows 실기 검증 필요)

- [ ] G1. 상단 탭: `파라미터`→`파라미터 값 확인`, `양식 만들기` 탭 추가. (탭 순서/스타일)
- [ ] G2. `파라미터 값 확인` 화면 **읽기전용화**: 값 셀 편집 팝업/`_set_value` 진입 차단
      (보기·색·비고·이력 확인은 유지). 상단에 `[값 업데이트]` `[이력 확인]` 버튼.
- [ ] G3. `⋯파일` 메뉴 단순화 → 특이사항/참고자료 엑셀 불러오기만. (양식/값 열기는 각 기능에서)
- [ ] G4. `양식 만들기` 탭: PI/RDL·레시피 선택 → 신규(수집/로컬)/기존(버전) → 실제 Excel+완료.
- [ ] G5. `파라미터 값 업데이트` 다이얼로그: IP 입력 → 레시피 선택 알림 → 수집 → collate →
      불일치 알림/표기/생성확인 → **새 버전 저장**(레시피별) → 화면 표시.
- [ ] G6. `파라미터 이력 확인` 다이얼로그: 취합 엑셀 버전 2개 선택 → history diff 표시 →
      diff 엑셀 저장 + 비고 메모.
- [ ] G7. `로딩중` 모달 + 백그라운드(threading/after)로 수집·파싱·저장 래핑.

## 5. 테스트

```
python3 tests/test_versioning.py
python3 tests/test_formbuilder.py
python3 tests/test_history.py
python3 tests/test_collate.py
python3 tests/test_ini_parser.py   # 기존
```

## 6. 알려진 한계 / 후속(Windows 실기 필요)

- 이 개발환경: GUI(tkinter)/Windows(net use)/Excel 미지원 → 헤드리스는 실행검증,
  GUI는 정적검증. 실제 장비망·Excel 연동은 Windows에서 최종 확인 필요.
- 실제 Excel 열기 = `os.startfile`(Windows). 비-Windows/Excel 없음 → 안내 후 내장표 폴백.
- 원본 장비 파일 **읽기/복사만**(수정·삭제·이동 금지), 복사 간 0.1s 지연 유지.
- 의존성: `openpyxl` + `tksheet`만. conda/인터넷 금지.
