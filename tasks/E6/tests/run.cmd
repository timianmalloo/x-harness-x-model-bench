@echo off
if "%USERPROFILE%"=="" set "USERPROFILE=%SYSTEMDRIVE%\Users\malla"
if "%APPDATA%"=="" set "APPDATA=%USERPROFILE%\AppData\Roaming"
if "%LOCALAPPDATA%"=="" set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
if "%ProgramFiles%"=="" set "ProgramFiles=%SYSTEMDRIVE%\Program Files"
dotnet test tests/E6.Tests.csproj %*
