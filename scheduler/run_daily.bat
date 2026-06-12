@echo off
REM Wrapper invoked by Windows Task Scheduler. Runs the daily job-search pipeline.
REM Working dir = project root (this file lives in scheduler\).
cd /d "%~dp0.."

REM Prefer the py launcher; fall back to python on PATH.
where py >nul 2>&1 && (
  py -3 run_daily.py >> "logs\scheduler.out" 2>&1
) || (
  python run_daily.py >> "logs\scheduler.out" 2>&1
)
