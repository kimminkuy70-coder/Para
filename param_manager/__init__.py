"""PI_ALL 장비 파라미터 관리 프로그램.

엑셀(.xlsm) + VBA 로 운영하던 Camtek AOI 장비 PI 코어 파라미터 관리를
오프라인 데스크톱 프로그램으로 옮긴 패키지입니다.

- engine : 엑셀 입출력 / Row_ID / 변경이력 / 호기별 요약 / 비교 / 병합 저장 / 편집 잠금
- app    : tkinter GUI

외부 패키지는 openpyxl(MIT) 하나만 사용하며, 실행 중 네트워크 접속이 없습니다.
"""

__version__ = "1.0.0"
