Build-time destination only. Never commit executables here.
Windows onedir Python engine layout:
  sidecar/Camtek_AOI_engine.exe
  sidecar/_internal/... (PyInstaller runtime dependencies)
The native launcher never uses Python from PATH or a user-supplied command.
Without the packaged engine, the UI reports engine_not_packaged.
