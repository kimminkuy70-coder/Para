# TB500 Review (`TB500_Review.html`) — 사용법 · 판정 규칙 · 보안 검토

- 브랜치 `version_TB500_review`, 이슈 Para #40. 원본 `TB500_Lot_Folder_List_ImageName_Equipment.html` 은 고치지 않았다.
- 외부 라이브러리 · 인터넷 접속 없음. Microsoft Edge(또는 Chrome)에서 파일을 더블클릭해 연다.

## 0. 화면 구성 (Para #42 후속, 2026-11-07)
- 맨 위 탭 2개: **[설정]**(첫 탭 — 폴더 연결 3개 · 캐시 상태 · [캐시 갱신]) / **[조회]**(Lot 목록 · 조회 결과).
- HTML 을 열 때 폴더 3개가 모두 연결되어 있고 캐시도 받았으면 [조회] 탭을, 아니면 [설정] 탭을 엽니다. 설정을 마치지 않았으면 [설정] 탭에 빨간 점이 붙습니다.
- 색은 Camtek AOI Manager 와 같은 계열입니다(머리 = slate navy `#37474f`, 강조 = 초록 `#047857`). 장비(KLA 파랑 · Camtek 초록) · Layer · 호기 색은 자료 구분용이라 그대로 둡니다.
- Lot History ③ wafer 판정의 **슬롯별 표는 접혀 있는 것이 기본**입니다. 제목 줄(Lot 상태 · 판정 개수)을 누르면 펼칩니다.

## 1. 처음 설정 (1회)
1. 개발자가 공유한 OneDrive 폴더를 [내 파일에 바로 가기 추가]로 연결하십시오.
2. [설정] 탭의 ① [폴더 연결]을 누르고 동기화된 `캐시공유` 폴더를 고르십시오.
   (예: `C:\Users\(사번)\OneDrive - Amkor Technology\0. Camtek AOI parameter 취합\캐시공유`)
3. ② [폴더 연결]을 누르고 Conder Scan 폴더(Lot 폴더들이 바로 아래에 있는 폴더)를 고르십시오. 표시 경로 칸에 UNC 경로를 적으십시오(경로 복사용).
4. ③ [폴더 연결]을 누르고 내 PC 캐시 폴더(예: 문서 아래 새 폴더 `TB500리뷰캐시`)를 고르십시오.
5. [캐시 갱신]을 누르십시오.
- 연결한 폴더는 브라우저가 기억합니다. 브라우저 보안 때문에, HTML 을 다시 열면 폴더를 처음 쓸 때 [허용]을 한 번 눌러야 합니다.

## 2. 매일 쓰는 법
1. HTML 을 여십시오. 캐시를 받은 지 24시간이 지났으면 맨 위에 빨간 알림이 나옵니다. 알림은 내 PC 기록만 보고 띄웁니다(OneDrive 에 접속하지 않음).
2. 알림이 있으면 [설정] 탭의 [캐시 갱신]을 누르십시오.
3. [조회] 탭에서 Lot 목록을 붙여 넣고 [조회]를 누르십시오.

## 3. 판정 규칙 (소유자 답변 2026-11-06 댓글 6691832497)
- Lot 폴더 = Conder Scan 바로 아래에서 Lot 이름이 들어 있는 폴더(예 `976. TB500.INT1041 (CMS)`). 괄호 안 = S/M.
- Layer = 폴더 이름(괄호 앞)에서 가장 앞에 나오는 Layer 표기(RDL4 · PIDS3(PI4) · RDL3 · PIDS5(PI3) · RDL2 · PIDS7(PI2) · RDL1 · FS UBM).
  예 `4. PIDS5_Skip (RDL3 재리뷰 결과 …)` = PIDS5 (괄호 안 RDL3 는 보지 않음).
- 폴더 종류(괄호 앞 이름): `재리뷰` 포함 = 재리뷰 폴더, `Skip` = Skip, `재스캔` = 재스캔, 그 밖 = 기본 폴더.
- **재리뷰 완료** = 같은 Layer 에 `_재리뷰` 폴더가 있다. 그 폴더 안 맵(.txt) 수를 세고 경로를 보여 준다(파일 5천 개 또는 2.5초가 넘으면 세지 않고 경로만). 호기 · 스캔 시각은 조사하지 않는다.
- **재리뷰 필요** = Layer 폴더(기본 · 재스캔)는 있는데 `_재리뷰` 폴더가 없다 → 장비 · 호기 · 스캔 시각을 캐시에서 찾는다.
- **Skip** = `_재리뷰` 폴더는 없고 `Skip` 폴더가 있다 → 조사하지 않는다 (내 해석, 확인 전).
- 장비 = Layer 폴더 안 이미지 파일 이름(원본 HTML 규칙: `TB500_…` 또는 ` - Multi_` = Camtek, `영문숫자_숫자×4 이상` = KLA). 모르면 두 캐시를 다 본다.
- Camtek 호기 = Batch Report 캐시에서 **S/M 코드**(S/M 안 첫 단독 영문 3글자, 예 `CMS`)가 같고 **Job 이름**(`Job/Setup` 의 Job, 예 `TB500_RDL3-Multi`)에 그 Layer 가 있는 Batch Report 의 호기 · Batch Start.
- KLA 호기 = KLA 캐시에서 Lot 폴더 이름이 `{Lot}@{공정번호}` 이고 공정번호가 그 Layer 의 AOI · Review 공정(예 RDL1 = 6316 · 6326)인 것의 장비 · 첫 슬롯 스캔 시각.
- 한 Layer 를 여러 호기에서 스캔했으면 `여러 호기 n대` 표시.

### 결과 표 (Para #41, 2026-11-06)
- **한 줄 = Lot 폴더 안의 실제 하위 폴더 하나**(이름 그대로, 이름순). Layer 를 모르는 폴더(예 `메모`)도 줄로 나오고 나머지 칸은 빈칸.
- 칸: 하위 폴더(재스캔 · 재리뷰 · Skip 표시) · Layer · 공정번호(AOI · Review) · 재리뷰 · 장비 · 호기 · 스캔 시각 · [경로 복사].
- 재리뷰 칸: `_재리뷰` 폴더 줄 = `재리뷰 결과` + 맵(.txt) 수 · 기본/재스캔 폴더 줄 = 같은 Layer 에 `_재리뷰` 폴더가 있으면 `재리뷰 완료`, 없으면 `재리뷰 필요`(빨간 줄) · Skip 폴더 줄 = `Skip`.
- 장비 · 호기 · 스캔 시각은 `재리뷰 필요` 줄에만 쓴다. 다른 줄은 빈칸(종전 "조사하지 않음" 문구 삭제 — 소유자 지시).
  장비는 그 폴더 안 이미지 이름으로 폴더마다 판정한다.
- **Lot History**(Lot 칸 또는 `재리뷰 필요` 줄의 버튼): Camtek AOI Manager 의 Lot History 와 같은 꼴 —
  Layer 고르기 칩(줄에서 열면 그 Layer) · 숫자 4개(스캔 · 호기 · 호기 이동 · 기간) · ① 시간순 요약(스캔마다 한 칸: Layer · 호기 · 장비 · 시각, 칸 사이 = 간격 · 호기 이동)
  · ② 시간순 기록(앞 기록과의 간격, Layer 바뀜, 호기 이동 A → B). 호기 색은 창 안에서 같다.
- **Camtek Pass/Fail 판정**(Para #42, 소유자 지시 2026-11-06 "기존 AOI 프로그램처럼 Pass/Fail 따져서 기록"): Camtek AOI Manager(`param_manager/lotmodel.py`)와 같은 규칙이다.
  - wafer 행 종류: Pass / Error(빈칸 포함, 앞 Error 뒤의 Aborted · Skipped 도 Error) / 작업자 중단(앞에 Error 없는 `Aborted.` 와 그 뒤) / 스캔 안 한 슬롯(앞에 Error · 중단 없는 `Skipped.` — wafer 로 세지 않음).
  - Batch Report 결과: `정상`(청록) · `Error`(주황, Pass 가 0장이면 빨강) · `작업자 중단`(노랑) + `Pass n · Error n · 중단 n · 스캔 안 한 슬롯 n`.
  - Layer 의 wafer 판정: 그 Layer 의 Camtek Batch Report 를 시간순으로 모아 슬롯마다 `한 번에 Pass` / `재스캔 Pass`(Error · 중단 뒤 Pass) / `중복 Pass`(Pass 2번 이상) / `Pass 없음`.
    Lot 상태 = `Pass하지 못한 wafer 존재`(빨강) · `재스캔으로 완료`(주황) · `한 번에 완료`(청록). 2D · 3D 스캔(S/M 에 단독 `3D`)은 따로 센다.
  - 슬롯 = 25행 표면 행 위치(1행 = 25번), 아니면 Wafer ID(`Slot 14` · `14` · `SF14G14-A0`).
  - 나오는 곳: 결과 표의 호기 칸(Lot 상태 한 줄 + Batch Report 마다 결과), Lot History ① 요약 그림(`22P 3E`) · ② 기록 · ③ wafer 판정 표(행 = 슬롯, 열 = 스캔, 끝 = 판정), CSV(`Camtek Batch Report Result`, `Camtek Layer Wafer Verdict`).
- **Batch Report 보기**(Para #42): Lot History ② 기록의 Camtek Batch Report 파일 이름을 누르면, 캐시에 든 머리 정보(Batch Start · Job/Setup · Wafers Scanned …)와 wafer 표(슬롯 · Wafer ID · Pass/Fail · Scanned/Bad/Good Dice · Faults · Yield · Recipe(s) — 원문 열 그대로)를 Batch Report 꼴로 보여 준다. 원본 파일을 여는 것이 아니다.
- 내 PC 색인은 schema 4(행 [9] = wafer 판정 칸, [10] = 머리 정보 · wafer 표). 예전(schema 1~3) 색인이면 같은 zip 이어도 [캐시 갱신]이 다시 푼다. 그 전에는 회색 `[캐시 갱신] 필요` 로 보인다.

## 4. 내 PC 캐시 폴더에 생기는 파일
- `TB500리뷰_Camtek색인_YYYYMMDD_HHMMSS.json` · `TB500리뷰_KLA색인_YYYYMMDD_HHMMSS.json`(zip 에서 푼 검색용 자료) · `TB500리뷰_기록.json`(받은 시각 · zip 이름).
- 최신 1개만 남긴다: [캐시 갱신]이 끝나면 이름이 정확히 위 규칙에 맞는 지난 색인 파일만 지운다. 다른 파일은 건드리지 않는다.
- zip 은 내 PC 에 복사하지 않는다. 동기화된 OneDrive 파일을 읽어 크기 · SHA-256 을 확인한 뒤 안의 JSON 만 읽는다.

## 5. Windows Defender 검토 (소유자 요청: HTML 이 자동으로 지워도 위협으로 잡히지 않는지)
결론: **위협으로 잡힐 가능성은 낮다**(실제 회사 PC 확인 전). 근거:
- 쓰기 · 지우기를 하는 주체는 Microsoft Edge 브라우저 자체(msedge.exe, 서명된 프로그램)다. 새 실행 파일 · 스크립트 파일(.bat · .ps1 · .vbs · .exe)을 만들거나 실행하지 않는다.
  예전 사고 유형(미서명 exe 의 net use 로그온, .bat 자기 교체, 인터넷에서 받은 exe)과 겹치지 않는다.
- 브라우저 File System Access API 는 사용자가 직접 고르고 [허용]한 폴더 안에서만 동작한다. 다른 폴더에는 접근할 수 없다.
- 지우는 것은 한 번에 1~2개의 JSON 파일이다. Defender 의 랜섬웨어류 행위 탐지(많은 사용자 파일을 짧은 시간에 고치거나 지우기)와 규모 · 형태가 다르다.
- 만드는 파일은 JSON(텍스트)뿐이다. 브라우저는 쓰는 동안 같은 폴더에 `.crswap` 임시 파일을 만들었다가 이름을 바꾼다(정상 동작).
- 인터넷 접속 · 자격 증명 사용이 없다. OneDrive · Conder Scan 에는 쓰지 않는다(읽기 권한으로만 연결).
- 남는 위험: 회사 보안 정책이 브라우저의 로컬 폴더 쓰기(File System Access API)를 막을 수 있다. 그때는 [캐시 갱신]이 '폴더 접근을 허용해야…'로 실패한다 — 실제 PC 에서 한 번 확인 필요.

## 6. 시험
- `node tools/test_tb500_review.mjs`(PARA_TEST_NODE_MODULES = playwright 가 있는 node_modules): 합성 자료(`tools/tb500_review_fixture.py`, 소유자 예시 폴더 이름)로
  SHA-256(= Node crypto) · 판정 규칙 · 캐시 갱신 · 최신 1개 보관 · 다른 파일 보존 · 원본 무쓰기 · 여러 호기 · Lot History · 24시간 알림을 확인한다.
- 실제 Para v12.9.23 코드가 게시한 zip(Camtek · KLA)으로도 한 번 확인함(시험 코드는 저장소에 넣지 않음).
- 확인 못 한 것: 실제 Edge · 회사 OneDrive · UNC Conder Scan · 큰 캐시(수백 MB) 속도 · Defender 실제 반응.
