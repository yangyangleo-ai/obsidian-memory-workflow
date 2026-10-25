[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('daily','weekly','monthly','manual')][string]$Job,
    [Parameter(Mandatory)][string]$LockRoot,
    [string]$Owner = ('workflow-' + $PID),
    [ValidateRange(0,3600)][int]$WaitTimeoutSeconds = 0,
    [string]$AnchorUtc = ([DateTimeOffset]::UtcNow.ToString('o')),
    [string]$TimeZoneId = 'Asia/Shanghai',
    [switch]$ContextOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'The guard support baseline is Windows with PowerShell 7.' }
if ($AnchorUtc -notmatch '(Z|[+-]\d{2}:\d{2})$') { throw 'AnchorUtc requires an explicit offset.' }
$instant = [DateTimeOffset]::Parse($AnchorUtc, [Globalization.CultureInfo]::InvariantCulture)
try { $zone = [TimeZoneInfo]::FindSystemTimeZoneById($TimeZoneId) }
catch {
    if ($TimeZoneId -eq 'Asia/Shanghai') { $zone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time') }
    else { throw }
}
$local = [TimeZoneInfo]::ConvertTime($instant, $zone)
$day = $local.Date
$cycle = $local.ToString('yyyy-MM-dd')
$period = $cycle
if ($Job -eq 'weekly') {
    $cycle = '{0}-W{1:00}' -f [Globalization.ISOWeek]::GetYear($day), [Globalization.ISOWeek]::GetWeekOfYear($day)
    $weekStart = $day.AddDays(-(([int]$day.DayOfWeek + 6) % 7))
    $period = $weekStart.ToString('yyyy-MM-dd') + '/' + $weekStart.AddDays(6).ToString('yyyy-MM-dd')
}
if ($Job -eq 'monthly') {
    $cycle = $local.ToString('yyyy-MM')
    $period = [datetime]::new($day.Year,$day.Month,1).AddMonths(-1).ToString('yyyy-MM')
}
$context = [ordered]@{ job=$Job; cycle=$cycle; review_period=$period; timezone=$TimeZoneId; anchor_at_utc=$instant.ToUniversalTime().ToString('o'); actual_triggered_at_utc=$null }
if ($ContextOnly) { $context | ConvertTo-Json -Compress; exit 0 }
$root = [IO.Path]::GetFullPath($LockRoot).TrimEnd('\')
if (-not [IO.Directory]::Exists($root)) { throw 'LockRoot must already exist and be independently reviewed.' }
if ($root -eq [IO.Path]::GetPathRoot($root).TrimEnd('\') -or $root -eq [Environment]::GetFolderPath('UserProfile')) { throw 'Refusing a broad lock directory.' }
function Open-Exclusive([string]$Path) {
    try { return [IO.File]::Open($Path,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
    catch [IO.IOException] {
        if (($_.Exception.HResult -band 0xffff) -in @(32,33)) { return $null }
        throw
    }
}
function Emit([string]$Event,$Value) {
    [Console]::Out.WriteLine($Event+' '+($Value|ConvertTo-Json -Depth 5 -Compress))
    [Console]::Out.Flush()
}
$jobStream=$null
$globalStream=$null
$watch=[Diagnostics.Stopwatch]::StartNew()
$requested=[DateTimeOffset]::UtcNow.ToString('o')
try {
    $jobStream=Open-Exclusive (Join-Path $root ('vault-job-'+$Job+'.guard'))
    if ($null -eq $jobStream) { Emit 'JOB_ALREADY_RUNNING' @{job=$Job;owner=$Owner}; exit 73 }
    $announced=$false
    while ($null -eq $globalStream) {
        $globalStream=Open-Exclusive (Join-Path $root 'vault-job.guard')
        if ($null -ne $globalStream) { break }
        if ($WaitTimeoutSeconds -eq 0) { Emit 'JOB_BUSY' @{job=$Job;owner=$Owner}; exit 75 }
        if (-not $announced) { Emit 'JOB_WAITING' @{job=$Job;owner=$Owner;requested_at_utc=$requested}; $announced=$true }
        if ($watch.Elapsed.TotalSeconds -ge $WaitTimeoutSeconds) { Emit 'JOB_WAIT_TIMEOUT' @{job=$Job;owner=$Owner}; exit 74 }
        Start-Sleep -Milliseconds 100
    }
    $record=[ordered]@{job=$Job;owner=$Owner;process_id=$PID;requested_at_utc=$requested;acquired_at_utc=[DateTimeOffset]::UtcNow.ToString('o');wait_seconds=[math]::Round($watch.Elapsed.TotalSeconds,3);context=$context}
    Emit 'JOB_ACQUIRED' $record
    while ($true) {
        $line=[Console]::ReadLine()
        if ($null -eq $line -or $line.Trim() -eq 'release') { break }
        if ($line.Trim() -eq 'status') { Emit 'JOB_HELD' $record }
    }
}
finally {
    if ($null -ne $globalStream) { $globalStream.Dispose(); Emit 'JOB_RELEASED' @{job=$Job;owner=$Owner;guard_files_retained=$true} }
    if ($null -ne $jobStream) { $jobStream.Dispose() }
}
