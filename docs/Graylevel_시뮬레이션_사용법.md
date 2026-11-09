# AOI Contrast AVG 단계별 비교 (Graylevel 시뮬레이션) — 사용법 · 설계

- 브랜치: `version_graylevel_simulation` (Para #50에서 `version_v12` 의 `3a132bb` 를 기준으로 만듦)
- 프로그램: 저장소 맨 위 `AOI_Contrast_Wizard.html` (단일 HTML, 설치 없음, Edge/Chrome 로컬 실행)
- 시험: `node tools/test_contrast_wizard.mjs` (합성 자료 `tools/contrast_wizard_fixture.py`, Playwright)
- 제한: **간단 버전 — Reference 이미지 없음, 좌표 모델 보정 필요 가능** (화면 맨 위에 늘 표시)

## 1. 사용 절차

1. `AOI_Contrast_Wizard.html` 을 Edge 로 여십시오.
2. Step 1 에서 [결과 폴더 추가]를 누르고, 압축을 푼 결과 폴더를 고르십시오.
   - 상위 폴더를 고르면 안에 있는 `Surface.flt` 폴더를 모두 등록합니다.
   - 브라우저가 "파일 업로드" 확인을 물으면 [업로드]를 누르십시오. 파일은 이 PC 브라우저 안에서만 읽습니다(서버로 보내지 않음).
3. 스캔마다 Contrast AVG · 검사 호기 · Step 이름을 입력하십시오. 폴더 이름에 `CA27` · `Contrast27` · `AVG27` 이 있으면 Contrast AVG 를 미리 채웁니다.
4. [점검]을 펼쳐 경고를 확인하십시오 (Record Size, 파일 누락, ScanLog 교차 검증, Die 계산 가능 여부).
5. Step 2 에서 허용오차(기본 2 µm)를 확인하고 [비교 실행]을 누르십시오. 등록한 리스트의 **모든 쌍**을 비교합니다(리스트 3개 = 3쌍). [쌍별 비교] 표의 [보기] 또는 Step 3 · 4 위의 쌍 단추로 볼 쌍을 고르십시오.
6. Step 3 Wafer Map: 점선 직사각형(좌측 하단 = 0,0) · wafer 원 · Die 격자 위에 Defect 를 그립니다. 점에 마우스를 올리면 상세 + Color + Gray Crop, 누르면 새 창(사진은 창 크기에 맞춤, 사진을 누르면 원래 크기 ↔ 창 맞춤).
7. Step 4 없어진 Defect 리뷰: 고른 쌍 A → B 에서 A 에만 있는 Defect(= B 에서 없어진 Defect). ↑↓ 또는 J/K 이동, Enter 새 창, O = 위치 맞음, X = 벗어남. 아래 Wafer map 에 이 쌍의 전체 Defect 를 그리고 **보고 있는 Defect 가 깜빡입니다**(점을 누르면 그 Defect 로 이동).
8. [CSV 내보내기]로 전체 결과를 저장하십시오.

## 2. 계산 규칙

| 항목 | 규칙 |
|---|---|
| Surface.flt | 152 byte 고정 레코드, little-endian, 이슈 본문 필드 표 그대로(`FLT_FIELDS`). `Surface.flt.md` 에 같은 이름 필드가 있으면 그 offset · 형식을 쓰고 경고. byteLength 가 152 로 나누어떨어지지 않으면 오류 |
| Area(µm²) | area(pixel) × PixelSize² (기본 0.7708). 예: 82 → 48.72 |
| 동일 Defect | Wafer x/y(또는 ActualX/Y 선택) 거리 ≤ 허용오차. 격자 최근접 검색 + 거리순 greedy 1:1 (중복 매칭 없음) |
| 구분(이름 표기) | 쌍 A → B 마다 `A에만` · `A · B 둘 다` · `B에만` — 리스트(Step) 이름으로 표기(유지 · 소거 · 신규 라는 말은 쓰지 않음, 소유자 지시). A 에만 = B 에서 없어진 Defect |
| 쌍 | 리스트를 Contrast AVG 오름차순(빈 값은 등록 순서로 뒤)으로 놓고 i<j 모든 쌍. 쌍별 표 = A · B Defect 수, 둘 다, A 에만, B 에만, 없어진 비율(A 에만 ÷ A) |
| Wafer map | 좌표 기준 = wafer map 을 꽉 채우는 가상의 직사각형의 좌측 하단 (0,0)(소유자 설명). 직사각형 = ProductInfo Die 격자(OffX + Cols×PitchX, OffY + Rows×PitchY)와 Defect 범위를 덮는 영역, wafer 원 = 직사각형에 내접. X 오른쪽 · Y 위쪽 |
| Die | `ix=floor((X−OffX)/PitchX)`, `DieCol=(Cols−2)−ix`, `DieRow=(Rows−2)−iy`, Die 내부 = 나머지. 값은 폴더마다 `ProductInfo.ini` 에서 읽음. 없으면 "계산 불가", Cols/Rows 밖이면 "범위 밖"(빨강) |
| Gray 위치 | **Para 'Color · Gray 매칭'(`param_manager/colorgray.py`)과 같은 모델**: `frameToChuckPlane(.<레시피>).ini` 의 `Scan_X/Scan_Y` 역행렬로 `p = M⁻¹·(결함 − 프레임 좌표 − offset)`, 3168×1024 안에 들고 가장자리에서 가장 먼 프레임. 레시피 번호(.t.<n>)가 맞는 프레임 먼저 |
| Gray 간단 모델 | `frameToChuckPlane` 이 없을 때만: `(결함 − 프레임 좌표) / PixelSize`. "보정 필요" 표시. 두 모델 모두 X/Y 반전 · X/Y Offset 을 Step 2 에서 조정 |
| 범위 밖 | 어떤 프레임에도 들지 않으면 임의 위치를 보이지 않고 "좌표 변환 보정 필요" |
| Crop | 결함 중심 Crop(기본 160 px), 가운데 빨간 박스 = BoxWidth × BoxHeight(pixel) |
| Color 연결 | ① ColorImageGrabingInfo.ini Fault 좌표 최근접(Color 연결 허용오차, 기본 5 µm) ② 인덱스 규칙(id · id±1 · resultID · resultID±1 · 기록 순서 0/1)을 **스캔마다 하나** 고름 — 좌표로 검증된 수가 가장 많은 규칙, 검증이 없으면 맞는 수가 가장 많은 규칙("좌표 없음 · 확인 전") |
| GL 측정 | Gray Crop 을 볼 때 ROI(Box) mean/median/max, 주변 ring(기본 6 px) median, ROI−ring delta. **Local Reference 추정치**이며 장비 Contrast 와 같다고 보지 않음 |
| 좌표 모델 확정 | 리뷰에서 "맞음" 10개 이상 + "벗어남" 0개일 때만 "확인됨". 그 전에는 "미확정" |

## 3. 성능 · 안전

- 네트워크 요청 없음(시험이 file/blob 밖 요청 0건을 확인). 원본은 `<input webkitdirectory>` 로 읽기만.
- Wafer Map = Canvas + requestAnimationFrame. 상세 표 = 쪽당 200행. 리뷰 목록 = 가상 스크롤.
- 이미지 캐시 LRU: Color object URL 80개(버리면 `revokeObjectURL`), Gray 프레임 ImageBitmap 16개(버리면 `close`). 현재 항목 앞뒤 8개 Color, 4개 Gray 를 미리 읽음.

## 4. 확인 전(소유자 확인 필요)

- Surface.flt 의 x/y 가 ColorImageGrabingInfo 의 FaultX/FaultY 와 같은 좌표계라고 가정했다(Color · Gray 매칭과 같은 변환을 쓰려면 필요). 다르면 Step 2 의 [결함 좌표] ActualX/ActualY 를 고르거나 Offset 으로 보정.
- `s_FrameData.dat` 는 크기만 표시하고 좌표 계산에는 쓰지 않는다(이슈에서 Gray color 매칭 쪽이 더 정확하다고 함).
- ProductInfo.ini 키 이름: `CustomerDiePitch_X/Y`, `Cols`, `Rows`, Offset 은 `CustomerDieOffsetX/Y` · `OffsetX/Y` · `DieOffsetX/Y` · `MapShiftX/Y` 중 하나를 받음. 실제 이름이 다르면 알려 주십시오.
- ScanLog/ProductionInfo 의 Surface defect 수는 파일 이름이 `ScanLog*` · `ProductionInfo*` 이고 글에 "Surface … 숫자"가 있을 때만 비교한다.
- Wafer Map 은 X 오른쪽 · Y 위쪽으로 그리고, Defect 좌표의 (0,0) 을 직사각형 좌측 하단으로 본다(소유자 설명). wafer 원은 직사각형에 내접한다고 보았다(확인 전).
