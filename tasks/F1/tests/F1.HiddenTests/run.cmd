@echo off
dotnet test F1.HiddenTests\F1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false %*
exit /b %ERRORLEVEL%
