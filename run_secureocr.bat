@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo SecureOCR Desktop Python 3.11 environment was not found.
  echo Expected: %~dp0.venv\Scripts\pythonw.exe
  pause
  exit /b 1
)
start "SecureOCR Desktop" ".venv\Scripts\pythonw.exe" -m secureocr_desktop
popd

