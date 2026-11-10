# AOI Contrast AVG 단계별 비교 (Graylevel 시뮬레이션) — 사용법 · 설계

- 브랜치: `version_graylevel_simulation` (Para #50에서 `version_v12` 의 `3a132bb` 를 기준으로 만듦)
- 프로그램: 저장소 맨 위 `AOI_Contrast_Wizard.html` (단일 HTML, 설치 없음, Edge/Chrome 로컬 실행)
- 시험: `node tools/test_contrast_wizard.mjs` (합성 자료 `tools/contrast_wizard_fixture.py`, Playwright)
- 제한: **간단 버전 — Reference 이미지 없음, 좌표 모델 보정 필요 가능** (화면 맨 위에 늘 표시)

## 1. 사용 절차

1. `AOI_Contrast_Wizard.html` 을 Edge 로 여십시오.
2. Step 1 에서 [Lot 폴더 추가]를 누르고, Lot 폴더(또는 그 상위 폴더)를 고르십시오(#57).
   - 인식 기준: `Surface.flt` 가 있는 폴더 = **Wafer Slot 폴더**, 그 바로 위 폴더 = **Lot 폴더**. 한 Lot 폴더 안의 Slot 폴더 1~25개를 그 Lot 으로 묶습니다. **Lot 1개 = 스캔 결과 1개**(Step 1 표 한 줄).
   - 상위 폴더(예: `CA20/` 아래 Lot 여러 개)를 고르면 안의 Lot 을 모두 등록합니다. Slot 폴더를 바로 고르면 그 폴더 = Slot 1개짜리 Lot.
   - Contrast AVG · Step 이름은 Lot 폴더 이름 → 그 위 폴더들 → Slot 폴더 이름 순으로 `CA27` 같은 이름을 찾아 채웁니다. 같은 Lot 을 다시 추가하면 Slot 만 더합니다.
   - 등록하는 동안 **로딩창**이 뜹니다(#59): `Slot 폴더 k / N` 큰 글자 + 진행 막대 + `파일 x / M개 (%)` + 지금 읽는 폴더. 폴더를 고른 뒤 브라우저가 파일 목록을 만드는 동안은 개수를 알 수 없어 '폴더 고르는 중'만 보입니다(고르기를 취소했으면 [닫기]). 등록이 끝나면 저절로 닫힙니다.
   - 오류 Slot(Record Size 등)은 [점검]에 Slot 이름과 함께 나오고 비교에서 뺍니다.
   - 브라우저가 "파일 업로드" 확인을 물으면 [업로드]를 누르십시오. 파일은 이 PC 브라우저 안에서만 읽습니다(서버로 보내지 않음).
3. Lot 마다 Contrast AVG · 검사 호기 · Step 이름을 입력하십시오. 폴더 이름에 `CA27` · `Contrast27` · `AVG27` 이 있으면 Contrast AVG 를 미리 채웁니다.
4. [점검]을 펼쳐 경고를 확인하십시오 (Record Size, 파일 누락, ScanLog 교차 검증, Die 계산 가능 여부).
5. Step 2 에서 **[보기 단위]**를 고르십시오(#57). `Lot 별 (모든 Slot 합침)` = Lot 의 모든 Slot Defect 를 한 wafer map 에 겹쳐 보고 집계합니다(같은 Defect 판정은 **같은 Slot 끼리만** — 다른 Wafer 의 같은 좌표는 다른 Defect). `Slot 별 · W05 (2/2 Lot)` = 그 Slot 1장만(그 Slot 이 없는 Lot 은 빠짐). Step 3 맨 위에도 같은 고르기가 있고, 바꾸면 바로 다시 비교합니다. Slot 짝은 Slot 폴더 이름(대소문자 무시)으로 맞춥니다. 양쪽 Lot 이 Slot 1개씩이면 이름이 달라도 짝짓습니다.
   이어서 허용오차(기본 2 µm)를 확인하고 [비교 실행]을 누르십시오. 등록한 리스트의 **모든 순서쌍**을 비교합니다(리스트 3개 = 3×2 = 6쌍, `CA20 → CA27` 과 `CA27 → CA20` 을 따로, #56). [쌍별 비교] 표의 [보기] 또는 Step 3 · 4 위의 쌍 단추로 볼 쌍을 고르십시오.
6. Step 3 Wafer Map 분석(#55): **스캔 결과 하나 = 집합 하나**. 맨 위 [시뮬레이션 집합]에서 1개 ~ 스캔 수만큼 체크하고 [결과 →]를 누르십시오. 그 뒤에는 체크를 바꾸면 바로 바뀝니다.
   - 벤다이어그램은 늘 **모든 스캔**으로 그립니다(4개까지 원 · 타원, 5개 이상은 아래 영역 표만). 고른 집합과 관련된 영역(그 집합이 하나라도 들어 있는 영역)만 영역마다 다른 색, 나머지는 옅은 회색 + 경계선만. 영역 안 숫자 = Defect 수.
   - 영역(또는 영역 표의 줄)을 누르면 그 영역이 **더해집니다**. 이미 고른 영역을 다시 누르면 **빠집니다**(Ctrl 필요 없음, #56). 빈 곳 = 고른 집합 전체.
   - 오른쪽 Wafer map: 영역 색으로 Defect 를 그립니다. [다른 영역 Defect 도 표시] 체크 = 다른 영역 Defect 도 작게(관계없는 영역은 회색). 보고 있는 Defect 가 깜빡입니다. 점을 누르면 그 Defect(다른 영역이면 그 영역으로 바꾸고 이동).
   - [⧉ 새 창으로 크게 보기] = 다른 모니터에 띄우는 창. 왼쪽 **벤다이어그램** + 오른쪽 **wafer map**(#56). 이 화면과 **실시간 연동**(깜빡임 · 목록 이동 · 영역 바꾸기가 바로 반영). 그 창에서 벤다이어그램 영역 클릭(더하기/빼기) · 점 클릭 · ↑↓ 도 이 화면에 반영됩니다.
   - 아래 = 그 영역 Defect 목록(왼쪽) + Color · Gray Crop 사진 · 정보(오른쪽). 여러 스캔에 있는 Defect 는 [사진 · 정보 스캔] 단추로 어느 스캔의 사진을 볼지 고릅니다. ↑↓ 또는 J/K 이동, **더블 클릭 또는 Enter = 새 창(큰 화면)**.
   - 종전 쌍별 KPI · 상세 표 · [CSV 내보내기]는 맨 아래 접힌 상자 [쌍별 상세 표 · CSV]에 있습니다.
7. Step 4 Escape Defect 리뷰(#55 에서 Step 3 과 같은 구성, #56 에서 이름 바꿈): 고른 쌍 A → B 에서 A 에만 있는 Defect(= B 로 가면서 Escape 된 Defect). 왼쪽 위 **간략 wafer map 2개**(A = A 의 Defect 회색 + 없어진 것 빨강 점, B = B 의 Defect 회색 + 없어진 자리 빨간 원 — 이해를 돕는 그림), 오른쪽 위 자세한 Wafer map(깜빡임 같음, 새 창 = 왼쪽 간략 지도 2개 + 오른쪽 wafer map), 아래 목록 + 사진. O = 위치 맞음, X = 벗어남. Step 3 에서 두 집합만 고르고 'A - B' 영역을 봐도 같은 Defect 지만, 스캔이 3개 이상이면 A - B 가 영역 여러 개로 나뉘고 O/X 위치 확인 기록은 Step 4 에만 있어 Step 4 를 남겼습니다(내 판단, 확인 전).
8. [CSV 내보내기]로 전체 결과를 저장하십시오.
9. **목록 필터 · 정렬**(Step 3 · 4 목록 위, 2026-11-10): `Contrast(실제)` · `Area(µm²)` · `Width` · `Length` 의 최소 ~ 최대(빈 칸 = 제한 없음)와 정렬(기본 순서 · 각 값 큰 순/작은 순). 필터에 맞는 Defect 만 목록 · 사진에 나오고, 맞지 않는 것은 wafer map 에 회색 원으로 남습니다. 비교는 화면에 보이는 자릿수(Contrast · Area 소수 2자리, Width · Length 1자리)로 하므로 보이는 값을 그대로 넣으면 됩니다. [필터 지우기] = 범위만 비움.
10. **Step 5 대용량 Defect 조회**(2026-11-10): 큰 Lot 여러 개를 한꺼번에 불러와 필터 · 정렬한 뒤 필요한 Defect 의 사진만 봅니다. 비교(Step 2 ~ 4)와는 따로 움직입니다.
    - [Lot 폴더 추가 (정보만 빠르게)] → Lot 폴더나 그 상위 폴더를 고릅니다(여러 번 가능). 등록 때는 Slot 폴더마다 `Surface.flt`(+ `.md`) · `ProductInfo.ini` **만** 읽습니다. 사진과 사진 목록(`ColorImageGrabingInfo.ini` · `ScanResultImageList.txt` · `frameToChuckPlane.ini`)은 그 Slot 의 Defect 사진을 처음 볼 때 읽습니다.
    - Edge/Chrome 에서는 폴더를 읽기 전용으로 여는 창이 뜹니다(사진 파일 목록을 만들지 않아 빠름). 지원하지 않는 브라우저는 Step 1 과 같은 폴더 고르기로 바뀝니다(파일 목록을 만드는 시간은 걸리지만 사진 내용은 읽지 않음).
    - `Step 1 에 등록한 Lot 도 목록에 포함`(기본 켬)이면 Step 1 의 Lot 도 같은 목록에 나옵니다.
    - 필터 = Lot · Slot · Contrast(실제) · Area · Width · Length, 정렬 = 정렬 고르기 또는 **열 제목 클릭**(다시 누르면 반대 순서). 기본 = Contrast(실제) 큰 순.
    - `고르면 바로 사진 보기`(기본 켬): 줄을 고르면 오른쪽에 Color · Gray Crop · 정보가 바로 나오고, 더블 클릭 · Enter = 새 창(큰 화면). 끄면 고를 때는 정보만 나오고 더블 클릭 · Enter · [사진 불러오기]로 그 Defect 사진만 읽습니다.
    - [CSV 내보내기] = 지금 목록 전부(필터 · 정렬 그대로, 사진 · Gray 측정 값은 없음). Die = 장비 Col/Row(`floor(X/PitchX)`, `floor(Y/PitchY)`) — 이 화면은 wafer map 맥락이 없어 '맨 왼쪽 아래 = (0,0)' 로 다시 세지 않습니다.
11-0. **rev1 판 Step 1 [Lot 폴더 추가]**(`AOI_Contrast_Wizard_rev1.html`, 2026-11-10 소유자 "폴더 고르는 중에서 오래 걸려"): Edge · Chrome 의 빠른 폴더 열기 창으로 폴더를 고릅니다. 폴더마다 `Surface.flt` 가 있는지만 바로 확인하고, Slot 폴더 안(사진 수천 장)은 그 Slot 을 등록할 때 이름만 나열합니다. 사진은 볼 때 읽습니다. 예전 방식(브라우저가 사진까지 모든 파일 목록을 만든 뒤 넘겨줌)은 '폴더 고르는 중'에서 오래 걸렸습니다.
    - 빠른 폴더 열기를 쓸 수 없으면(지원하지 않는 브라우저 · 회사 정책으로 막힘) 이유를 알리고, 느린 방식으로 계속할지 묻습니다. Step 5 [Lot 폴더 추가]도 같습니다.
11. **rev1 판 Step 5**(`AOI_Contrast_Wizard_rev1.html`, Para #61 후속 소유자 지시 2026-11-10): 원래 파일(`AOI_Contrast_Wizard.html`)은 그대로 두고 Step 5 만 3단계로 바꾼 새 파일입니다.
    - **1단계 · 폴더 불러오기**: Slot 마다 `Surface.flt`(+ `.md`)만 읽습니다(Contrast 리스트). ProductInfo, 사진 목록, 사진은 읽지 않습니다.
      폴더를 훑을 때도 폴더마다 `Surface.flt` 가 있는지 이름으로 바로 확인합니다. 있으면 그 Slot 폴더 안(사진 수천 장)은 열어 보지 않습니다. 그래서 Lot 표의 이미지 수는 '안 셈'으로 나옵니다. Slot 폴더 안은 3단계에서 결정한 Slot 만 엽니다. (Edge · Chrome 의 읽기 전용 폴더 창에서만 빨라집니다. 예전 폴더 고르기 창은 브라우저가 모든 파일 목록을 만들어 빨라지지 않습니다.)
    - **2단계 · 리스트 결정**: Contrast(실제) 큰 순 리스트를 필터 · Lot · Slot · 정렬로 추린 뒤 **[리스트 결정 → 3단계 취합]** 을 누르십시오. 지금 보이는 리스트 전체가 대상입니다(2만 개가 넘으면 한 번 더 묻습니다).
    - **3단계 · 취합**: 로딩창(`리스트 취합 중`, Slot 폴더 k / N)이 뜨고, 리스트에 든 Slot 만 Step 1 과 같은 방식으로 다시 읽습니다(ProductInfo · Wafer Map 파일 · s_DieLocation · ColorImageGrabingInfo · ScanResultImageList · frameToChuckPlane). 그다음 Defect 마다 Die · Color 이미지 · Gray 프레임을 연결합니다.
    - **Slot 별 취합 결과 표**(소유자 지시 2026-11-10 "각종 .ini 파일 불러와서 리스트 취합 결과 봐야 해"): Slot 마다 리스트 수 · Defect 전체 · ColorImageGrabingInfo 항목 수 · Color 연결 · Color 사진 있음 · ScanResultImageList 프레임 수 · Gray 연결 · Gray 사진 있음 · frameToChuckPlane · Die(ProductInfo) · Wafer Map · s_DieLocation · 읽은 .ini/.txt · 점검. 0 인 칸은 빨간 굵은 글씨입니다. '사진 있음' = 연결된 사진 파일이 폴더에 실제로 있는지 이름으로 확인한 수(내용은 볼 때 읽음). [리스트 취합 결과 CSV] = 결정한 리스트 전부(Defect 값 · Die · Color/Gray 파일 · 사진 있음 · 사진 경로).
    - 결과 화면 = Step 3 · 4 와 같은 리뷰 화면: wafer map(결정한 Defect, Lot 마다 색) · 리스트 · Color · Gray Crop · 정보(Die · Color · Gray · GL). 더블 클릭 · Enter = 새 창, [⧉ 새 창으로 크게 보기] = wafer map 새 창.
    - **폴더의 PC 경로(필수)**: [Lot 폴더 추가]로 폴더를 고르면 바로 '고른 폴더의 PC 경로 입력' 창이 뜹니다. 탐색기 주소창의 경로를 붙여 넣으십시오(예: `D:\AOI\BIG` 또는 `\\서버\공유\BIG`). 경로는 `D:\` 또는 `\\서버\공유` 로 시작하고 마지막 폴더가 고른 폴더 이름과 같아야 합니다. **입력하지 않으면 [확인]이 눌리지 않고, 취소하면 그 폴더는 등록되지 않습니다.** 폴더 이름마다 기억해 다음에 미리 채웁니다(이 PC 브라우저). 브라우저는 보안 규칙 때문에 고른 폴더의 이름만 알려 주고 PC 전체 경로는 알려 주지 않습니다.
    - **📷 Color 사진 경로 열기 · 📷 Gray 사진 경로 열기**: 보고 있는 Defect 의 사진 파일 경로(사진을 실제로 찾은 곳)를 복사하고 그 사진을 새 탭으로 엽니다. 화면에 두 사진의 경로와 `사진 열기` · `사진 폴더 열기` 링크가 나옵니다. 경로를 고치려면 [PC 경로 바꾸기]를 누르십시오(Step 1 에서 등록한 Lot 처럼 경로를 넣지 않은 폴더도 여기서 넣습니다).
    - 사진 찾기: 이름의 대소문자가 달라도(`.JPEG`) 찾고, 한 번 실패한 사진을 다시 시도합니다.
    - [← 2단계 리스트로 돌아가기] 로 리스트를 다시 고를 수 있습니다. 한 번 읽은 Slot 은 다시 읽지 않습니다.

12. **rev2 판**(`AOI_Contrast_Wizard_rev2.html`, 2026-11-10 소유자 세션 지시 "새 파일로 따로"): 원래 파일 · rev1 과 별개인 세 번째 파일입니다. 시험 `node tools/test_contrast_wizard_rev2.mjs`.
    - **폴더 인식**: 구조 = 레시피 / Setup / Lot / Slot(최대 25). **Surface.flt 가 있는 폴더 = Slot, 그 바로 위 폴더 = Lot** — 레시피 · Setup · Lot 어느 폴더를 골라도 같은 Lot(Step 1 도 같음). 위쪽 폴더(Lot · Setup · 레시피)의 파일(사진 제외)은 그 아래 Slot 이 같이 쓰고, 같은 이름이면 Slot 것을 씁니다.
    - **5-1 Contrast 모으기 · 걸러내기**: [레시피 폴더 고르기](Edge/Chrome 읽기 전용 폴더 창) → 폴더만 훑어 Slot 을 찾고(폴더마다 Surface.flt 를 이름으로 바로 확인, **Slot 안 사진 목록은 만들지 않음**) Slot 마다 `Surface.flt`(+ `.md`) · `ProductInfo.ini` 만 읽습니다. [동시에 읽을 폴더] 1 · 2 · 4(기본) · 8. 여러 레시피 폴더를 차례로 더할 수 있습니다.
      목록 = Lot · Slot · Contrast(실제) · Area · Width · Length 필터 + 정렬(열 제목 클릭, 기본 Contrast 큰 순). [목록 CSV] = 사진 정보 없는 목록.
    - **5-2 사진 짝짓기 · CSV 저장**: [다음]을 누르면 CSV 저장 위치를 먼저 고르고(고르기 창은 누른 직후에만 열 수 있음, 취소해도 짝짓기는 함) 지금 목록(필터 · 정렬 그대로)의 Defect 마다 Color 이미지(ColorImageGrabingInfo 좌표 → 번호 규칙)와 Gray 프레임 + 픽셀 좌표(ScanResultImageList · frameToChuckPlane)를 짝짓고 파일이 실제로 있는지 확인합니다(사진 픽셀은 읽지 않음).
      상태 = 짝 완료 / Color 만 / Gray 만 / 둘 다 없음(이유 함께). CSV 열 = 순서 · 상태 · Lot · Slot · ID · Contrast · Area · Width · Length · Box · Wafer X/Y · Die · Color 이미지 · **Color 경로** · Color 연결 · Gray 프레임 · **Gray 경로** · Gray 픽셀(3168×1024 기준) · 모델 · 이유.
      브라우저는 전체 경로를 알려 주지 않아 경로는 고른 폴더 이름부터 적힙니다 — [원본 폴더 경로]에 상위 폴더(예 `Y:\AOI-16\Scanresult`)를 적으면 앞에 붙입니다(이 PC 에 기억, 선택).
    - **5-3 사진 정밀 조사**: 짝지은 Defect 만(기본 '짝 완료만', 짝 완료가 없으면 자동으로 끔). [하나씩 크게] = 목록 + Color 원본 + Gray Crop(빨간 박스 = Box W×H, GL 측정) + **진행 기록**(사진 목록 확인 → Color 찾기 · 읽기 · 디코딩 → Gray 프레임 찾기 · 읽기 · 디코딩 → 크롭 · GL, 단계마다 걸린 시간) + 정보, 다음 3개 미리 읽기.
      더블 클릭 · Enter · 사진 누르기 = 새 창(Color 원본 + Gray 프레임 전체). [격자로 여러 개] = 한 쪽 48개 카드(Color · Gray Crop, ROI−local). [이 목록 사진 모두 미리 준비] = 같은 Gray 프레임끼리 묶어 한 번만 디코딩(로딩창 · 중지).
      Crop 크기 · Ring 폭 · Offset · 반전은 Step 2 와 같은 값(어느 쪽에서 고쳐도 같이 바뀜). 짝짓기에 영향을 주는 값이 바뀌면 '5-2 다시 하기' 안내.
    - **로딩창**(모든 긴 작업): 단계 목록(✔ 끝 · ▶ 지금) · 개수(k / N) · 진행 막대 · 지금 읽는 폴더/파일 · `경과 · 마지막 진행 n초 전 · 속도 · 남은 시간`. '마지막 진행'이 3초를 넘으면 노란 글 '응답을 기다리는 중'(네트워크 드라이브 · 큰 파일), 브라우저 계산으로 화면이 멈췄으면 '화면이 n초 멈췄었음'. [중지] = 지금 파일까지 끝내고 멈춤(5-2 는 남은 것 '확인 안 함').
    - 이름으로 바로 못 찾은 파일(예: 사진이 Slot 하위 폴더에 있음)만 그 Slot 파일 목록을 한 번 만들어 찾습니다(로딩창에 개수). Edge/Chrome 이 아니면 폴더 고르기(webkitdirectory)로 바뀌어 느립니다(사진 내용은 읽지 않음).
    - 시험 = 가짜 폴더 Lot 40 × Slot 25(Slot 마다 사진 3,000장, 호출마다 8 ms 지연): 5-1 약 14초(Slot 안 목록 0번), 짝짓기 1,000개 약 20초. 합성 30만 Defect 필터 + 정렬 약 0.03초. 실제 큰 폴더 · 네트워크 드라이브로는 확인 전.
    - **Color 연결(2026-11-10, 소유자 확정 "Color 이미지 정보는 어떤 경우에도 있다 · 사진은 모두 Slot 폴더 안")**: 스캔(Slot)마다 기준을 한 번 정한 뒤 Defect 마다
      ① 좌표(Color FaultX/FaultY ↔ Defect x/y 또는 ActualX/Y 중 더 잘 맞는 쪽, 스캔 전체에서 **일정한 어긋남을 찾아 보정**) 허용오차 안 → ② 번호(Color Index = Defect 번호 규칙 — 기록 순서 · id · resultID 중 Defect 마다 값이 다른 규칙만) →
      ③ 가장 가까운 Color 중 Defect 가 그 Color 사진 범위(ImageSize × PixelSize) 안에 드는 것('확인 필요'). `ColorImageGrabingInfo.ini` 가 없거나 항목이 없으면 Slot 폴더의 Color 사진 이름(`X.Y.c.번호.jpeg`, 앞 두 숫자 = 좌표)으로 연결합니다.
      ini · txt 는 UTF-8 · UTF-16 · EUC-KR 을 알아서 읽습니다. 5-2 결과에 'Color 연결 방법'(좌표 · 어긋남 보정 좌표 · 번호 · 가장 가까운 것 개수)과 좌표가 그대로 맞지 않은 Slot 의 기준(어긋남 · 규칙)을 보여 주고, 못 붙이면 이유(가장 가까운 Color 와의 거리)를 적습니다.
      실제 결과 폴더(`사진 제외.zip`, 353개)로 확인: 그대로 · 100 µm 어긋남 · 어긋남 + Index 없음 · ±8 µm 흔들림 · ini 없음 · UTF-16 ini 모두 353/353 맞는 Color(종전은 어긋남이면 0, UTF-16 이면 'Color 파일 없음' 353).

13. **rev3 판**(`AOI_Contrast_Wizard_rev3.html`, 2026-11-10 소유자 세션 지시 "Rev2에 적용해서 rev3으로", 시험 `node tools/test_contrast_wizard_rev3.mjs`): rev2(위 Color 연결 포함) + **5-2 · 5-3 이 Slot 을 Step 1 과 똑같이 읽음**. rev2 · 원래 파일 · rev1 은 그대로입니다.
    - 왜 바꿨나(소유자 "1,2,3 에서는 되는 Lot 도 5 에서는 안 된다 — 방식이 다른 것 아니냐"): 맞습니다. rev2 의 5-2 는 Slot 폴더에서 `ColorImageGrabingInfo.ini` · `ScanResultImageList.txt` · `frameToChuckPlane.ini` 를 **이름으로만** 찾았고, Step 1 은 Slot 안 파일 전부 + Lot ~ Slot 사이 폴더(위쪽 폴더)의 파일을 모아 읽습니다.
      그래서 이 파일들이 Slot 이 아니라 위쪽 폴더(예: Lot 폴더)에 있거나 Slot 하위 폴더에 있으면 Step 1 은 되고 rev2 5-2 는 '없음'이 됩니다(실제 zip 의 세 파일을 Lot 폴더로 옮겨 재현: Step 1 353 · rev2 5-2 짝 0 · rev3 353).
    - rev3: 5-2 를 누르면 리스트에 있는 Slot 만 **Slot 안 파일 전부(사진은 이름 · 핸들만, 내용은 안 읽음) + 위쪽 폴더 파일**을 모아 Step 1 의 `buildScan` 그대로 읽습니다(Color · Gray 프레임 · 변환 · Wafer Map · ProductInfo 전부 Step 1 과 같은 값). 5-1 은 rev2 와 같이 빠르게(Surface.flt · .md · ProductInfo 만).
    - **Slot 별 읽은 결과** 표(5-2 결과 아래, 문제 있는 Slot 이 있으면 펼쳐짐 · 노란 줄): Lot · Slot · 리스트 Defect · Color 항목 수 · Color 연결 · Color 사진 있음 · Gray 프레임 수 · frameToChuckPlane · Gray 연결 · Gray 사진 있음 · 파일 수(사진, 위 폴더) · Color 기준 · 점검. 그래도 안 되면 이 표의 그 Slot 줄을 보면 어디서 끊겼는지 알 수 있습니다.
    - 시험: 실제 결과 폴더(`사진 제외.zip`) 그대로 · 100 µm 어긋남 · UTF-16 ini · ini 없음 · 어긋남 + Index 없음 · ±8 µm 흔들림 · 세 파일이 Lot 폴더에 있음 — 모두 353/353 맞는 Color. 가짜 큰 폴더(rev2 와 같은 조건)에서 5-2 약 30초(rev2 약 20초 — 고른 Slot 의 파일 목록을 전부 만들기 때문), 5-1 약 14초 그대로. 실제 큰 폴더 · 네트워크 드라이브로는 확인 전.

14. **rev4 판**(`AOI_Contrast_Wizard_rev4.html`, 2026-11-10 소유자 세션 지시 "rev4 로 새 파일 만들어서 둘 다 적용해", 시험 `node tools/test_contrast_wizard_rev4.mjs`): rev3 + 아래 두 가지. rev3 · rev2 · rev1 · 원래 파일은 그대로입니다.
    - 조사 결과(rev3 까지): 5-1 이 모으는 Defect 정보(x · y · ActualX · ActualY · id · resultID · 기록 순서 · recipe · Box · Area · Width · Length · Contrast)는 사진 짝짓기에 충분합니다(실제 결과 폴더 353개 모두 Step 1 과 같은 값 · 같은 Color · 같은 Gray 프레임 · 픽셀).
      `frameIdx` · `xInFrame` · `yInFrame` 은 모으지 않지만 어느 Step 도 쓰지 않고 실제 자료는 전부 0 입니다. 빈틈은 **`Surface.flt.md`(Surface.flt 안 필드 자리) 를 Slot 바로 안에서만 찾던 것** — md 가 Lot 폴더 · Slot 하위 폴더에 있고 그 배치가 기본과 다르면 5-1 좌표 · Contrast 가 틀립니다(재현: x · y 자리를 바꾼 md 를 Lot 폴더에 두면 rev3 5-1 좌표 353개 전부 틀림, Color 0 · Gray 3).
    - **① 5-1 이 `Surface.flt.md` 를 Step 1 과 같은 순서로 찾음**: Slot 바로 안 → Slot 하위 폴더(이름 순, 4단계까지) → 위쪽 폴더(가까운 것부터). Slot 바로 안에 있으면 지금처럼 Slot 안 목록을 만들지 않습니다(빠름). 없을 때만 그 Slot 폴더 목록을 한 번 만들어 하위 폴더를 봅니다 — 로딩창에 '하위 폴더까지 찾은 Slot n개', 결과에 `Surface.flt.md 위치: Slot 안 · Slot 하위 폴더 · 위쪽 폴더 · 없음(기본 배치)` 개수.
    - **② 5-2 안전장치**: 5-2 에서 Slot 을 Step 1 방식으로 읽은 뒤 5-1 이 모은 값과 Defect 마다 비교합니다. 다르면 그 Slot 을 Step 1 값으로 바꾸고 5-1 필터를 다시 걸어 목록을 다시 만든 뒤 짝짓습니다(Contrast 를 틀리게 읽어 빠졌던 Defect 도 돌아옴, 새로 들어온 Slot 도 읽음). 5-2 · 5-1 화면에 `Slot n개는 … Step 1 값으로 바꾸고 5-1 필터를 다시 걸었습니다(Defect a개 → b개): Slot — x 353개 · …`.
      'Slot 별 읽은 결과' 표에 **Surface.flt.md · 5-1 값** 칸(예 `위쪽 폴더 · 값 같음`, `5-1 Slot 안 / Step 1 Slot 하위 폴더 · 값 다름 → Step 1 값으로 (x 353개)`) — 다르면 노란 줄. 안전장치는 5-1 목록에 남은 Slot 에서만 동작합니다(목록에 없는 Slot 은 5-2 에서 읽지 않음).
    - 5-2 진행 = ① 리스트의 Slot 읽기 · 5-1 값 비교(Slot k / N) → ② Defect 짝짓기(Defect k / N) → ③ 결과.
    - 시험: 실제 결과 폴더 + md 위치(Slot · Lot 폴더) × 배치(기본 · x/y 바꿈) 4가지 모두 5-1 값 · Die · Color · Gray 353/353 이 Step 1 과 같음, Color 연결 변형 6가지 · ini 를 Lot 폴더에 둔 경우 353/353.
      가짜 큰 폴더(Lot 40 × Slot 25, Slot 마다 사진 3,000장): md 가 Slot 안이면 5-1 약 14초 · 5-2 약 30초(rev3 과 같음), md 가 모든 Slot 에서 Lot 폴더에 있으면 5-1 약 25초. 실제 큰 폴더 · 네트워크 드라이브로는 확인 전.
15. **rev5 판**(`AOI_Contrast_Wizard_rev5.html`, 2026-11-10 소유자 세션 지시 "프로그램에 있는 기능을 최우선으로 · 설정은 아예 없애 · 결과물은 목록으로, 새 창에서 큰 화면으로 사진들만", 시험 `node tools/test_contrast_wizard_rev5.mjs`): rev4 + 아래. rev4 이하는 그대로입니다.
    - **Color · Gray 매칭 = Para 프로그램 'Color · Gray 매칭'(`param_manager/colorgray.py`)과 같은 계산**: 5-1 에서 Slot 마다 매칭 파일 3개(ColorImageGrabingInfo.ini · ScanResultImageList.txt · frameToChuckPlane.ini)를 이름으로 바로 읽어(폴더 목록은 만들지 않음) Color 항목마다 Gray 프레임 · 픽셀을 구합니다. 사진은 읽지 않습니다.
      매칭 폴더 = 세 파일이 바로 안에 있는 폴더(Slot 바로 안 → 없으면 Slot 하위 폴더 중 세 파일이 다 있는 첫 폴더. Surface.flt 가 있는 하위 폴더는 다른 Slot 이라 빌려 쓰지 않음). 위쪽 폴더(Lot · Setup)의 세 파일은 쓰지 않습니다(프로그램과 같음).
      좌표 기준(그대로 → 맞지 않으면 프레임 직사각형의 좌측 하단 원점 해석 중 가장 많이 맞는 것)도 프로그램과 같습니다. Defect → Color 항목 = Index(기록 순서) + 좌표 5 µm 확인, 아니면 5 µm 안 가장 가까운 Color. Color 항목이 없는 Defect 는 Defect 좌표로 Gray 만 찾습니다.
      5-1 목록에 **'Color · Gray 매칭'** 칸(Color · Gray / Color 만 / Gray 만 / 짝 없음 / 매칭 파일 없음)이 생겼습니다.
    - **매칭 파일이 다 없어도 됩니다**(소유자 확정: ColorImageGrabingInfo.ini 는 항상 있음 · ScanResultImageList.txt 는 없을 수 있음 · 변환 파일이 `frameToChuckPlane.1.ini` · `.2.ini` 둘이면 .2 기준). 프로그램 파일이 있으면 프로그램 계산 그대로이고, 없는 것만 대신 계산합니다.
      ScanResultImageList.txt 없음 → **Gray 사진 이름**(`-56211.70388.t.jpeg` = 프레임 가운데의 장비 Table 좌표)을 `Wafer2Table.ini` 로 웨이퍼 좌표로 바꿈(없으면 `s_FrameData.dat` 의 같은 프레임). 변환 파일이 번호 파일 여러 개면 가장 큰 번호, 하나도 없으면 '목록 좌표 = 프레임 가운데' 모델.
      실제 결과 폴더에서 파일을 빼고 시험: 모두 353/353 같은 Gray 프레임, 픽셀 차 최대 2.6 px(사진 이름 + Wafer2Table) · 0 px(+ s_FrameData) · 0.13 px(변환 파일 없음). 무엇으로 계산했는지는 5-1 알림 · Slot 별 결과 표 · CSV 에 나옵니다. 대신할 것도 없으면 짝을 만들지 않고 이유를 알립니다.
      참고: Para 프로그램의 Color · Gray 매칭(원 v16 부터)은 세 파일이 모두 있어야 Wafer 폴더로 인식합니다(사진만으로는 매칭하지 않음). 이 대신 계산은 rev5 HTML 에만 있습니다.
    - **5-2 = 결과 목록 · 사진 새 창 · CSV**: 사진 파일이 매칭 폴더에 있는지 이름 목록으로만 확인합니다(다른 파일은 열지 않음). rev3 · rev4 는 Slot · 위쪽 폴더의 사진 아닌 파일을 전부 열어, 하나만 열기에 실패해도 그 아래 Slot 이 모두 0 이 됐습니다(재현: Slot 안 파일 1개 → 그 Slot 0/353, Setup 폴더 파일 1개 → 모든 Slot 0).
      줄 더블 클릭 · Enter · [⧉ 사진 새 창] = **사진 새 창**(큰 화면, 사진만): 위 = Color 원본 | Gray Crop(Color 시야), 아래 = Gray 프레임 전체(빨간 + = Defect, 노란 상자 = Crop 범위). 새 창은 목록에서 고른 줄을 따라가고, **새 창에서 방향키(↑↓ ←→ · PageUp/PageDown · Home/End)로 다음 · 이전 Defect** 로 넘어갑니다(목록도 같이 움직임, 끝에서는 멈춤). 사진을 누르면 원래 크기 ↔ 창 맞춤.
      사진마다 위쪽 제목에 **사진 파일명과 전체 경로**(예 `Y:\AOI-16\Scanresult\…\W01\266814.266016.c.-1445395397.jpeg`)가 나옵니다(사진을 가리지 않음, 경로는 끌어서 복사). 5-3 칸 제목 · 정보 표 · 5-2 결과 목록('Color/Gray 전체 경로' 칸) · CSV 도 같은 경로, 격자 카드는 파일명(마우스를 올리면 경로).
      브라우저는 고른 폴더의 PC 경로를 모르므로 **5-1 의 [원본 폴더 경로(PC)]** 에 탐색기 주소창 경로(고른 폴더 자체 또는 그 상위 폴더, `\\서버\공유\…` 도 됨)를 한 번 적으십시오(이 PC 에 기억, 5-2 칸과 같은 값). 비어 있으면 고른 폴더 이름부터 나오고 새 창 위에 안내가 나옵니다. 본 화면 목록(5-2 · 5-3)도 ←→ 로 이전 · 다음.
      CSV 열 추가: FaultX · FaultY · 후보프레임 · Gray계산(Color 좌표 / Defect 좌표) · 좌표기준 · CropW · CropH · 매칭폴더.
    - **5-3 Gray Crop = 프로그램과 같음**: Color 시야(ImageSize × PixelSize ÷ 0.769644 µm, 실제 자료 829×622 px)만큼 Defect 가운데로 잘라 Color 크기(1380×1036)로 늘린 흑백입니다. GL 은 그 Crop 의 원래 해상도에서 Box W×H · Ring 폭으로 잽니다.
    - **설정 없앰**: 결함 좌표 · Pixel Size · Color 연결 허용오차 · X/Y 반전 · X/Y Offset 칸을 없앴습니다(종전 기본값 x/y · 0.7708 · 5 µm · 반전 없음 · 0 으로 고정, Step 3 · 4 도 같음). Crop 크기 · Ring 폭(Step 3 · 4 GL)은 남겼습니다.
    - **Slot 찾기**: Surface.flt 가 있는 폴더에 ColorImageGrabingInfo.ini 가 바로 없으면 그 아래 폴더도 봅니다(Lot 폴더에 Surface.flt 가 있어도 실제 Slot 이 빠지지 않음 — Step 1 과 같음). Surface.flt.md 찾기 순서는 rev4 와 같고, rev4 의 '5-1 값 ↔ Step 1 값' 안전장치는 없앴습니다(그 확인이 Slot 전체를 다시 읽는 과정).
    - 시험: 실제 결과 폴더(`사진 제외.zip`) Defect 353개 모두 Color · Gray 프레임 · 픽셀 · 후보 수가 이 브랜치의 `colorgray.py` 와 같음 — 그대로 · 관계없는 파일 열기 실패(Slot 안 · Setup 폴더) · Lot 폴더 Surface.flt · 좌측 하단 원점 좌표 4가지. 실제 사진 · 네트워크 드라이브 속도는 확인 전.

**폴더 인식(2026-11-10)**: Step 1 · Step 5 모두 **고른 폴더 바로 아래 폴더 = Lot**, Surface.flt 가 있는 폴더 = Wafer Slot(이름 = 그 폴더 이름)입니다. Slot 이 Lot 안 몇 단계 아래에 있어도(예: `고른 폴더/Contrast Avg24/Job/Setup/SM/Wafer/Surface.flt`) 그 Lot 으로 묶습니다.
- Lot 폴더 하나를 고르면(`Lot/Wafer/Surface.flt`) 고른 폴더 = Lot, Slot 폴더를 고르면 Slot 1개짜리 Lot.
- 고른 폴더 바로 아래 폴더마다 Surface.flt 가 바로 있고 폴더 이름마다 다른 CA 번호(`CA20`, `CA27` …)가 있으면 그 폴더들을 Lot 으로 봅니다.
- Contrast AVG · Step 이름은 Lot 폴더 이름 → Lot ~ Slot 사이 폴더 → Slot 폴더 → 고른 폴더 순으로 'CA27' · 'Avg24' 같은 이름을 찾습니다.
- Lot 폴더 ~ Slot 사이 폴더에 있는 파일(ProductInfo.ini · Wafer Map 등, 사진 제외)은 그 아래 Slot 들이 같이 씁니다(Slot 에 같은 이름이 있으면 Slot 것). 같은 Lot 에 같은 이름 Slot 이 둘이면 사이 폴더 이름을 붙여 구분합니다.
- 등록 결과 맨 위에 `폴더 '…' → Lot n개(…)` 로 어떻게 인식했는지 보여 줍니다.

## 2. 계산 규칙

| 항목 | 규칙 |
|---|---|
| Surface.flt | 152 byte 고정 레코드, little-endian, 이슈 본문 필드 표 그대로(`FLT_FIELDS`). `Surface.flt.md` 에 같은 이름 필드가 있으면 그 offset · 형식을 쓰고 경고. byteLength 가 152 로 나누어떨어지지 않으면 오류 |
| Area(µm²) | area(pixel) × PixelSize² (기본 0.7708). 예: 82 → 48.72 |
| 동일 Defect | Wafer x/y(또는 ActualX/Y 선택) 거리 ≤ 허용오차. 격자 최근접 검색 + 거리순 greedy 1:1 (중복 매칭 없음) |
| 구분(집합 기호, 차집합 = `-`, #56) | 쌍 A → B 마다 `A - B`(A 에만 = B 에서 없어진 Defect) · `A ∩ B`(둘 다) · `B - A`(B 에만). 리스트(Step) 이름으로 표기(유지 · 소거 · 신규 라는 말은 쓰지 않음, 소유자 지시). 보기 = `A ∪ B`(모두) · `A (전체)` · `B (전체)` · `A - B` · `A ∩ B` · `B - A` — Wafer map 단추와 상세 표 [보기] 가 같음 |
| 집합 · 벤다이어그램 (#55) | 같은 Defect 묶음 = Contrast AVG 오름차순으로 스캔을 차례로 1:1 매칭(같은 허용오차, 묶음 위치 = 처음 나온 스캔의 좌표). 묶음마다 들어 있는 스캔 = 영역. 영역 이름 = `들어 있는 스캔 ∩ … - (없는 스캔 ∪ …)`, 예) `CA20 ∩ CA27 - CA30`. 스캔 2개면 영역 3개 = 쌍 비교의 `A - B` · `A ∩ B` · `B - A` 와 같은 수(시험이 확인). 4개 타원 배치는 15개 영역이 모두 생기게 수치로 찾은 값 |
| 쌍 | 리스트를 Contrast AVG 오름차순(빈 값은 등록 순서로 뒤)으로 놓고 i ≠ j 모든 순서쌍(#56, n개 → n×(n−1)쌍, A 순서 → B 순서로 나열). 쌍별 표 = A · B Defect 수, 둘 다, A 에만, B 에만, 없어진 비율(A 에만 ÷ A) |
| Wafer map | **맵 파일 없이 계산**(#52 소유자 확정 좌표): Die 좌표 = 좌측 하단 (0,0) 에서 x, y 그래프처럼 오른쪽 · 위쪽으로 1씩. ① 칸 짝수/홀수 = ProductInfo 격자 (Cols−1)×(Rows−1) 가운데에 wafer 중심을 둘 때와 같게 ② 반지름 = Wafer 지름/2 − Edge 제외(Step 2, 기본 300 mm · 0 mm, ProductInfo 에 `WaferDiameter`/`WaferSize`/`EdgeExclusion` 이 있으면 그 값) ③ Die = 네 모서리가 모두 원 안인 칸(굵게) ④ **wafer 중심(#53) = ProductInfo `[Geometric] CenterX/CenterY`**(없으면 Params_WaferInfo `Center_X/Y` → `s_DieLocation.dat` Die 묶음 가운데 → 셋 다 없을 때만 종전 추정 = 그 Die 들의 좌측 하단이 Wafer (0,0) 이 되는 위치). 화면 Die 번호는 맨 왼쪽 아래 Die = (0,0) 으로 다시 센다(장비 Col/Row 와 다르면 상세 표에 '장비 Col, Row' 함께). 실제 폴더(#53): 중심 (204849, 224520) µm = (5.5·PitchX, 5·PitchY), 맨 왼쪽 아래 Die = 장비 Col 2 · Row 2, s_DieLocation 30개 · Color 이미지 Col/Row 353개와 일치, Defect 353개 모두 원 안. 아래 '예시 맵 중심 (3.5·PitchX, 3·PitchY)'는 중심 정보가 없을 때의 추정이다. 검증: #50 ProductInfo(37249×44905.8, Cols 10, Rows 9)로 소유자 예시 맵(7×6, 아래 줄부터 3·5·7·7·5·3 = 30)과 같고 wafer 중심 = (3.5·PitchX, 3·PitchY) = (130372, 134717) µm. 점선 = Die 를 꽉 채우는 직사각형(좌측 하단 (0,0)). Wafer Map 파일(RowData)이 있으면 비교만: 맵 칸 (r, c) ↔ Col = c, Row = (ROWCT−1) − r(맵 맨 아래 줄 = Row 0), 일치 여부 표시 · 다른 칸 점선(계산에만 빨강, 맵에만 주황) · Bin ≠ 000 옅은 노랑. 상세 표 Die 칸에 Die 가 아닌 칸은 'wafer 밖 칸', 상태 문구에 원 밖 Defect 수. X 오른쪽 · Y 위쪽(맵 파일과 같은 방향). **Notch** = wafer 원 가장자리의 V 홈 + 'Notch' 글자. Step 2 [Notch] 자동 = 맵 파일 `FNLOC`(0 위 · 90 오른쪽 · 180 아래 · 270 왼쪽) → ProductInfo(`FNLOC`/`Notch`/`NotchAngle`/`FlatAngle` 등) → 없으면 아래(180). 직접 고를 수도 있음 |
| Die 판정 순서 (#52 후속, 어떤 자재에도) | 그리는 Die = ① `s_DieLocation.dat`(장비가 실제로 스캔한 Die) → ② Wafer Map 파일 RowData(`___` 아닌 칸, 맵 Die 묶음의 왼쪽 아래를 기준 Die 묶음의 왼쪽 아래에 맞춤) → ③ 계산(네 모서리가 모두 원 안, '확인 필요' 표시). 계산 결과는 늘 남겨 ①·② 와 비교만 한다(`#mapSt` 에 일치 ✔ / 다름 수). 상태 문구 맨 앞 `[기준 …]` 이 어느 것으로 그렸는지 알려 준다. wafer 중심은 #53 순서(ProductInfo CenterX/Y → s_DieLocation 가운데 → 추정) 그대로 |
| Wafer map 과 원 · Notch 맞춤(#57) | ① 맵 파일만 있을 때(s_DieLocation 없음) 맵 Die 묶음의 **가운데**를 wafer 중심에 맞춘다(종전: 계산 Die 묶음의 왼쪽 아래에 맞춰 맵이 계산보다 크면 맵만 오른쪽 위로 밀렸다 — 소유자 #57 지적). ② 그리는 Die(s_DieLocation · 맵)의 가운데가 wafer 중심(ProductInfo 등)과 0.75 Pitch 넘게 다르면 원 · Notch 를 그 Die 묶음 가운데로 옮기고 상태 문구에 '중심과 x, y µm 달라 Die 에 맞춤'을 적는다. 실제 폴더(#53)는 두 값이 같아 ProductInfo 그대로 |
| Die | (#53 확인: ColorImageGrabingInfo 의 장비 Col/Row 와 353/353 같음) (#52 소유자 확정) `Col=floor((X−OffX)/PitchX)`, `Row=floor((Y−OffY)/PitchY)` — 좌측 하단 (0,0) 에서 오른쪽 · 위쪽으로 1씩, Die 내부 = 그 Die 좌측 하단에서의 거리. 종전 #50 문서 식 `DieCol=(Cols−2)−ix`, `DieRow=(Rows−2)−iy` 는 폐기. 값은 폴더마다 `ProductInfo.ini` 에서 읽음. 없으면 "계산 불가" |
| Gray 위치 | **Para 'Color · Gray 매칭'(`param_manager/colorgray.py`)과 같은 모델**: `frameToChuckPlane(.<레시피>).ini` 의 `Scan_X/Scan_Y` 역행렬로 `p = M⁻¹·(결함 − 프레임 좌표 − offset)`, 3168×1024 안에 들고 가장자리에서 가장 먼 프레임. 레시피 번호(.t.<n>)가 맞는 프레임 먼저 |
| Gray 간단 모델 | `frameToChuckPlane` 이 없을 때만: `(결함 − 프레임 좌표) / PixelSize`. "보정 필요" 표시. 두 모델 모두 X/Y 반전 · X/Y Offset 을 Step 2 에서 조정 |
| 범위 밖 | 어떤 프레임에도 들지 않으면 임의 위치를 보이지 않고 "좌표 변환 보정 필요" |
| Crop | 결함 중심 Crop(기본 160 px), 가운데 빨간 박스 = BoxWidth × BoxHeight(pixel) |
| Color 연결 | ① ColorImageGrabingInfo.ini Fault 좌표 최근접(Color 연결 허용오차, 기본 5 µm) ② 인덱스 규칙(id · id±1 · resultID · resultID±1 · 기록 순서 0/1)을 **스캔마다 하나** 고름 — 좌표로 검증된 수가 가장 많은 규칙, 검증이 없으면 맞는 수가 가장 많은 규칙("좌표 없음 · 확인 전") |
| GL 측정 | Gray Crop 을 볼 때 ROI(Box) mean/median/max, 주변 ring(기본 6 px) median, ROI−ring delta. **Local Reference 추정치**이며 장비 Contrast 와 같다고 보지 않음 |
| 좌표 모델 확정 | 리뷰에서 "맞음" 10개 이상 + "벗어남" 0개일 때만 "확인됨". 그 전에는 "미확정" |

## 3. 성능 · 안전

- 네트워크 요청 없음(시험이 file/blob 밖 요청 0건을 확인). 원본은 `<input webkitdirectory>` 로 읽기만.
- Wafer Map = Canvas. 벤다이어그램 = 픽셀마다 타원 안/밖 판정(집합 · 영역을 바꿀 때만 다시 그림, 깜빡임 때는 안 그림). 상세 표 = 쪽당 200행. 목록 = 가상 스크롤.
- 새 창 wafer map 은 같은 파일이 연 창이라 이 화면이 그 창의 canvas 에 직접 그린다(서버 · 메시지 없음).
- Step 5: Defect 를 객체가 아니라 열 배열(Float64Array 등, Defect 1개 ≈ 90 byte)로 두고 필터 · 정렬은 번호 배열만 다룬다. 시험 = 합성 30만 Defect 등록 약 0.3초 · 필터 + 정렬 약 0.03초(개발 PC). 표는 보이는 줄만 그리고, 100만 줄을 넘으면 앞 100만 줄만 그린다(CSV 는 전부). 폴더는 `showDirectoryPicker({mode:'read'})` — 읽기 전용, 쓰기 권한을 요청하지 않는다.
- 이미지 캐시 LRU: Color object URL 80개(버리면 `revokeObjectURL`), Gray 프레임 ImageBitmap 16개(버리면 `close`). 현재 항목 앞뒤 8개 Color, 4개 Gray 를 미리 읽음.

## 4. 확인 전(소유자 확인 필요)

- (2026-11-10 필터 · Step 5) 실제 큰 Lot 폴더로는 확인하지 못했다(합성 자료 시험만). Width = `BlobBreadth`, Length = `BlobLength`, Area 필터 단위 = µm²(화면 값)로 보았다. Step 5 에서 등록한 Lot 은 비교(Step 2 ~ 4)에 들어가지 않는다. Step 5 Lot 의 Step 이름 · Contrast AVG 는 폴더 이름에서만 읽는다(고치는 칸 없음). 읽기 전용 폴더 창(`showDirectoryPicker`)이 회사 PC 정책으로 막히면 예전 폴더 고르기로 바뀐다.

- (#57) Slot 짝 = Slot 폴더 이름(대소문자 무시). Lot 마다 Slot 폴더 이름(Wafer ID)이 같은 Wafer 라고 보았다. 기본 보기 단위 = Lot 별. Lot 별 wafer map = 모든 Slot 을 한 지도에 겹침. Step 이름이 같은 Lot 이 둘 이상이면 Lot 경로로 바꿈. 원 · Notch 를 Die 에 맞추는 기준 0.75 Pitch(내 해석, 확인 전). 소유자가 말한 '다른 파일'을 받지 못해 그 파일로 직접 확인하지는 못함(합성 자료로 재현 · 확인).

- (#55) Step 4 를 지우지 않고 Step 3 과 같은 구성으로 남김(위 7번 이유). 벤다이어그램 '관련 영역' = 고른 집합이 하나라도 들어 있는 영역. 스캔 5개 이상은 벤다이어그램 대신 영역 표만.

- Surface.flt 의 x/y 가 ColorImageGrabingInfo 의 FaultX/FaultY 와 같은 좌표계라고 가정했다(Color · Gray 매칭과 같은 변환을 쓰려면 필요). 다르면 Step 2 의 [결함 좌표] ActualX/ActualY 를 고르거나 Offset 으로 보정.
- `s_FrameData.dat` 는 크기만 표시하고 좌표 계산에는 쓰지 않는다(이슈에서 Gray color 매칭 쪽이 더 정확하다고 함).
- ProductInfo.ini 키 이름: `CustomerDiePitch_X/Y`, `Cols`, `Rows`, Offset 은 `CustomerDieOffsetX/Y` · `OffsetX/Y` · `DieOffsetX/Y` · `MapShiftX/Y` 중 하나를 받음. 실제 이름이 다르면 알려 주십시오.
- ScanLog/ProductionInfo 의 Surface defect 수는 파일 이름이 `ScanLog*` · `ProductionInfo*` 이고 글에 "Surface … 숫자"가 있을 때만 비교한다.
- Wafer Map 은 X 오른쪽 · Y 위쪽으로 그리고, Defect 좌표의 (0,0) 을 직사각형 좌측 하단으로 본다(소유자 설명). wafer 원은 직사각형에 내접한다고 보았다(확인 전).
- (#52) Die 좌표는 소유자 확정(좌측 하단 (0,0), 오른쪽 · 위쪽 증가). wafer 중심 = 완전한 Die 들의 좌측 하단이 (0,0) 이 되는 위치(내 해석, 확인 전 — 예시 맵에서는 맵 격자 가운데와 같다). 첫 수정(Defect 분포로 중심 자동 맞춤)은 소유자가 아니라고 해서 되돌렸다.
- (#53) 실제 결과 폴더 확인: Surface.flt.md 는 형식을 `Vartype` 숫자(2 int16 · 3 int32 · 4 float32 · 5 float64 · 17 uint8)로 적는다 → 읽게 고침. Surface.flt 의 `id` 는 전부 1 → 표의 ID 는 기록 순서(0부터, Color `Index` 와 같음). ScanLog.ini `SurfaceDefects=` 로 Defect 수 교차 검증. Gray 프레임 좌표(ScanResultImageList) = s_FrameData WaferPos = 프레임 가운데(frameToChuckPlane offset −1219.4, −394.2 = 3168×1024 의 절반 × 0.7698), 353개 Defect 모두 프레임 안 — 사진이 없어 Crop 화면은 확인 못 함.
