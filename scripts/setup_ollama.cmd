@echo off
REM Pull the default clinical-parser model and ensure the Ollama app can serve it.
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not exist "%OLLAMA_EXE%" (
  echo Ollama not found at "%OLLAMA_EXE%"
  exit /b 1
)
echo Using: %OLLAMA_EXE%
"%OLLAMA_EXE%" --version
echo.
echo Pulling llama3.2 (one-time download)...
"%OLLAMA_EXE%" pull llama3.2
echo.
echo Done. Start the Ollama app from the Start menu if it is not already running,
echo or run: scripts\ollama.cmd serve
