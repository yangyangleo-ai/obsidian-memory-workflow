Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $IsWindows) { throw 'Windows guard test only.' }
$repo=Split-Path $PSScriptRoot -Parent
$gate=Join-Path $repo 'scripts/vault-job-gate.ps1'
$writerScript=Join-Path $repo 'scripts/vault-write-guard.ps1'
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('obsidian-workflow-guard-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -ErrorAction Stop | Out-Null
$children=[Collections.Generic.List[Diagnostics.Process]]::new()
$script:assertions=0
function Assert($Condition,[string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:assertions++
}
function Start-Child([string]$File,[string[]]$Parameters) {
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=(Get-Process -Id $PID).Path
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.RedirectStandardInput=$true
    $info.RedirectStandardOutput=$true
    $info.RedirectStandardError=$true
    foreach($arg in @('-NoProfile','-File',$File)+$Parameters){$info.ArgumentList.Add($arg)}
    $process=[Diagnostics.Process]::new()
    $process.StartInfo=$info
    [void]$process.Start()
    $children.Add($process)
    return $process
}
function Event([Diagnostics.Process]$Process,[string]$Expected) {
    $line=$Process.StandardOutput.ReadLineAsync()
    if(-not $line.Wait(10000)){throw ('Event timeout: '+$Expected)}
    $value=$line.Result
    Assert ($null -ne $value -and $value.StartsWith($Expected)) ('Expected '+$Expected+', got '+$value)
    return $value
}
function Release([Diagnostics.Process]$Process,[string]$Expected) {
    $Process.StandardInput.WriteLine('release')
    $Process.StandardInput.Flush()
    [void](Event $Process $Expected)
    Assert ($Process.WaitForExit(5000) -and $Process.ExitCode -eq 0) 'Release did not exit successfully'
}
try {
    $daily=Start-Child $gate @('-Job','daily','-LockRoot',$testRoot)
    [void](Event $daily 'JOB_ACQUIRED')
    $duplicate=Start-Child $gate @('-Job','daily','-LockRoot',$testRoot)
    [void](Event $duplicate 'JOB_ALREADY_RUNNING')
    Assert ($duplicate.WaitForExit(5000) -and $duplicate.ExitCode -eq 73) 'Wrong duplicate exit'
    $busy=Start-Child $gate @('-Job','weekly','-LockRoot',$testRoot)
    [void](Event $busy 'JOB_BUSY')
    Assert ($busy.WaitForExit(5000) -and $busy.ExitCode -eq 75) 'Wrong busy exit'
    $writer=Start-Child $writerScript @('-LockRoot',$testRoot)
    [void](Event $writer 'LOCK_ACQUIRED')
    $writerDuplicate=Start-Child $writerScript @('-LockRoot',$testRoot)
    [void](Event $writerDuplicate 'LOCK_BUSY')
    Assert ($writerDuplicate.WaitForExit(5000) -and $writerDuplicate.ExitCode -eq 73) 'Wrong writer duplicate exit'
    Release $writer 'LOCK_RELEASED'
    Assert (-not $daily.HasExited) 'Job must stay alive after writer release'
    $timed=Start-Child $gate @('-Job','monthly','-LockRoot',$testRoot,'-WaitTimeoutSeconds','1')
    [void](Event $timed 'JOB_WAITING')
    [void](Event $timed 'JOB_WAIT_TIMEOUT')
    Assert ($timed.WaitForExit(5000) -and $timed.ExitCode -eq 74) 'Wrong timeout exit'
    $waiting=Start-Child $gate @('-Job','weekly','-LockRoot',$testRoot,'-WaitTimeoutSeconds','10')
    [void](Event $waiting 'JOB_WAITING')
    Release $daily 'JOB_RELEASED'
    [void](Event $waiting 'JOB_ACQUIRED')
    Release $waiting 'JOB_RELEASED'
    $crash=Start-Child $gate @('-Job','manual','-LockRoot',$testRoot)
    [void](Event $crash 'JOB_ACQUIRED')
    $crash.Kill()
    Assert ($crash.WaitForExit(5000)) 'Crash child did not exit'
    $afterCrash=Start-Child $gate @('-Job','daily','-LockRoot',$testRoot)
    [void](Event $afterCrash 'JOB_ACQUIRED')
    Release $afterCrash 'JOB_RELEASED'
    Assert (Test-Path -LiteralPath (Join-Path $testRoot 'vault-job.guard')) 'Guard file must be retained'
    Assert (Test-Path -LiteralPath (Join-Path $testRoot 'vault-write.guard')) 'Writer guard must be retained'
    $iso=Start-Child $gate @('-Job','weekly','-LockRoot',$testRoot,'-AnchorUtc','2027-01-01T01:00:00Z','-ContextOnly')
    Assert ($iso.WaitForExit(5000)) 'Context child did not exit'
    $isoValue=$iso.StandardOutput.ReadToEnd()|ConvertFrom-Json
    Assert ($isoValue.cycle -eq '2026-W53') 'ISO week-year mismatch'
    $month=Start-Child $gate @('-Job','monthly','-LockRoot',$testRoot,'-AnchorUtc','2027-01-01T01:00:00Z','-ContextOnly')
    Assert ($month.WaitForExit(5000)) 'Month child did not exit'
    $monthValue=$month.StandardOutput.ReadToEnd()|ConvertFrom-Json
    Assert ($monthValue.cycle -eq '2027-01' -and $monthValue.review_period -eq '2026-12') 'Previous month mismatch'
    $invalid=Start-Child $gate @('-Job','daily','-LockRoot',$testRoot,'-AnchorUtc','2027-01-01T01:00:00','-ContextOnly')
    Assert ($invalid.WaitForExit(5000) -and $invalid.ExitCode -ne 0) 'Offset-less anchor must fail'
    [ordered]@{status='PASS';assertions=$script:assertions;isolated_test_root=$testRoot;test_files_retained=$true}|ConvertTo-Json
}
finally {
    foreach($child in $children){
        if(-not $child.HasExited){$child.Kill();[void]$child.WaitForExit(5000)}
        $child.Dispose()
    }
}
