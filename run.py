"""PyInstaller 엔트리포인트 (.exe 빌드용).

개발 중에는 `python -m param_manager` 또는 `python run.py` 로 실행할 수 있습니다.
"""
from param_manager.app import main

if __name__ == "__main__":
    main()
