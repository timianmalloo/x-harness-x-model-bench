@echo off
dotnet test D3.HiddenTests\D3.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false %*
exit /b %ERRORLEVEL%
