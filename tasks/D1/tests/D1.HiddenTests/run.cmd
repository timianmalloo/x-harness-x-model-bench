@echo off
set "USERPROFILE=C:\Users\malla"
set "HOME=%USERPROFILE%"
set "HOMEDRIVE=C:"
set "HOMEPATH=\Users\malla"
set "APPDATA=%USERPROFILE%\AppData\Roaming"
set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "NUGET_PACKAGES=%USERPROFILE%\.nuget\packages"
set "ALLUSERSPROFILE=C:\ProgramData"
set "PROGRAMDATA=C:\ProgramData"
set "PROGRAMFILES=C:\Program Files"
set "PROGRAMFILES(X86)=C:\Program Files (x86)"
set "PROGRAMW6432=C:\Program Files"
set "COMMONPROGRAMFILES=C:\Program Files\Common Files"
set "COMMONPROGRAMFILES(X86)=C:\Program Files (x86)\Common Files"
set "COMMONPROGRAMW6432=C:\Program Files\Common Files"
dotnet test D1.HiddenTests\D1.HiddenTests.csproj -p:RestoreSources=. -p:RestorePackagesPath=%USERPROFILE%\.nuget\packages -p:NuGetAudit=false %*
exit /b %ERRORLEVEL%
