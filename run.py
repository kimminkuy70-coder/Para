"""PyInstaller 엔트리포인트 (.exe 빌드용).

개발 중에는 `python -m param_manager` 또는 `python run.py` 로 실행할 수 있습니다.
"""
from param_manager.equip_app import main   # 장비 UI(값 확인/양식 만들기/값 업데이트/이력)

if __name__ == "__main__":
    main()
