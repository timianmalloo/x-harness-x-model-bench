@echo off
dotnet test tests/E6.Tests.csproj -p:RestoreSources=. -p:NuGetAudit=false %*
exit /b %ERRORLEVEL%
