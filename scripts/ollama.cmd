@echo off
REM Wrapper so Ollama works even when Cursor terminals have a stale PATH.
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA_EXE%" (
  echo Ollama not found at "%OLLAMA_EXE%"
  echo Install with: winget install Ollama.Ollama
  exit /b 1
)
"%OLLAMA_EXE%" %*
