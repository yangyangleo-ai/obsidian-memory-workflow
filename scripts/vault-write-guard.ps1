[CmdletBinding()]
param([Parameter(Mandatory)][string]$LockRoot,[string]$Owner=('writer-'+$PID))
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if (-not $IsWindows) { throw 'The guard support baseline is Windows with PowerShell 7.' }
$root=[IO.Path]::GetFullPath($LockRoot).TrimEnd('\')
if (-not [IO.Directory]::Exists($root)) { throw 'LockRoot must already exist and be independently reviewed.' }
if ($root -eq [IO.Path]::GetPathRoot($root).TrimEnd('\') -or $root -eq [Environment]::GetFolderPath('UserProfile')) { throw 'Refusing a broad lock directory.' }
$stream=$null
try {
    try { $stream=[IO.File]::Open((Join-Path $root 'vault-write.guard'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
    catch [IO.IOException] {
        if (($_.Exception.HResult -band 0xffff) -in @(32,33)) { [Console]::Out.WriteLine('LOCK_BUSY'); exit 73 }
        throw
    }
    $record=@{owner=$Owner;process_id=$PID;acquired_at_utc=[DateTimeOffset]::UtcNow.ToString('o')}
    [Console]::Out.WriteLine('LOCK_ACQUIRED '+($record|ConvertTo-Json -Compress))
    [Console]::Out.Flush()
    while ($true) {
        $line=[Console]::ReadLine()
        if ($null -eq $line -or $line.Trim() -eq 'release') { break }
    }
}
finally {
    if ($null -ne $stream) { $stream.Dispose(); [Console]::Out.WriteLine('LOCK_RELEASED'); [Console]::Out.Flush() }
}
