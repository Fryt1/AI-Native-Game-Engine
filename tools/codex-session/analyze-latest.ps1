param(
  [switch]$Index,
  [int]$SessionLimit = 20,
  [string]$ProjectFilter = "",
  [switch]$FullTimeline
)

# Read-only wrapper for the external codex-session-timeline analyzer.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\tools\codex-session\analyze-latest.ps1
#   powershell -ExecutionPolicy Bypass -File .\tools\codex-session\analyze-latest.ps1 -FullTimeline
#   powershell -ExecutionPolicy Bypass -File .\tools\codex-session\analyze-latest.ps1 -Index -ProjectFilter AI-Native

$ErrorActionPreference = 'Stop'

if (-not (Get-Command codex-session-timeline -ErrorAction SilentlyContinue)) {
  Write-Error "codex-session-timeline is not installed. Run: python -m pip install -e D:\work\AI-Native\tools\codex-session-timeline-analyzer"
  exit 1
}

# Always use absolute output paths (the tool may mis-handle '..' relative paths).
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath '..\..'))
$reportDir = [System.IO.Path]::GetFullPath((Join-Path -Path $projectRoot -ChildPath 'artifacts\session-reports'))
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

if ($Index) {
  $out = [System.IO.Path]::GetFullPath((Join-Path -Path $reportDir -ChildPath 'index.html'))
  $cliArgs = @('--html-index-out', $out, '--session-limit', "$SessionLimit")
  if ($ProjectFilter) { $cliArgs += @('--project-filter', $ProjectFilter) }
  & codex-session-timeline @cliArgs
  Write-Host "`nHTML index: $out"
} else {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $out = [System.IO.Path]::GetFullPath((Join-Path -Path $reportDir -ChildPath "latest-$stamp.html"))
  if ($FullTimeline) {
    # Full timeline only for small sessions; huge rollouts may hang.
    $cliArgs = @('--latest', '--html-out', $out, '--timeline-limit', '-1')
  } else {
    # Default: render first 30 timeline buckets (summary + bottlenecks only).
    $cliArgs = @('--latest', '--html-out', $out, '--timeline-limit', '30')
  }
  & codex-session-timeline @cliArgs
  Write-Host "`nHTML report: $out"
}

# Uncomment to auto-open in browser:
# Start-Process $out