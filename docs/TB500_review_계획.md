# TB500 리뷰 전용 HTML — 검토와 계획 (Para #40, 소유자 검토 전)

- 작성 2026-11-06 · 브랜치 `version_TB500_review` · 기준 커밋 `cfac6de`(소유자 업로드 `TB500_Lot_Folder_List_ImageName_Equipment.html`)
- 상태: **계획만**. 소유자가 승인하고 아래 7절 질문에 답하면 구현을 시작한다. 코드는 아직 없다.

## 1. 원본 HTML 분석 (`TB500_Lot_Folder_List_ImageName_Equipment.html`, 26.5 KB, 외부 라이브러리 없음)

| 항목 | 지금 동작 |
|---|---|
| 입력 | Lot 목록 붙여넣기(줄바꿈 · 탭 · 쉼표 · 세미콜론 분리, 중복 제거) |
| 경로 | `showDirectoryPicker({mode:'read'})`(Edge/Chrome) 또는 `webkitdirectory` 대체. 경로 이름 · UNC 표시 경로는 `localStorage('tb500-paths')`, **폴더 연결(handle)은 저장 안 함** → 열 때마다 다시 연결 |
| Lot 찾기 | 루트 바로 아래에서 Lot 이름 정확 일치 → 없으면 포함(`976. TB500.INT1041 (CMS)` 같은 폴더) |
| Layer | Lot 폴더 바로 아래 하위 폴더 = Layer. 이름으로 공정 매칭(`processMap`: RDL4 6305/6412, PIDS3·PI4 6311/6321, RDL3 6312/6322, PIDS5·PI3 6313/6323, RDL2 6314/6324, PIDS7·PI2 6315/6325, RDL1 6316/6326, FS UBM 6317/6327 — AOI 공정 / Review 공정) |
| 장비 판정 | Layer 아래 이미지 파일명: `TB500_…` 또는 ` - Multi_` = Camtek, `영문숫자_숫자×4 이상` = KLA. 판정되면 그 Layer 조회 즉시 종료 |
| 결과 | 표(입력 Lot · 실제 폴더명 · Layer 목록 + 공정 배지 + 장비 배지) · 상세 대화상자 · 대표 이미지 새 창 · CSV 저장 |
| 쓰기 | **없음**(원본 폴더 읽기 전용). 호기 · 스캔 시각은 모름 |

UX 개념(새 HTML 에 그대로 씀): 카드 2단 배치, 색 토큰 `:root` + 다크 모드, AOI 공정 보라 · Review 공정 분홍 · KLA 파랑 · Camtek 초록 배지, `READ ONLY` 배지, 오른쪽 아래 `Developer: 김민규`.

## 2. 결론: HTML 로 구현 가능 — 단 두 가지는 HTML 로는 안 된다

가능한 것(브라우저 표준 기능만, 설치 · 외부 라이브러리 · 인터넷 없음):
1. Conder Scan 폴더를 **읽기 전용**으로 열기(지금과 같음). 연결한 폴더는 IndexedDB 에 기억 → 다음부터는 [다시 연결] 클릭 1번(브라우저 보안상 권한 확인 클릭은 없앨 수 없음).
2. 캐시 zip 을 HTML 안에서 풀기: Edge 기본 기능 `DecompressionStream('deflate-raw')` 로 zip 안 JSON 을 읽는다(라이브러리 불필요).
3. 사용자가 고른 **로컬 캐시 폴더**(예 `C:\TB500리뷰캐시`)에만 쓰기(`mode:'readwrite'`): 받은 zip 복사, 풀어 만든 검색 색인 JSON, 마지막 갱신 기록. Conder Scan · OneDrive 에는 쓰지 않는다.
4. 갱신 알림: HTML 을 열 때 **로컬 기록만** 보고(마지막 갱신 시각) 기준(기본 1일)이 지나면 알림. OneDrive 에 접속하지 않으므로 트래픽 없음.
5. Camtek: S/M + Layer 로 캐시에서 호기 · 스캔 시각 찾기. KLA: Lot 이름 + 공정번호로 장비 · 날짜 · 슬롯 찾기(아래 4 · 5절).

HTML 로 안 되는 것:
- **A. OneDrive 링크에서 자동 다운로드**: 브라우저 보안(CORS · 회사 로그인) 때문에 HTML 이 OneDrive 공유 링크에서 파일을 직접 받을 수 없다.
  → 대안(권장 순서):
  ① **OneDrive 동기화 폴더 사용(권장)**: 사용자가 처음 1번 공유 링크를 열어 [내 파일에 바로 가기 추가](이미 저장 폴더에 쓰는 방식, CLAUDE.md 152행) → 탐색기의 `OneDrive - 회사\…\캐시공유` 가 생김 → HTML 에서 그 폴더를 1번 연결.
     이후 HTML 은 로컬 동기화 폴더의 `캐시정보.json` 만 읽어(인터넷 접속 아님) 새 zip 이 있으면 로컬 캐시 폴더로 복사 · 풀기 · 색인. SHA-256 확인(#39 와 같은 원칙)으로 동기화 덜 된 파일은 거부.
  ② 바로 가기를 못 쓰는 PC: HTML 의 [OneDrive 열기] 버튼이 공유 링크를 새 탭으로 열고, 사용자가 zip 을 받아 HTML 에 끌어 넣음 → 같은 처리.
- **B. KLA 자료**: 지금 OneDrive 캐시(#39)는 **Camtek Batch Report 만** 들어 있다. KLA 는 장비 폴더 이름(`{장비}\{날짜}\{Lot}\{시각}_{슬롯}`)을 봐야 하는데 사용자는 장비에 연결하지 않는다.
  → KLA 폴더 이름 색인(장비 · 날짜 · Lot · 슬롯 · 경로 — 이름만, 파일 내용 없음, 작음)을 **개발자 PC 의 데스크톱 프로그램(version_v12)이 같이 게시**해야 한다(7절 질문 2).

## 3. 사용자 첫 설정(목표: 2가지만)
1. OneDrive 캐시 위치 — 링크(HTML 에 상수로 넣음, 7절 질문 1) → 동기화 폴더 연결(또는 zip 끌어 넣기)
2. Conder Scan 경로 연결(기본 표시 경로 = 원본 HTML 의 `\\k5cifsn2\k5tsvdata$\1. Conder Scan\531. NVIDIA INT\129. 4DT-TB500-H-M1`)
- 로컬 캐시 폴더는 처음 1번 고름(없으면 [문서]에 새 폴더 만들기 안내). 이후는 Lot 붙여넣기 → [조회] 만.

## 4. Camtek 찾기 흐름 (Lot 1개 기준)
1. Conder Scan 에서 Lot 폴더 찾기(원본과 같음). 폴더명 괄호 안 = **S/M**(`976. TB500.INT1041 (CMS)` → `CMS`). 괄호가 없으면 "S/M 없음" 표시.
2. Lot 아래 Layer 폴더 목록 + 공정 매칭(원본 `processMap` 그대로).
3. Layer 마다 **재리뷰 여부** 판정(7절 질문 3 — 판정 기준 확인 필요).
4. 재리뷰 안 된 Layer(또는 전부 — 질문 4)는 캐시 색인에서 찾기:
   - 색인 1행 = Batch Report 1장: 파일명 `{Job}_{Setup}_{S/M}_{YY-Mon-DD}_({HH.MM.SS})_BatchReport.htm` 에서 Job · Setup · S/M, `metadata` 의 Batch Start/End, 캐시 파일의 호기(`machine`), 웨이퍼 행의 Lot · Wafer ID · 장수.
   - 조건: S/M 의 Lot 코드(첫 단독 영문 3글자, 프로그램 기존 규칙) = Conder Scan 의 S/M **그리고** Job/Setup/S/M 꼬리 어딘가에 Layer 토큰(예 `RDL3`).
     예 `TB500_RDL3-Multi_Setup1_WGB-RDL3_26-Oct-22_(11.23.53)_BatchReport.html` → S/M `WGB-RDL3` → `WGB` + `RDL3`.
   - 결과: 호기(예 AOI-21) · 스캔 시각(Batch Start, 없으면 파일명 시각) · 장수 · Report 파일명. 여러 건이면 최신순 전부(재스캔 표시).
   - 같은 S/M 이 다른 Lot 에 재사용되는 경우(기존 확인 사례 `BAH`)가 있어, Wafer ID 의 Lot ID 가 입력 Lot 과 맞는지도 표시(맞지 않으면 "다른 Lot 가능" 경고).

## 5. KLA 찾기 흐름
- Layer 가 KLA 로 판정되면(이미지 파일명, 원본 규칙) KLA 색인에서 Lot 이름으로 찾는다: `TB500.INT948@6326_RAW` → Lot `TB500.INT948`, 공정번호 `6326` → `processMap` 으로 Layer(6326 = RDL1 Review 2D/R7).
- 결과: 장비(예 `AOI-K6`) · 날짜 · 슬롯 목록 · 경로(`P:\2026-11-05\TB500.INT948@6326_RAW`) — 이슈에 붙인 KLA 자재 찾기 결과 한 줄과 같은 칸.

## 6. 화면 · 파일 계획
- 새 파일 `TB500_Review.html`(단일 HTML, 외부 라이브러리 없음). **원본 `TB500_Lot_Folder_List_ImageName_Equipment.html` 은 고치지 않는다**.
- 화면: ① 설정 카드(OneDrive 캐시 상태 — 마지막 갱신 시각 · zip 이름 · 호기 수, [캐시 갱신] · [OneDrive 열기], Conder Scan 연결, 로컬 캐시 폴더) ② Lot 입력 카드 ③ 결과 표: 입력 Lot · S/M · Layer · AOI/Review 공정 · 재리뷰 여부 · 장비(KLA/Camtek) · **호기** · **스캔 시각** · 근거(Report 파일명 / KLA 경로) ④ 상세 · 대표 이미지 · CSV(원본 기능 유지).
- 갱신 알림: 맨 위 띠 "캐시가 N일 전 것입니다 — [캐시 갱신]". 기준 일수는 설정에서 바꿈(기본 1일 — 매일 올린다고 하셨음).
- 시험: Linux 에서 합성 Conder Scan 폴더 · 합성 캐시 zip 으로 Playwright(Chromium) 자동 시험 — 실제 UNC · 회사 OneDrive · Edge 실기는 검증 불가.

## 7. 소유자에게 확인할 것 (답을 받아야 구현)
1. **OneDrive 링크**: 저장소 · 인수인계 문서 어디에도 OneDrive 공유 링크가 없다(Claude 는 링크를 모름). HTML 에 넣을 공유 링크(캐시공유 폴더 또는 그 상위 공유 폴더)를 알려 주십시오.
   그리고 사용자가 동기화 폴더(①)와 수동 다운로드(②) 중 어느 쪽을 쓰게 할지(권장 ①, 둘 다 넣기도 가능).
2. **KLA 자료**: KLA 폴더 이름 색인을 개발자 PC 의 데스크톱 프로그램(version_v12)에 "KLA 색인도 같이 게시" 기능으로 추가해도 되는지. (안 되면 KLA 는 "장비 판정"까지만 하고 호기는 비워 둠.)
3. **재리뷰 판정 기준**: Conder Scan 에서 "재리뷰 됨"을 무엇으로 아는지 — 예 ⓐ 그 Layer 폴더가 있으면 재리뷰 됨, ⓑ Layer 폴더 안에 특정 파일(이미지 · txt 맵)이 있으면, ⓒ Review 공정번호(6321~6327, 6412) 폴더가 있으면, ⓓ 기타.
   지금 내 해석(확인 전): **"기대 Layer(8개) 중 Conder Scan 에 폴더가 없는 Layer = 재리뷰 안 됨"** → 그 Layer 를 캐시에서 찾아 호기 표시.
4. 재리뷰 된 Layer 도 호기 · 스캔 시각을 같이 보여 줄지(기본 계획: 보여 주되 회색).
5. Camtek 매칭에서 Layer 토큰을 Job(`TB500_RDL3-Multi`) · S/M 꼬리(`WGB-RDL3`) 중 어디서 보는지 — 계획은 둘 중 하나만 맞아도 인정.
6. 로컬 캐시 폴더 기본 위치(예 `C:\TB500리뷰캐시`)와 캐시 보관 개수(계획: 최신 1개만).
