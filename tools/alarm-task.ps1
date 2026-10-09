# alarm-task.ps1 - the scheduled alarm wrapper (W1-K 6.3, W0 rev 6.11 section 13, R6.9b).
# Runs under powershell.exe 5.1. Runs `bench status <run_id> --alarm-after <s> --json` as an external command:
# exit 0 no alarm; exit 6 an alarm (bench-status/1 on stdout, read: alarm.code, alarm.cause, alarm.age_s);
# any other non-zero exit is the payload code check-error. POSTs to ntfy on the edge, keeps the edge state file
# and the delivery log. The topic is a bearer secret: it is never printed, logged or put in the payload.
[CmdletBinding()]
param(
    [string]$RunId = '',
    [Parameter(Mandatory = $true)][int]$AlarmAfter,
    [string]$Bench = 'bench',
    [string]$RunsRoot = 'runs',
    [string]$Now = '',
    [switch]$DryRun,
    [string]$RestStub = '',
    [switch]$Drill,
    [string]$TaskName = '',
    [switch]$Toast
)

$ErrorActionPreference = 'Stop'
$ResendAfterS = 3600

function Show-DrillToast {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>Harness benchmark alarm drill</text><text>Check your phone and acknowledge the run id there.</text></binding></visual></toast>')
    $notification = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Microsoft.Windows.PowerShell').Show($notification)
}

if ($DryRun) {
    # The network is unreachable by construction under -DryRun: a local function shadows the cmdlet.
    function Invoke-RestMethod { param($Uri, $Method, $Body) }
    function Show-DrillToast { }
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

if ($Drill) {
    if (-not $TaskName.Trim() -or $TaskName -match "[\r\n]") {
        [Console]::Error.WriteLine('drill task name is missing or invalid')
        exit 2
    }
    # The existing task is configured once for this runs root. Select the newest seed for its task.
    # No run id is printed by start; it reaches the operator inside the push only.
    $seeds = @()
    if (Test-Path -LiteralPath $RunsRoot) {
        foreach ($folder in (Get-ChildItem -LiteralPath $RunsRoot -Directory -Filter 'drill-*')) {
            try {
                $seed = Get-Content -LiteralPath (Join-Path $folder.FullName 'drill-seed.json') -Raw | ConvertFrom-Json
                if ($seed.run_id -eq $folder.Name -and $seed.run_id -match '^drill-[0-9a-f]{8}$' -and $seed.task -eq $TaskName) {
                    $seeds += $seed
                }
            } catch { } # An incomplete seed is not an alarm target.
        }
    }
    if ($seeds.Count -eq 0) {
        [Console]::Error.WriteLine('no seeded drill for this scheduled task and runs root')
        exit 2
    }
    $selected = $seeds | Sort-Object seeded_at, run_id | Select-Object -Last 1
    $RunId = $selected.run_id
    # UTC records have second precision: an immediate push must land in a later measured second.
    # One bounded wait on the real clock; an injected clock or a clock that moved back fails closed.
    if ($stamp -le $selected.seeded_at) {
        if (-not $Now) {
            $seedTime = [datetime]::Parse($selected.seeded_at, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
            $waitMs = [Math]::Min(1000, [Math]::Max(1, [Math]::Ceiling(($seedTime.AddSeconds(1) - $clock).TotalMilliseconds)))
            Start-Sleep -Milliseconds $waitMs
            $clock = (Get-Date).ToUniversalTime()
            $stamp = $clock.ToString('yyyy-MM-ddTHH:mm:ssZ')
        }
        if ($stamp -le $selected.seeded_at) {
            [Console]::Error.WriteLine('drill delivery must be after the seed time; retry the scheduled task')
            exit 2
        }
    }
}
if (-not $RunId) {
    [Console]::Error.WriteLine('run id is required outside drill mode')
    exit 2
}

$runDir = Join-Path $RunsRoot $RunId
New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$edgePath = Join-Path $runDir '.alarm_edge'
$logPath = Join-Path $runDir 'alarm-delivery.log'

# Stderr (the HB-ALM-00x line the real command prints on exit 6) must not become a terminating NativeCommandError in 5.1:
# 'Continue' for this one native call only; the exit code is read right after, and every other statement stays 'Stop'.
$ErrorActionPreference = 'Continue'
$out = & $Bench --runs $RunsRoot status $RunId --alarm-after $AlarmAfter --json 2>$null
$exit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

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
if ($Drill -and $Toast -and $body -and $result -eq 'push ok') {
    try { Show-DrillToast } catch { Write-Output 'optional drill toast unavailable' }
}
$evidence = if ($Drill -and $code) { " code=$code task=$TaskName" } else { '' }
Add-Content -Path $logPath -Value "$stamp exit=$exit $result$evidence" -Encoding Ascii
exit $exit
