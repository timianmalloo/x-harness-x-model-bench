# alarm-task.ps1 - the scheduled alarm wrapper (W1-K 6.3, W0 rev 6.11 section 13, R6.9b).
# Runs under powershell.exe 5.1. Runs `bench status <run_id> --alarm-after <s> --json` as an external command:
# exit 0 no alarm; exit 6 an alarm (bench-status/1 on stdout, read: alarm.code, alarm.cause, alarm.age_s);
# any other non-zero exit is the payload code check-error. POSTs to ntfy on the edge, keeps the edge state file
# and the delivery log. The topic is a bearer secret: it is never printed, logged or put in the payload.
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
$ResendAfterS = 3600

if ($DryRun) {
    # The network is unreachable by construction under -DryRun: a local function shadows the cmdlet.
    function Invoke-RestMethod { param($Uri, $Method, $Body) }
    if ($RestStub) { . $RestStub }
}

$topic = $env:HB_ALARM_NTFY_TOPIC
if (-not $topic) {
    [Console]::Error.WriteLine('alarm channel not configured: set HB_ALARM_NTFY_TOPIC (runbook)')
    exit 2
}
$base = if ($env:HB_ALARM_NTFY_URL) { $env:HB_ALARM_NTFY_URL.TrimEnd('/') } else { 'https://ntfy.sh' }

# The injected clock: -Now (ISO 8601) in tests, the wall clock otherwise.
$clock = if ($Now) { [datetime]::Parse($Now, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime() } else { (Get-Date).ToUniversalTime() }
$stamp = $clock.ToString('yyyy-MM-ddTHH:mm:ssZ')

$runDir = Join-Path $RunsRoot $RunId
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$edgePath = Join-Path $runDir '.alarm_edge'
$logPath = Join-Path $runDir 'alarm-delivery.log'

$out = & $Bench status $RunId --alarm-after $AlarmAfter --json 2>$null
$exit = $LASTEXITCODE

$state = $null
if (Test-Path $edgePath) { $state = Get-Content -Raw -Path $edgePath | ConvertFrom-Json }

$code = $null
$body = $null
if ($exit -eq 0) {
    if ($state) { $body = "run $RunId recovered" }
} else {
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
    $new = (-not $state) -or ($state.code -ne $code)
    $due = $false
    if ($state -and -not $new) {
        $last = [datetime]::Parse($state.last_sent_at, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
        $due = (($clock - $last).TotalSeconds -ge $ResendAfterS)
    }
    $ageText = if ($age) { ": age ${age}s" } else { '' }
    if ($new -or $due) { $body = "run $RunId $code ${cause}${ageText}" }
}

$result = 'no push'
if ($body) {
    try {
        Invoke-RestMethod -Uri "$base/$topic" -Method Post -Body $body | Out-Null
        $result = 'push ok'
        if ($code) {
            $first = if ($state -and ($state.code -eq $code)) { $state.first_sent_at } else { $stamp }
            @{ code = $code; first_sent_at = $first; last_sent_at = $stamp } | ConvertTo-Json -Compress |
                Set-Content -Path $edgePath -Encoding Ascii
        } else {
            Remove-Item -Force -Path $edgePath
        }
    } catch {
        # Fixed text only: never $_, its message or TargetObject (a failed POST carries the full URI in 5.1).
        $result = 'push failed: ' + $_.Exception.GetType().Name
        Write-Output $result
    }
}
Add-Content -Path $logPath -Value "$stamp exit=$exit $result" -Encoding Ascii
exit $exit
