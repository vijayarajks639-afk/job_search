<#
Registers two daily Windows scheduled tasks for the job-search pipeline:
  - JobSearch_Morning  at 06:00 (IST — machine clock is IST)
  - JobSearch_Evening  at 22:00

Run once, in a normal PowerShell window (no admin needed for per-user tasks):
    powershell -ExecutionPolicy Bypass -File scheduler\setup_tasks.ps1

Tasks run only when you are logged on (so they inherit your Claude Code + Gmail
auth), and use StartWhenAvailable to catch up a missed run after the machine wakes.
Re-running this script updates the existing tasks.
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $PSScriptRoot "run_daily.bat"
if (-not (Test-Path $bat)) { throw "run_daily.bat not found at $bat" }

$action = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $projectRoot

$triggers = @(
    New-ScheduledTaskTrigger -Daily -At 6:00AM
    New-ScheduledTaskTrigger -Daily -At 10:00PM
)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

$taskName = "JobSearch_Daily"
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers `
    -Settings $settings -Principal $principal `
    -Description "Daily India-GCC job search: agentic match + honest tailoring + emailed report (06:00 & 22:00 IST)." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$taskName' with triggers at 06:00 and 22:00 (IST)."
Write-Host "Inspect with:  Get-ScheduledTask -TaskName JobSearch_Daily"
Write-Host "Run now with:   Start-ScheduledTask -TaskName JobSearch_Daily"
