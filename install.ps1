param([string]$Target = '')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts/install_workspace.ps1') -Target $Target
exit $LASTEXITCODE
