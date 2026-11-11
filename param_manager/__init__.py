"""PI_ALL 장비 파라미터 관리 프로그램.

엑셀(.xlsm) + VBA 로 운영하던 Camtek AOI 장비 PI 코어 파라미터 관리를
오프라인 데스크톱 프로그램으로 옮긴 패키지입니다.

- engine : 엑셀 입출력 / Row_ID / 변경이력 / 호기별 요약 / 비교 / 병합 저장 / 편집 잠금
- 화면   : frontend/dist (Edge 앱 창, 127.0.0.1 로컬 서버)

외부 패키지는 openpyxl(MIT) 하나(vendor/)뿐. 인터넷 접속은 업데이트 확인 · 받기(github.com 이 저장소) 때만.
"""

# v13: 릴리스 태그 v13.x.y 와 같아야 한다(CI 가 확인, 업데이트가 태그 zip 의 이 값을 대조).
__version__ = "13.0.2"
