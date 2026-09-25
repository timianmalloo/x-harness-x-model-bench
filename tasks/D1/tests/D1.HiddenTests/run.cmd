@echo off
dotnet test D1.HiddenTests\D1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false %*
exit /b %ERRORLEVEL%
