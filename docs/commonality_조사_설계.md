# Commonality 조사 기능 — 설계/구현 계획

> 브랜치: `claude/commonality-survey` (feature 브랜치 `claude/program-dev-prompt-file-f2oept`
> 에서 분기). 기존 저장폴더 모델·모듈을 **최대한 재사용**한다. 이 문서는 세션이 끊겨도
> 이어서 작업할 수 있도록 단계·모듈·미결정 항목을 모두 적는다.

## 0. 한 줄 요약

Scanresult 폴더의 여러 **Lot**(웨이퍼 로트)들에 대해 파라미터가 바뀐 부분이 있는지
**이력/공통성(commonality)** 을 조사한다. 호기 1대씩 → Lot 폴더 선택 → 안전 복사 →
(양식 만들기와 동일한 방식으로) 조사할 파라미터 양식 확정 → Lot별 값 조사 엑셀 →
호기 취합·비교(불일치 색칠) → 변경/이상치 뷰어.

기존 **양식 만들기 + 파라미터 값 확인** 흐름과 유사하되, 대상이 "장비 레시피 현재값"이
아니라 "**Scanresult 아래 실제 검사된 Lot들의 값**"이라는 점이 다르다.

## 1. 대상 폴더 구조 (핵심)

```
{루트}\{AOI-호기}\Scanresult\{2D@디바이스_레시피}\{공정번호}\{S/M}\{웨이퍼번호}\
                                                                   ├─ Zones\*        (하위 ini 전체)
                                                                   ├─ RTP.txt        (표시값 — 계수 추정)
                                                                   └─ OpticPreset.ini
```

예시:
- `X:\AOI-6\Scanresult\2D@R2-1M3_0855360PD-0A\6321\HPG\CX05129990C4\`
- `W:\AOI-9\Scanresult\2D@R3-S6WH11001-00001_0851974PD-0C\6322\TVS\65328D00001\`

레벨 해석:
| 레벨 | 예시 | 의미 |
|---|---|---|
| `AOI-6` | 호기 | 장비 호기(= 장비 IP 주소.xlsx의 호기) |
| `2D@R2-1M3_0855360PD-0A` | 레시피/디바이스 폴더 | 폴더명 안에 **디바이스명** 포함(`2D@R3-S6WH11001-00001_...` → 디바이스 `S6WH11001-00001`) |
| `6412` | 공정번호 | 조사 단위 공정(폴더 레벨) |
| `HPG` / `TVS` | S/M | (Slot/Map 추정 — **확인 필요**) |
| `CX05129990C4` | 웨이퍼번호 | **이름순 1번째** 웨이퍼 폴더의 파일만 조사 |

- **웨이퍼 폴더는 이름순 첫 번째 1개만** 조사한다(동일 위치에 여러 웨이퍼 번호 존재).
- `downloader.parse_scanresult_path()` 가 이미 이 구조를 파싱한다
  (`equipment/recipe_name/setup/recipe_code/wafer`
  = 호기/`2D@..`/공정번호/`S/M`/웨이퍼). **재사용**.

## 2. 동작 단계 (사용자 지정 7단계)

### Step 1 — 조사할 장비 IP 선택 (1대씩)
- `장비 IP 주소.xlsx`(refdata) 목록을 띄워 호기/IP **1개** 선택.
- 선택한 호기 → **Scanresult 루트 경로 확정**.
  - ⚠️ **미결정**: IP↔루트(드라이브 X:/W:) 매핑 방식. 예시가 호기별 매핑 드라이브라서
    IP만으로 루트를 알 수 없음. 계획: **호기별 Scanresult 루트를 config 에 저장**
    (첫 사용 시 폴더 브라우즈로 지정 → 재사용). 후보: `\\{IP}\...\Scanresult` 접근도 옵션.

### Step 2 — 호기별 조사할 Lot 폴더 선택 (엑셀 업로드)
- **Lot 계획 엑셀 템플릿을 프로그램이 생성**해서 사용자가 수정하도록 띄운다.
  - 열: `1=디바이스명, 2=공정번호, 3=S/M, 4=AOI호기`.
- 업로드 → **선택한 호기 행만** 필터.
- 각 행을 실제 폴더로 해석: 디바이스명(→ `2D@..` 폴더 매칭) + 공정번호(→ `{공정번호}` 레벨)
  + S/M(→ `{S/M}` 레벨). **폴더 실재 확인**.
- 알림창: 찾은 Lot 폴더 목록(이대로 진행) / **추가할 Lot 폴더 수동 선택**.

### Step 3 — 조사 폴더/파일 복사 (수정 절대 금지)
- Lot마다 **이름순 첫 웨이퍼 폴더**의 `Zones\*` + `RTP.txt` + `OpticPreset.ini` 만 복사.
- `downloader.copy_wafer()`/`collect_target_items()`/`copy_one_file()` **재사용**
  (원본 read-only, `.part`→replace, 해시 검증 옵션). 저장 위치는 저장폴더 하위 staging.

### Step 4 — 조사할 파라미터 양식 확정 (양식 만들기와 동일 방식)
- **양식 제목(레시피명)은 양식 만들기 전에 사용자가 직접 지정**.
- 대표 Lot 1개를 `ini_parser` 로 파싱(OpticPreset 추림·변환계수·추천 파라미터
  = 기존 양식 만들기와 동일 규칙). 계수는 RTP.txt 로 `coef_detector` 자동 추정 후 추천.
- `formbuilder.build_initial_workbook()` 로 **편집용 엑셀** 생성 → 사용자가 사용/최종
  Parameter 수정 → `build_final_from_initial()` 로 확정(+`_EXTRACT_MAP`).
- ⚠️ **Lot마다 파일이 동일하지 않을 수 있음 → 확인 절차**: 모든 선택 Lot의
  **설정키 구조(파일/섹션/키 집합)를 비교**해서, 대표 Lot과 다른 Lot이 있으면
  "구조 불일치" 경고 + 어떤 Lot이 어떤 키에서 다른지 안내.

### Step 5 — 선택 Lot들의 파라미터 값 조사 → 엑셀
- 확정 양식의 `_EXTRACT_MAP`(설정키) 기준으로 **각 Lot의 값**을 읽어 채운다.
- 호기 1대 결과 엑셀 저장: 행=파라미터, 열=Lot(+메타). (`collate` 방식과 유사, 호기 대신 Lot 열)

### Step 6 — 호기별 취합 및 비교 (불일치 색칠)
- 여러 호기의 Step 5 엑셀들을 다시 취합.
- **파라미터 항목 동일성 체크**, 불일치 셀 **색깔 처리**.
- 레이아웃(사용자 지정): `1열=공정번호, 2열=장비 호기, 3열~=파라미터`.
  → 각 **행 = (공정번호, 호기)**, 열 = 파라미터(Step 5의 전치 형태).
- 색칠 기준: 파라미터 열별 **과반수(mode) 대비 이탈 셀** = 변경/이상 후보.

### Step 7 — 변경이력/이상치 뷰어
- Step 6 엑셀을 입력으로 **뷰어 구현**(의존성 제약: tkinter/tksheet/openpyxl 만).
- **추천/구현안**: tksheet 격자 뷰어
  - 파라미터 열별 과반수 대비 이탈 셀 히트맵 색칠,
  - "**변경된 파라미터만 보기**" 필터(모든 행이 동일한 열 숨김),
  - 파라미터별 이탈 요약(고유값 개수 · 어떤 공정/호기가 다른지),
  - 정렬/검색. (외부 시각화 라이브러리 금지라 matplotlib 등 미사용.)

## 3. 신규/재사용 모듈

### 신규
- `param_manager/commonality.py` — 헤드리스 코어:
  - Lot 계획 엑셀 **템플릿 생성/판독**(`디바이스명/공정번호/S/M/AOI호기`),
  - 호기 필터 + Lot 폴더 해석(디바이스명·공정번호·S/M 매칭, 실재 확인),
  - **이름순 첫 웨이퍼** 선택,
  - Lot별 값 추출(`ini_parser` 재사용) + **구조 diff**(Lot 간 설정키 비교),
  - 호기 결과 엑셀 write/read,
  - **호기 취합·비교**(과반수 대비 이탈 색칠, 공정번호/호기/파라미터 레이아웃).
- `tests/test_commonality.py` — 로컬 가짜 Scanresult 트리로 헤드리스 전 구간 테스트.

### 재사용 (수정 최소)
| 모듈 | 재사용 지점 |
|---|---|
| `downloader.py` | Scanresult 경로 파싱, 안전 read-only 복사, 대상(Zones/RTP/Optic) 수집 |
| `ini_parser.py` | Zones/OpticPreset/RTP → pivot, 변환/계수, OpticPreset 추림, 추천 파라미터 |
| `coef_detector.py` | RTP.txt(웨이퍼 폴더에 존재)로 변환계수 자동 추정 |
| `formbuilder.py` | 편집용 양식 생성/확정 + `_EXTRACT_MAP` |
| `collate.py` | 취합/색상·테두리 시트 패턴 |
| `refdata.py` | Step 1 호기/IP 목록 |
| `workdirs.py` | 저장폴더 하위 commonality 경로 규칙 추가 |
| `history.py` | Step 7 diff/이상치 로직 참고 |

### 저장폴더 경로(안)
```
{저장폴더}/commonality/{호기}/{생성시간}/
    staging/{공정번호}/{Zones|RTP.txt|OpticPreset.ini}   # Step3 복사본
    양식_{제목}_{시간}.xlsx                           # Step4 확정 양식
    조사_{호기}_{시간}.xlsx                           # Step5 호기별 값
{저장폴더}/commonality_취합/취합_{시간}.xlsx           # Step6 호기 취합·비교
```

## 4. GUI (equip_app.py)
- 새 탭 **"Commonality 조사"** 추가(기존 탭 옆).
- 액션: `IP 선택 → Lot 계획(엑셀) → 폴더 확인 → 복사 → 양식 만들기 → 값 조사`
  / 별도 `호기 취합·비교` / `뷰어 열기`.
- 오래 걸리는 복사·파싱은 `_run_busy` 로딩 모달 + 백그라운드 스레드(기존 패턴).
- 원본 보호·네트워크 규칙은 collector/downloader와 동일(읽기·복사만).

## 5. 확정된 결정 (사용자 승인 2026-07)
1. **IP↔Scanresult 루트**: **호기별 루트를 config(`commonality_roots`)에 저장** — 첫 사용
   시 폴더 브라우즈로 지정 후 자동 재사용. `commonality.scanresult_root(base, 호기)`는
   `Scanresult*` 변형(백업본 `Scanresult_260401` 등)·호기 0패딩(AOI-9==AOI-09)을 흡수.
   **백업본이 여러 개면 조사할 Scanresult 폴더를 사용자가 직접 지정**(자동 최신선택 없음;
   폴더를 직접 고르면 그대로 사용).
2. **폴더 매칭**: **디바이스명 + 공정번호 + S/M 모두**로 폴더 특정(정규화 비교, 정확
   일치 우선→포함). 이름순 첫 웨이퍼.
3. **Step 7 뷰어**: **tksheet 격자** — 과반수 이탈 셀 색칠 + "변경된 파라미터만 보기"
   필터 + 이탈 요약. (외부 시각화 라이브러리 금지.)
4. (참고 대기) **S/M 의미**(HPG/TVS): 현재 폴더 3번째 레벨로만 취급. 의미 확인되면
   라벨/필터에 반영.

## 6. 구현 현황
- [x] `commonality.py` 헤드리스 코어 + `tests/test_commonality.py`(6종 통과)
- [x] Step 4~5(양식·값 조사) — formbuilder/ini_parser/collate 연결
- [x] Step 6 취합·비교 엑셀(과반수 이탈 색칠)
- [x] `workdirs` commonality 경로(`commonality_*`)
- [x] GUI 탭 'Commonality 조사' + 단계 카드/다이얼로그(`_view_commonality`, `_cm_*`)
- [x] Step 7 뷰어(`_cm_open_viewer`, tksheet)
- 실기 확인(Windows/tksheet/Excel) 필요 — GUI 는 `py_compile` 정적검증만 가능.
