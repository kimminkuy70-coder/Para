# Wafer Map 변환 v1.0.0

Wafer Map TXT 를 Excel 로 펼쳐 Bin Code 를 고치고, 원본 그대로 다시 TXT 로 되돌리는 프로그램의 첫 배포입니다.

## 기능
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

개발: 김민규
