# Camtek AOI Wafer Map v1.0.0

Camtek AOI Manager 의 **특수 버전**입니다. 본 프로그램과 같은 구조(Tauri 실행 파일 + 변환 엔진 sidecar)에서
**Wafer Map 변환 기능만** 따로 묶었습니다. 다른 기능(Recipe · Batch Report · Commonality · 자동 감시 · Color·Gray 매칭 · 자동 업데이트)의
코드는 패키지에 들어 있지 않습니다.

## 들어 있는 것
- **TXT → Excel**: Wafer Map TXT 를 색칠된 맵(`_Map_Edit.xlsx`)으로 펼쳐 Bin Code die 를 고칩니다. 맵 이미지 2장(Bin Code / Bin Meaning PNG)도 만듭니다.
- **Excel → TXT**: 고친 Excel 을 원본 형식 그대로 TXT(`_Converted.txt`)로 되돌립니다. 손대지 않은 맵은 원본과 바이트까지 같습니다.
- 헤더 수정(`Header_Edit` 시트, 수정 값을 채운 항목만) · 하위 폴더까지 찾기 · 결과 위치(원본 옆 / 다른 폴더) · 결과 열기.

## 설치
1. `Camtek_AOI_WaferMap_v1.0.0.zip` 을 받아 **속성 › 차단 해제**(보이면) 후, `C:\AOI_Tools\Camtek_AOI_WaferMap\` 같은 **고정 로컬 폴더**에 풉니다
   (다운로드 · 바탕화면 · OneDrive 에서 바로 실행하지 마세요).
2. `Camtek_AOI_WaferMap.exe` 실행. `sidecar\` 폴더는 그대로 두세요. 자세한 내용은 압축 안의 `사용법.md`.

## 보안
- 원본 읽기 전용 · 인터넷 미사용 · 네트워크 포트 없음 · **자동 업데이트 없음** · 관리자 권한 불필요.
- 엔진 = `sidecar\Camtek_AOI_WaferMap_engine.exe`(별도 `pythonw.exe` 실행 없음). 파일별 SHA-256 = 압축 안 `SHA256SUMS.txt`.
- 본 프로그램(Camtek AOI Manager)과 동시에 실행할 수 있습니다(이름 · 식별자 · 중복 실행 확인이 따로).
