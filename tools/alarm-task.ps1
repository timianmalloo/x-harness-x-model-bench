# alarm-task.ps1 - the scheduled alarm wrapper (W1-K 6.3, W0 rev 6.11 section 13, R6.9b).
# Runs under powershell.exe 5.1. Runs `bench status <run_id> --alarm-after <s> --json` as an external command.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][int]$AlarmAfter,
    [string]$Bench = 'bench',
    [string]$RunsRoot = 'runs',
    [string]$Now = '',
    [switch]$DryRun,
    [string]$RestStub = ''
)

$ErrorActionPreference = 'Stop'

if ($DryRun) {
    # The network is unreachable by construction under -DryRun: a local function shadows the cmdlet.
    function Invoke-RestMethod { param($Uri, $Method, $Body) }
    if ($RestStub) { . $RestStub }
}

$topic = $env:HB_ALARM_NTFY_TOPIC
$base = if ($env:HB_ALARM_NTFY_URL) { $env:HB_ALARM_NTFY_URL.TrimEnd('/') } else { 'https://ntfy.sh' }

$out = & $Bench status $RunId --alarm-after $AlarmAfter --json 2>$null
$exit = $LASTEXITCODE

if ($exit -eq 0) { exit 0 }

if ($exit -eq 6) {
    $alarm = ($out -join "`n" | ConvertFrom-Json).alarm
    $code = [string]$alarm.code
    $cause = [string]$alarm.cause
    $age = [string]$alarm.age_s
} else {
    $code = 'check-error'
    $cause = "bench status exited $exit"
    $age = ''
}

$body = "run $RunId $code ${cause}: age ${age}s"
Invoke-RestMethod -Uri "$base/$topic" -Method Post -Body $body
exit $exit
