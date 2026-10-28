[CmdletBinding()]
param([string]$Target = '', [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot))
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Safe-Path([string]$Value) {
    $full = [IO.Path]::GetFullPath($Value)
    $item = $full
    while ($item) {
        if (Test-Path -LiteralPath $item) {
            $entry = Get-Item -LiteralPath $item -Force
            if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Links and reparse points are not supported.' }
        }
        $parent = Split-Path -Parent $item
        if ($parent -eq $item) { break }
        $item = $parent
    }
    if ($full.TrimEnd('\','/') -eq ([IO.Path]::GetPathRoot($full)).TrimEnd('\','/')) { throw 'Filesystem root is not a target.' }
    if ($full.TrimEnd('\','/') -eq $HOME.TrimEnd('\','/')) { throw 'Home directory is not a target.' }
    return $full.TrimEnd('\','/')
}

function Safe-Name([string]$Name) {
    if (-not $Name -or $Name.Contains('\') -or $Name.Contains(':') -or $Name.StartsWith('/')) { throw 'Invalid relative name.' }
    foreach ($part in $Name.Split('/')) {
        if ($part -in @('', '.', '..', '.git', '.obsidian', 'private', 'local', 'runtime', 'control', 'receipts', 'backups', 'snapshots') -or $part.StartsWith('.env', [StringComparison]::OrdinalIgnoreCase)) { throw 'Private or ambiguous relative name.' }
    }
    return $Name
}

function Bytes-Hash([byte[]]$Bytes) {
    $h = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($h.ComputeHash($Bytes))).Replace('-','') } finally { $h.Dispose() }
}

function File-Hash([string]$Path) {
    $stream = [IO.File]::OpenRead((Safe-Path $Path))
    $h = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($h.ComputeHash($stream))).Replace('-','') }
    finally { $h.Dispose(); $stream.Dispose() }
}

function Write-New([string]$Path, [byte[]]$Bytes) {
    $parent = Split-Path -Parent $Path
    Safe-Path $parent | Out-Null
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    Safe-Path $Path | Out-Null
    $s = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $s.Write($Bytes, 0, $Bytes.Length); $s.Flush($true) } finally { $s.Dispose() }
}

try {
    $source = Safe-Path $SourceRoot
    if ([string]::IsNullOrWhiteSpace($Target)) { $Target = Join-Path $HOME 'AI-Memory-Workspace' }
    $dest = Safe-Path $Target
    if ($dest.Equals($source, [StringComparison]::OrdinalIgnoreCase) -or $dest.StartsWith($source + '\', [StringComparison]::OrdinalIgnoreCase) -or $source.StartsWith($dest + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Source and target must not overlap.' }
    if (Test-Path -LiteralPath $dest) {
        $receiptPath = Safe-Path (Join-Path $dest 'runtime/setup-receipt.json')
        if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf) -or (Get-Item -LiteralPath $receiptPath).Length -gt 200000) { throw 'Existing folder is foreign or partial; choose a new target.' }
        $old = [IO.File]::ReadAllText($receiptPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if ($old.kind -ne 'obsidian-memory-workspace' -or $old.status -ne 'FILES_VERIFIED' -or $old.schema_version -ne 1 -or $null -eq $old.files -or $old.files -isnot [PSCustomObject]) { throw 'Invalid installation receipt.' }
        $properties = @($old.files.PSObject.Properties)
        if ($properties.Count -lt 1 -or $properties.Count -gt 512) { throw 'Invalid receipt inventory.' }
        $changed = @()
        foreach ($p in $properties) {
            $name = Safe-Name $p.Name
            if ($p.Value -isnot [string] -or $p.Value -notmatch '^[A-Fa-f0-9]{64}$') { throw 'Invalid receipt hash.' }
            $file = Safe-Path (Join-Path $dest $name)
            if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (File-Hash $file) -ne $p.Value) { $changed += $name }
        }
        [ordered]@{status='ALREADY_PRESENT_USER_DATA_PRESERVED'; version=$old.version; changed_files=$changed; file_count=$properties.Count; written=$false; ai_acceptance='NOT_TESTED'; target=$dest} | ConvertTo-Json -Depth 6
        exit 0
    }
    $parent = Split-Path -Parent $dest
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Target parent must already exist.' }
    $walk = $parent
    while ($walk) {
        if (Test-Path -LiteralPath (Join-Path $walk '.git')) { throw 'Install outside existing Git repositories.' }
        $next = Split-Path -Parent $walk
        if ($next -eq $walk) { break }
        $walk = $next
    }
    $listPath = Safe-Path (Join-Path $source 'PUBLIC_FILES.txt')
    if ((Get-Item -LiteralPath $listPath).Length -gt 200000) { throw 'Oversized allowlist.' }
    $names = @([IO.File]::ReadAllLines($listPath, [Text.Encoding]::UTF8) | Where-Object { $_ -and -not $_.StartsWith('#') })
    $seen = @{}
    $payload = @{}
    $sourceHashes = @{}
    $total = 0
    if ($names.Count -lt 1 -or $names.Count -gt 512) { throw 'Invalid allowlist size.' }
    foreach ($name in $names) {
        Safe-Name $name | Out-Null
        if ($seen.ContainsKey($name)) { throw 'Duplicate or case-ambiguous public file.' }
        $seen[$name] = $true
        $file = Safe-Path (Join-Path $source $name)
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-Item -LiteralPath $file).Length -gt 200000) { throw 'Missing or oversized public file.' }
        [byte[]]$bytes = [IO.File]::ReadAllBytes($file)
        $total += $bytes.Length
        if ($total -gt 20000000 -or $bytes -contains 0) { throw 'Binary or oversized payload.' }
        $strictUtf8 = New-Object Text.UTF8Encoding($false, $true)
        $strictUtf8.GetString($bytes) | Out-Null
        $sourceHashes[$name] = Bytes-Hash $bytes
        if ($name -eq '.gitignore') { $bytes += [Text.Encoding]::UTF8.GetBytes("`n# Installed workspace: never publish personal notes.`n/vault-template/`n/runtime/`n/control/`n") }
        $payload[$name] = $bytes
    }
    foreach ($required in @('PUBLIC_FILES.txt','VERSION','.gitignore','START_HERE.md','AI_START_HERE.md','AGENTS.md','CLAUDE.md','GEMINI.md','.github/copilot-instructions.md','.cursor/rules/project-memory.mdc',('vault-template/' + [char]0x9996 + [char]0x9875 + '.md'))) {
        if (-not $payload.ContainsKey($required)) { throw 'Incomplete installation source.' }
    }
    $version = [Text.Encoding]::UTF8.GetString($payload['VERSION']).Trim()
    if ($version -notmatch '^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$') { throw 'Invalid source version.' }
    foreach ($name in $names) { if ((File-Hash (Join-Path $source $name)) -ne $sourceHashes[$name]) { throw 'Source changed during preflight.' } }
    # New-Item fails if another installer reserved this directory. Never merge or clean up.
    New-Item -ItemType Directory -Path $dest -ErrorAction Stop | Out-Null
    $hashes = [ordered]@{}
    foreach ($name in $names) {
        $file = Join-Path $dest $name
        Write-New $file $payload[$name]
        $hashes[$name] = Bytes-Hash $payload[$name]
        if ((File-Hash $file) -ne $hashes[$name]) { throw 'Readback failed; partial installation is preserved.' }
    }
    foreach ($name in $names) { if ((File-Hash (Join-Path $dest $name)) -ne $hashes[$name]) { throw 'Installed content changed; no success marker written.' } }
    $receipt = [ordered]@{schema_version=1; kind='obsidian-memory-workspace'; status='FILES_VERIFIED'; version=$version; created_at_utc=[DateTimeOffset]::UtcNow.ToString('o'); files=$hashes; scope='local files only; no account, model, plugin, schedule or permission changes'; ai_acceptance='NOT_TESTED'}
    $receiptPath = Join-Path $dest 'runtime/setup-receipt.json'
    [byte[]]$receiptBytes = [Text.Encoding]::UTF8.GetBytes(($receipt | ConvertTo-Json -Depth 6) + "`n")
    Write-New $receiptPath $receiptBytes
    if ((File-Hash $receiptPath) -ne (Bytes-Hash $receiptBytes)) { throw 'Receipt readback failed.' }
    [ordered]@{status='INSTALLED_FILES_VERIFIED'; file_count=$names.Count; written=$true; target=$dest; start=(Join-Path $dest 'START_HERE.md'); ai_acceptance='NOT_TESTED'} | ConvertTo-Json -Depth 5
    exit 0
} catch {
    [ordered]@{status='FAILED_NO_OVERWRITE'; reason=$_.Exception.Message} | ConvertTo-Json -Compress | Write-Output
    exit 2
}
