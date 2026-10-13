@echo off
setlocal
cd /d "%~dp0"
where dotnet >nul 2>&1
if errorlevel 1 (
  echo ERROR: Install .NET 10 SDK: https://dotnet.microsoft.com/download/dotnet/10.0
  exit /b 1
)
echo Building dshot for Windows x64...
dotnet restore "src\dshot\dshot.csproj"
if errorlevel 1 exit /b 1
dotnet publish "src\dshot\dshot.csproj" -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:DebugType=none -o release
if errorlevel 1 (
  echo ERROR: Build failed. See the errors above.
  exit /b 1
)
if not exist "release\dshot.exe" (
  echo ERROR: Published executable was not found.
  exit /b 1
)
echo.
echo SUCCESS: %CD%\release\dshot.exe
echo If release contains other files, keep them next to the EXE.
exit /b 0
