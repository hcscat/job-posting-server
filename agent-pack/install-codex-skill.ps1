$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$targetDir = Join-Path $codexHome "skills\\job-posting-collector"

New-Item -ItemType Directory -Force -Path (Join-Path $codexHome "skills") | Out-Null
if (Test-Path $targetDir) {
    Remove-Item -Recurse -Force $targetDir
}
Copy-Item -Recurse -Force (Join-Path $scriptDir "codex\\job-posting-collector") $targetDir

Write-Host "Installed Codex skill to: $targetDir"
