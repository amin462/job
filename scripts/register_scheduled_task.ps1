<#
.SYNOPSIS
    T0.5 — ลงทะเบียน Windows Task Scheduler สำหรับรัน Pipeline รายสัปดาห์
    (re-discovery หน้ารายการ JobThai + ETL อัปเดต DW/Marts)

.DESCRIPTION
    สคริปต์นี้สร้างงานตั้งเวลา (Scheduled Task) บน Windows เพื่อรัน:
      1) pipeline/scraper/rediscover.py  (อัปเดต last_seen และหา job id ใหม่แบบสุภาพ)
      2) pipeline/etl/run_pipeline.py    (คลีน ดึงทักษะ ตรวจ DQ และอัปเดต DW/Marts)

    หมายเหตุเรื่อง Keep-Alive ด้วย cron-job.org (ทำควบคู่กันบนเว็บ https://cron-job.org):
    -----------------------------------------------------------------------
    1. กัน Supabase Free Tier หยุดทำงาน (Pause หลังไม่มีการใช้งาน 7 วัน):
       - ตั้ง cron-job.org ยิงทุก 3 วัน (เช่น Cron: "0 9 */3 * *")
       - Method: GET
       - URL: https://<your-project-id>.supabase.co/rest/v1/public_summary?select=n_postings&limit=1
       - Headers:
           apikey: <NEXT_PUBLIC_SUPABASE_ANON_KEY>
           Authorization: Bearer <NEXT_PUBLIC_SUPABASE_ANON_KEY>
           Accept-Profile: mart
       - (หากเปิดเฉพาะ schema `public` ใน Supabase API Settings สามารถเรียก RPC `GET /rest/v1/rpc/get_dim_locations` แทนได้)

    2. กัน Render Free Tier หลับ (Spin down หลังไม่มีทราฟฟิก 15 นาที — ใช้เฉพาะช่วงซ้อม/วันสอบ):
       - ตั้ง cron-job.org ยิงทุก 14 นาที (Cron: "*/14 * * * *")
       - Method: GET
       - URL: https://<your-ml-api>.onrender.com/health
       - หมายเหตุ: Render Free ให้ 750 ชม./เดือน (1 เดือนมี 744 ชม. เปิดบริการเดียวได้ตลอดเดือน)
         และเมื่อปิดช่วงสอบแล้วสามารถปิด job นี้ใน cron-job.org ได้

.EXAMPLE
    .\scripts\register_scheduled_task.ps1 -DryRun
    .\scripts\register_scheduled_task.ps1 -DayOfWeek Sunday -Time "02:00"
    .\scripts\register_scheduled_task.ps1 -Unregister
#>

[CmdletBinding()]
param(
    [string]$TaskName = "SkillDemandIntelligence-WeeklyPipeline",
    [ValidateSet("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")]
    [string]$DayOfWeek = "Sunday",
    [string]$Time = "02:00",
    [switch]$Unregister,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "weekly_pipeline.log"

if ($Unregister) {
    if ($DryRun) {
        Write-Host "[DryRun] จะยกเลิก Scheduled Task: $TaskName"
        exit 0
    }
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "ยกเลิก Scheduled Task '$TaskName' เรียบร้อยแล้ว"
    } else {
        Write-Host "ไม่พบ Scheduled Task ชื่อ '$TaskName'"
    }
    exit 0
}

if (-not (Test-Path $PythonExe)) {
    Write-Warning "ไม่พบ .venv ที่ $PythonExe — กรุณาสร้าง .venv ก่อนรันงานจริง (py -3 -m venv .venv)"
}

# คำสั่งที่ Task Scheduler จะรัน: เปลี่ยนไดเรกทอรี -> รัน rediscover.py -> รัน run_pipeline.py พร้อมบันทึก log
# หมายเหตุ: ไม่ใช้ธง -I (isolated mode) เพราะ -I จะตัดโฟลเดอร์โปรเจกต์ปัจจุบันออกจาก sys.path ทำให้ -m pipeline.* หาแพ็กเกจไม่พบ
$RunnerScript = @"
Set-Location -LiteralPath '$ProjectRoot'
if (-not (Test-Path '$LogDir')) { New-Item -ItemType Directory -Force -Path '$LogDir' | Out-Null }
Add-Content -Path '$LogFile' -Value ("`n=== Weekly Pipeline Started: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")
& '$PythonExe' -B -X utf8 -m pipeline.scraper.rediscover *>> '$LogFile'
if (`$LASTEXITCODE -ne 0) {
    Add-Content -Path '$LogFile' -Value ("ERROR: rediscover exited with code " + `$LASTEXITCODE)
    exit `$LASTEXITCODE
}
& '$PythonExe' -B -X utf8 -m pipeline.etl.run_pipeline *>> '$LogFile'
Add-Content -Path '$LogFile' -Value ("=== Weekly Pipeline Finished (exit=" + `$LASTEXITCODE + "): " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")
"@

$EncodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($RunnerScript))
$TaskArgs = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $EncodedCommand"

Write-Host "=== รายละเอียด Task Scheduler (T0.5) ==="
Write-Host "ชื่อ Task   : $TaskName"
Write-Host "โฟลเดอร์งาน : $ProjectRoot"
Write-Host "Python     : $PythonExe"
Write-Host "กำหนดการ   : ทุกวัน $DayOfWeek เวลา $Time น."
Write-Host "ไฟล์ Log    : $LogFile"

if ($DryRun) {
    Write-Host "`n[DryRun] ตรวจสอบโครงสร้างคำสั่งเรียบร้อย (ยังไม่ได้ลงทะเบียนจริงใน Task Scheduler)"
    Write-Host "ขั้นตอนรันภายใน:"
    Write-Host "  1) $PythonExe -B -X utf8 -m pipeline.scraper.rediscover"
    Write-Host "  2) $PythonExe -B -X utf8 -m pipeline.etl.run_pipeline"
    exit 0
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $TaskArgs `
    -WorkingDirectory $ProjectRoot

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $Time

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Skill Demand Intelligence (E'): Weekly polite re-discovery and ETL pipeline refresh" `
    -Force | Out-Null

Write-Host "`nลงทะเบียน Scheduled Task '$TaskName' สำเร็จแล้ว"
Write-Host "ทดสอบรันทันทีด้วยคำสั่ง: Start-ScheduledTask -TaskName '$TaskName'"
