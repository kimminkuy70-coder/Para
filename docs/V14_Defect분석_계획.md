# V14 계획 — 'Defect 분석' 탭: Contrast Wizard rev6(HTML) 이식 + 최종 목록 CSV 연동 (구현 전 계획)

- 작성 2026-11-15 · 기준: `version_v14` = `version_v13`(8c1306c, v13.0.2) 복사 · rev6 HTML = `ccr-7401b37d-bwze1e` 의 `AOI_Contrast_Wizard_rev6.html`(ac1195e 시점).
- 상태: **계획(코드 변경 없음)**. 구현은 다음 세션(소유자: "Opus 5.5 가 최종적으로 코드 수정")이 이 문서를 보고 한다.
- 소유자 지시(2026-11-15 세션 대화 · 질문 답):
  1) "Para v13 브랜치에 HTML rev6 기능을 동일하게" + "프로그램이 폴더를 직접 읽어 초기 읽기 과정을 대폭 단축"(HTML 의 '업로드' 1시간 제거).
  2) 탭 이름은 **'Defect 분석'** 으로 바꾸고, 기존 Color·Gray 매칭 기능은 그 탭 **안에** 넣는다.
  3) 하위 탭 2개 = **[기존 Color·Gray 매칭]** + **[대규모 Defect 분석]**(HTML Step 5). **Step 1~4(다이어그램 분석)도 옵션 체크로 선택해 쓸 수 있게** → "HTML 모든 기능 사용 가능하게 검토".
  4) HTML rev6 가 저장하는 **'원하는 Defect 이미지' 목록 CSV = 5-3 최종 목록(☑)** 을 기존 Color·Gray 매칭이 **인식해 연동**(그 Defect 만 추출).
  5) HTML 한계(폴더 전부 읽어 오래 걸림 · 상위 경로 일일이 지정) 분석 + 프로그램 이식으로 해소되는지 분석.
  6) 브랜치: "version_v14 새로 만들어 version_v13 을 복사" → **`version_v14` 생성 완료**(이 커밋). 소유자 표기 'vserion_v14' 는 오타로 보고 `version_vN` 규칙을 따랐다(routine 이 가장 큰 `version_vN` 을 작업 브랜치로 쓰고, v13 업데이트 확인도 `v13.*.*` 태그 규칙이라서). 다르면 지시.

## 1. 지금 상태 (확인한 사실)

- **version_v13**: V13 전환 완료 — 전용 exe 없음, `Camtek_AOI_manager.pyw` + `param_manager/engine.py`·`webserver.py`(127.0.0.1 + 토큰) + Edge 앱 창, `vendor/`(openpyxl), `frontend/dist` 커밋, 릴리스 v13.0.0~0.2(태그 → `v13.yml`).
- **기존 Color·Gray 매칭**(v12.9.30 수준 그대로 v13 에 있음): 화면 `frontend/src/ColorGray.tsx`, 엔진 `param_manager/desktop_colorgray.py` + `colorgray.py`.
  흐름 = `cgm_scan`(Wafer 폴더 찾기) → `cgm_start`(전부 매칭 · 계획) → `cgm_read`(원본 JPEG 조각 base64) → 화면이 캔버스로 crop·썸네일 → `cgm_put` → `cgm_finish`(비교 엑셀 + unmatched CSV).
  분담 원칙 = **엔진이 파일(읽기 전용 원본 · 로컬 전용 출력), 화면이 픽셀**. 출력 검사 `_check_output`(OneDrive·네트워크·원본 겹침 거부)은 그대로 쓴다.
- **rev6 HTML**(`ccr-7401b37d-bwze1e`): Step 1~4(두 Step Lot Graylevel 시뮬레이션 · 다이어그램) + Step 5(대규모 Defect 조회 · Color·Gray 매칭 · 사진 새 창 · GL 원 · 최종 목록 엑셀). 시험 `tools/test_contrast_wizard_rev6.mjs`(rev5 시험 포함). HTML 은 프로그램 없는 PC 용으로 **그대로 유지**한다.
- **HTML 1시간 대기의 원인**(2026-11-15 세션에서 확인): Windows 의 Chromium(Edge·Chrome)이 폴더 핸들로 `.ini` 를 거부(`download_file_types.asciipb` 에서 ini = Windows DANGEROUS)해 5단계도 파일 목록(webkitdirectory) 방식 → 브라우저가 고른 폴더의 **모든 파일(사진 포함)** 을 목록으로 처리한 뒤에야 페이지가 받는다(페이지 밖, 중지 불가). 실제 Slot = 사진 아닌 파일 71 + Color 353 + Gray 437 ≈ 860개 중 5단계가 읽는 것은 **10개(1.2%)**. 50만 파일 ≈ Slot 580개 ≈ 1시간(소유자 실측).

## 2. 탭 구조 (소유자 확정 + 해석)

- `main.tsx` 의 탭 이름 `'Color·Gray 매칭'` → **`'Defect 분석'`**(KEEP · VENDORS.CAMTEK · TAB_DESC · Tour 문구 · 저장된 사용자 탭 이름 이행 포함. 문서 · 스크린샷 문구도).
- `Defect 분석` 탭 안 하위 탭:
  1) **[대규모 Defect 분석]**(기본) = HTML Step 5 이식(새 화면 `DefectBig.tsx` + 새 엔진 `defect_scan.py`/`desktop_defect.py`).
  2) **[Color·Gray 매칭]** = 기존 `ColorGray.tsx` 그대로 + 6절의 '최종 목록 CSV 불러오기' 추가.
  3) **[다이어그램 분석]**(Step 1~4) = 옵션. 해석(확인 전): 탭 머리에 작은 체크 **'다이어그램 분석(Step 1~4) 보이기'**(기본 꺼짐, localStorage 기억) → 켜면 하위 탭 3번째가 나타남. 설정 화면에 숨기지 않는다(찾기 쉽게). 다르면 지시.

## 3. rev6 기능 인벤토리 → 이식 맵핑

구현 세션은 rev6 HTML 의 해당 구역 코드와 `ccr` 브랜치 CLAUDE.md의 rev5/rev6 절, `docs/AI_HANDOFF.md` 후속 1~23, `docs/Graylevel_시뮬레이션_사용법.md` 15번을 원전으로 삼는다. 수식 검증 기준은 언제나 `param_manager/colorgray.py`.

| rev6 기능(구역) | 프로그램에서 | 비고 |
|---|---|---|
| 5-1 폴더 훑기(walkFast) · Surface.flt 열 배열 · 필터(Contrast/Area/W/L/Slot/Lot 제외/Recipe/분류 2열 AND) · 정렬 · 목록 CSV | 엔진 훑기+읽기(4절) → 화면이 열 배열로 즉시 필터·정렬(rev6 로직 이관) | **1시간 대기 제거의 핵심**. CSV 는 엔진이 절대 경로로 저장 |
| 매칭 파일 찾기 규칙(후속 8: 이름→목록 대소문자 무시→하위 4단계→단독 위쪽 폴더) + 못 찾으면 진단 | 엔진 `defect_scan.py` (colorgray.file_names 재사용) | #48 의 long_path · 대소문자 규칙과 같은 계열 |
| 5-2 매칭 계산(cgPlan: choose_frame · COORD_MODES · 레시피 변환 파일) | **colorgray.py 함수 그대로 호출**(이식 아님) | HTML 은 포팅이었지만 엔진은 원본 — 수식 불일치 위험 소멸 |
| 5-2 대체 계산(ScanResultImageList 없음 → Gray 사진 이름+Wafer2Table → s_FrameData / 변환 .1·.2 → 큰 번호 / 변환 없음 → 가운데 모델 / Color 만 Slot) | `defect_scan.py` 에 파이썬으로 추가(colorgray.py 는 안 건드림) | 기대값은 rev5 시험이 실자료로 확정(353/353, 픽셀 차 ≤2.6 · 0 · 0.13 · 2.5) |
| 5-2 결과 목록 · 사진 파일 존재 확인 · Slot 표 · 결과 CSV | 엔진이 존재 확인(이름 목록) · CSV 저장, 화면이 표 | |
| 사진 새 창(방향키 · Space · 파일명+전체 경로 · 확대 2~16배 · 위치 고정 · 빨간 네모) | `DefectBig.tsx` + `window.open` | Edge 앱 창의 팝업 동작은 Windows 확인 전 — 10절 위험 |
| 5-3 하나씩/격자 · 상태 필터(짝 완료/Color 만/흑백만/둘 다 없음) · 리뷰PC 정보 · Recipe 열(#70~#73) · GL 원 측정(glProfile, 반지름 바 즉시 정렬) | 화면 캔버스 로직 이관(픽셀 작업은 화면 — 기존 분담 그대로), 사진은 엔진에서 | GL 누적(glp) · 빨간 네모(cgDefBox) 코드 재사용 |
| 5-3 최종 선택(Space · ☑) · 최종 목록 엑셀(사진 포함) | ☑ 상태는 화면, 엑셀은 **엔진 openpyxl**(`colorgray.build_workbook` 의 JpegImage 재사용, 열=XL_COLS) — 화면이 그린 사진 JPEG 을 `cgm_put` 방식으로 올림 | HTML 의 자체 xlsx(zip) 코드는 안 가져옴 |
| 분류(ManReClassify 2열 · AND 필터) · Recipe 이름(WaferInfo) · Zones · EquipmentClassifications | 엔진이 `manreclassify.py`·기존 파서로 읽어 화면에 | Slot 당 추가 파일 10개 안(1절 분류표) |
| 진행창(단계 · 개수 · 지금 파일 · 중지) · 일시 오류 재시도(retryRead) | `desktop_progress` + 엔진 재시도 | HTML 의 숨은 탭 스로틀 문제는 엔진이라 없음 |
| Step 1~4(등록 planUnits · md 찾기 · ScanLog 대조 · wafer map + 샘플 맵 보정(#69) · 쌍 선택 · Step 3/4 비교 · 벤다이어그램 · GL · 사진) | [다이어그램 분석] 하위 탭(옵션). 읽기는 같은 엔진 훑기 재사용(Slot 등록 = 5-1 과 같은 자료 + Step1 전용 파일 몇 개) | 2차(9절 6단계). HTML Step1 은 Slot 안 전 파일을 받지만, 프로그램은 필요한 파일만 읽게 바꾼다(요구 파일 목록은 rev6 조사: ScanLog·s_DieLocation(.md)·wafer map 후보 글 파일) |

## 4. 엔진 설계 (핵심: 직접 읽기)

새 파일 `param_manager/defect_scan.py`(순수 로직, tkinter·웹 무관) + `param_manager/desktop_defect.py`(웹 어댑터). `colorgray.py`·`manreclassify.py` 는 **수정 없이 재사용**(colorgray 에 없는 대체 계산만 defect_scan 에 추가).

1) **훑기** `scan(root, callback, cancel)`: `os.scandir` 폴더 단위(colorgray.file_names·child_dirs·long_path 재사용). Slot = `Surface.flt` 가 있는 폴더(대소문자 무시), 깊이 7, `SKIP`(colorgray.SKIP + `AOI_Color_Gray_Matching_Result` 등 결과 폴더). CI(ColorImageGrabingInfo.ini) 찾기 = 후속 8 규칙 + 못 찾으면 진단 문구(파일 수 · 비슷한 이름 · 경로 길이). 진행 콜백(폴더 수 · Slot 수 · 지금 경로) · 중지. 폴더 나열은 이름만 — 사진 '내용'은 안 읽음. 상위 경로는 **사람이 폴더 고르기 창에서 한 번**(엔진이 절대 경로를 아므로 HTML 의 [원본 폴더 경로] 입력칸은 아예 없음).
2) **Slot 읽기**(스레드 4~8 동시): Slot 당 Surface.flt(+.md) · ProductInfo · CI · ScanResultImageList · frameToChuckPlane(번호 포함) · WaferInfo.ini · Zones.ini · EquipmentClassifications · ManReClassify ≈ 10개(+없을 때만 Wafer2Table · s_FrameData(.md) · Params_WaferInfo · ProductionInfo). 일시 오류 1~2회 재시도.
3) **Surface.flt 파서**(신규): 기본 레코드 152 byte, `.md` 가 있으면 그 레이아웃(HTML `fltLayout`/`parseFltCols` 와 같은 규칙 — 열 정의 · offset 은 rev6 HTML `COLS` 구역이 명세). 필요한 열만 `struct.iter_unpack` → `array('d')`/`array('h')` 열 배열. 30만 Defect ≈ 15열 ≈ 36 MB, 표준 라이브러리만(numpy 금지 — vendor 정책).
4) **매칭**: colorgray `parse_colors`·`parse_frames`·`parse_transform`·`transform_files`·`choose_frame`·COORD_MODES 그대로 + 대체 계산(3절) → Slot 마다 {Color↔Gray 프레임, px·py, 좌표 기준, src(무엇으로 계산), 진단}.
5) **화면 전달**: 열 배열은 **바이너리 HTTP 응답**(little-endian, 열 이름·형 머리 + 본문; 127.0.0.1 로컬이라 36 MB ≈ 1초 안팎) → 화면 TypedArray 로 rev6 와 동일한 즉시 필터·정렬. 기존 통신(`/api/send` JSON + SSE, IPC 4 MB 프레임)으로는 30만 개가 느려서 `webserver.py` 에 GET 응답을 추가한다(`X-Para-Token` 검사 동일). 사진도 같은 방식의 GET(스캔된 Slot 의, 목록에 이름이 있는 파일만 — 경로 주입 차단은 기존 `cgm_read` 와 같은 원칙) → `<img src>`·createImageBitmap 에 바로 쓰고 브라우저 캐시를 얻는다.
6) **저장**: 목록 CSV · 결과 CSV · 최종 목록 CSV(6절 형식) · 최종 목록 엑셀 — 전부 엔진이 **로컬 전용**(`_check_output`) 경로에, **절대 경로 열 포함**. 원본 폴더에는 어떤 쓰기도 없음(소유자: "원본 훼손 절대 안 됨" — 코드 검토 결과 지금도 쓰기 없음, 유지).

## 5. 화면 설계 (React)

- `DefectAnalysis.tsx` = 하위 탭 컨테이너(2절). `DefectBig.tsx` = 5-1/5-2/5-3 + 사진 새 창(rev6 의 makeVT 가상 스크롤 표 · 필터 패널 · cgCropCanvas/cgFrameCanvas/cgDefBox/glProfile 캔버스 · 키 입력을 TS 모듈로 이관 — 로직은 그대로, 파일 접근만 엔진 HTTP 로 교체). `DefectDiagram.tsx` = Step 1~4(옵션, 2차).
- rev6 의 '설정 없음' 원칙 유지(PIX 0.7708 · CTOL 5 고정). 진행창 = 기존 desktop_progress 표시 방식.
- 시험: `tools/test_desktop_ui.mjs` 확장(엔진 가짜 응답 또는 실제 엔진 + fixture 폴더) + rev6 시험의 실자료 기대값을 파이썬 단위 시험으로 이관.

## 6. 최종 목록 CSV 연동 (소유자 확정: 5-3 최종 목록)

- **형식(공용, 'Para 최종 목록 CSV v1')**: UTF-8 BOM, 머리 열 이름으로 식별. 열 = `순서,Lot,Lot경로,Slot,ID,resultID,첫번째분류,재분류,Contrast,매칭폴더,Color이미지,Gray프레임,FaultX,FaultY,GrayPX,GrayPY`(= rev6 pairCsv 부분집합; `매칭폴더`+`Color이미지` 가 1차 키). 프로그램 저장본은 `매칭폴더` 가 절대 경로, HTML 저장본은 고른 폴더 기준 상대(+[원본 폴더 경로] 적었으면 절대).
- **A. HTML rev6 에 [최종 목록 CSV 저장] 추가**(`ccr-7401b37d-bwze1e` 별도 작업): 5-3 의 ☑ 목록을 위 형식으로 저장(엑셀 저장 옆 버튼).
- **B. 프로그램 [대규모 Defect 분석]** 도 같은 형식으로 저장(최종 목록 엑셀과 나란히).
- **C. 기존 [Color·Gray 매칭] 하위 탭에 [최종 목록 CSV 불러오기]**: CSV 를 읽어(화면에서 열 확인 표시) → `cgm_start(wafers, output, filter=...)` 에 전달 → **CSV 에 있는 Defect 만** crop·엑셀 추출. 키 매칭 ① `매칭폴더` 끝부분이 스캔된 Wafer 폴더 경로와 일치(절대·상대 모두 허용, 대소문자 무시) ② `Color이미지` 파일명 일치 ③ 보조로 resultID/Index. 못 찾은 줄은 unmatched CSV 에 '최종 목록에 있었으나 못 찾음'으로. `desktop_colorgray.py` 는 start 의 레코드 거르기만 추가(흐름 유지).

## 7. HTML 한계 분석 → 프로그램에서 해소되는 것 (소유자 질문)

| HTML 한계 | 원인 | 프로그램(V14) | 남는 것 |
|---|---|---|---|
| 폴더 고르기 뒤 대기 1시간(50만 파일) | 브라우저가 모든 파일을 '업로드' 목록으로 처리(Chromium 이 .ini 를 폴더 핸들에서 거부해 빠른 길 불가) | **없어짐**: 엔진이 폴더 단위 나열 + Slot 당 ~10개만 읽음. 8절 어림 1~3분 | 네트워크 왕복 자체(폴더 수 · SMB 속도)는 물리 한계 |
| 상위 경로 일일이 지정([원본 폴더 경로] 입력) | 브라우저가 절대 경로를 숨김 | **없어짐**: 폴더 고르기 창 한 번 → 절대 경로를 엔진이 앎(CSV·엑셀·화면 전부 자동) + 최근 폴더 기억 가능 | — |
| 매번 처음부터 다시 읽음 | 브라우저 보안(핸들 저장 불가 수준) | 가능해짐: Slot 목록·열 배열 로컬 캐시(선택, 2차 — 구현은 소유자 요청 시) | |
| 다른 창을 보면 느려짐/멈춤(숨은 탭 스로틀) | 브라우저 타이머 지연 | 없어짐(엔진 프로세스) | |
| 16 MB·메모리·팝업·저장 창 제약 | 브라우저 | 대부분 없어짐. 사진 새 창(window.open)만 Edge 앱 창에서 확인 필요(10절) | |
| 사진 읽기·디코딩 시간(5-3 · GL) | 공통 | 같음(네트워크에서 사진을 읽는 것 자체는 동일) — 다만 캐시·동시 읽기로 완화 | 사진 한 장 ~1.4 MB 읽기 시간 |

## 8. 속도 어림 (측정 전 — 회사 PC 실측으로 확정)

- 지금(HTML): 50만 파일 전부 처리 ≈ 1시간(실측) ≈ 파일당 ~7 ms.
- V14 엔진: 폴더 나열(Slot 580개면 폴더 수천 개 × scandir 1번) + 파일 읽기 10개×580 ≈ 6천 개 ≈ **1~3분** 어림(파일당 비용이 같다는 가정, 나열은 폴더당 1왕복이라 더 쌈). 소유자에게 안내한 PowerShell 측정(①전체 나열 ②Surface.flt 폴더마다 10개 읽기)의 ②가 이 어림의 실측치가 된다 — 받은 값이 있으면 이 절을 갱신할 것.

## 9. 구현 단계 (Opus 5.5 체크리스트 — 단계마다 시험·push)

0. (이 세션, 완료) `version_v14` 생성 + 이 계획.
1. 엔진 `defect_scan.py`: 훑기 + flt 파서 + 매칭(원본 colorgray 호출) + 대체 계산 + 단위 시험 `tests/test_defect_scan.py`(fixture = `tests/colorgray_fixture.py` 확장 + rev5/rev6 시험의 실자료 기대값 이관 — `ccr` 의 `사진 제외.zip` 을 v14 `tests/data/` 로 가져와 353/353 · 대체 계산 픽셀 차 확인).
2. `desktop_defect.py` + webserver 바이너리 응답·사진 GET + `DefectBig.tsx` 5-1(수집·필터·분류·Recipe·CSV). 새 엔진 모듈은 **`deploy.py` 배포 목록에 추가**(`tests/test_deploy_files.py`)하고 엔진 모듈 금지 문구 규칙(`test_sidecar_no_scripts` 계열)을 지킨다.
3. 5-2(짝 목록 · 사진 존재 확인 · 결과 CSV · Slot 표) + 사진 새 창.
4. 5-3(하나씩/격자 · GL 원 · 상태 필터 · 최종 선택 · 최종 목록 엑셀·CSV).
5. 탭 개편(2절) + 기존 Color·Gray 매칭의 [최종 목록 CSV 불러오기](6절 C).
6. [다이어그램 분석](Step 1~4) 옵션 이식.
7. HTML rev6 에 [최종 목록 CSV 저장] 추가(`ccr` 브랜치 — 6절 A. 5단계보다 먼저 해도 됨).
- 각 단계: `PYTHONPATH=vendor` 파이썬 시험 전부 + `tools/check_project.py` + `npm run build`(dist 커밋 규칙) + `tools/test_desktop_ui.mjs`. 릴리스는 소유자 지시 시(버전 번호는 11절 1).

## 10. 위험 · 확인 필요 (솔직히)

- **사진 새 창**: Edge 앱 창(`--app`)에서 `window.open` 팝업의 모양·차단 여부를 이 환경에서 확인 못 함. 대안을 같이 구현: 팝업이 안 되면 같은 창 전체 화면 보기로 자동 전환(기능 동일 — 방향키·Space·확대·고정).
- 30만 Defect 바이너리 전송·메모리는 로컬 기준 어림(36 MB)일 뿐 — 구현 때 실제 측정(목표: 전송+표 1초대).
- 네트워크 드라이브 속도(8절)는 회사 PC 에서만 실측 가능.
- Step 1~4 이식은 분량이 커서 2차(6단계) — 그 전까지는 HTML 로 쓰면 된다(HTML 유지).
- `frontend/dist` 커밋 정책: 새 화면으로 번들이 커짐(수백 KB 예상, 허용 범위 — 빌드 재현 CI 그대로).
- numpy·Pillow 금지(vendor 정책): flt 파서·엑셀 모두 표준 라이브러리 + openpyxl 로 설계했음(4절 3·3절 엑셀 행).

## 11. 소유자에게 확인할 것 (답 오기 전에는 '해석'대로 진행)

1. 릴리스 버전: v14 기능이 처음 나가는 태그를 `v14.0.0` 으로? (v13 업데이트 확인이 `v13.*.*` 태그 규칙이면 v13 사용자에게 v14 알림이 가는지 — 업데이트 규칙의 태그 패턴을 `v1*.*.*` 로 넓히는 수정 포함 여부) — **구현 전 답 필요**.
2. '다이어그램 분석' 체크 위치 = 탭 머리 체크(2절 해석)로 좋은지.
3. 사진 새 창이 Edge 앱 창에서 막히면 '같은 창 전체 화면'으로 대체(10절) — 좋은지.
4. 기존 Color·Gray 매칭이 CSV 로 거른 뒤의 결과물 = 지금과 같은 비교 엑셀(crop·썸네일) 그대로면 되는지, 아니면 최종 목록 엑셀(사진 3장 포함) 형식도 필요한지.
