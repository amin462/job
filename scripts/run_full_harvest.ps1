<#
.SYNOPSIS
    รันเก็บข้อมูลระยะยาวแบบอัตโนมัติ (JobThai + JobBKK แยก 1 process ต่อ 1 โดเมน)
    ตามด้วย ETL และเทรน/Export โมเดล ML (T1.8, T1.9, T3.7, T4.5)

.DESCRIPTION
    สคริปต์นี้ออกแบบสำหรับการรันข้ามคืนเพื่อเก็บตัวอย่างประกาศงาน 5,000–10,000+ ประกาศ
    โดยปฏิบัติตามกติกา ToS / PDPA / Polite Scraping อย่างเคร่งครัด:
      - ปฏิเสธการทำงานทันทีหาก -DelayMinSec < 5.0 วินาที
      - แยก Process อิสระ 1 ตัวต่อ 1 เว็บไซต์ (concurrency = 1 ต่อโดเมน):
          1) JobThai: pipeline.scraper.harvest_batch -> data/raw/jobthai
          2) JobBKK : pipeline.scraper.jobbkk_harvest -> data/raw/jobbkk
      - รองรับ Auto-Resume (นับไฟล์ job_*.html ที่มีอยู่แล้ว ข้ามไฟล์ซ้ำอัตโนมัติ)
      - หากพบ HTTP 403 / 429 / CAPTCHA (exit code 2) ให้หยุดเก็บเว็บไซต์นั้นทันที
      - เมื่อเก็บเสร็จ (หรือถึงเป้า / หยุดสุภาพ) จะรัน ETL:
          pipeline.etl.run_pipeline -> data/processed/clean_postings.csv, seed_marts.json, docs/dq-report.md
      - จากนั้นรัน ML Benchmark + Champion Selection + Export (ยกเว้นใส่ -SkipML):
          pipeline.ml.export_model --merge-seed -> models/salary_champion.joblib, feature_spec.json,
          data/processed/ml_marts.json, data/processed/seed_marts.json, docs/ml-report.md

.EXAMPLE
    .\scripts\run_full_harvest.ps1 -DryRun
    .\scripts\run_full_harvest.ps1 -WhatIf
    .\scripts\run_full_harvest.ps1 -TargetJobThai 5000 -TargetJobBKK 5000 -BatchSize 100 -DelayMinSec 5.2
    .\scripts\run_full_harvest.ps1 -TargetJobThai 500 -TargetJobBKK 0 -SkipML
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [int]$TargetJobThai = 5000,
    [int]$TargetJobBKK = 5000,
    [int]$BatchSize = 100,
    [double]$DelayMinSec = 5.2,
    [switch]$SkipML,
    [switch]$DryRun,
    [int]$MaxBatchesPerSite = 150,
    [int]$MaxEmptyBatches = 3
)

$ErrorActionPreference = "Stop"

# 1. บังคับกติกาเหล็ก Polite Scraping (ต้อง >= 5.0 วินาทีเสมอ)
if ($DelayMinSec -lt 5.0) {
    Write-Error "POLITE SCRAPING VIOLATION: -DelayMinSec must be >= 5.0 seconds (got $DelayMinSec)."
    exit 1
}
if ($BatchSize -lt 1) {
    Write-Error "Invalid parameter: -BatchSize must be >= 1 (got $BatchSize)."
    exit 1
}
if ($TargetJobThai -lt 0 -or $TargetJobBKK -lt 0) {
    Write-Error "Invalid parameter: -TargetJobThai and -TargetJobBKK must be >= 0."
    exit 1
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$MasterLog = Join-Path $LogDir "full_harvest.log"
$JobThaiDir = Join-Path $ProjectRoot "data\raw\jobthai"
$JobBkkDir = Join-Path $ProjectRoot "data\raw\jobbkk"
$DelayMaxSec = [Math]::Round($DelayMinSec + 1.1, 2)
$DelayMinStr = $DelayMinSec.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
$DelayMaxStr = $DelayMaxSec.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
$IsSimulated = $DryRun -or $WhatIfPreference

if (-not (Test-Path $PythonExe)) {
    Write-Error "ไม่พบ Python virtual environment ที่ $PythonExe — กรุณาสร้าง .venv และติดตั้ง pipeline/requirements.txt ก่อน"
    exit 1
}

function Get-RawJobCount {
    param([string]$DirPath)
    if (-not (Test-Path $DirPath)) { return 0 }
    return @(Get-ChildItem -LiteralPath $DirPath -Filter "job_*.html" -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 0 }).Count
}

$InitialJobThai = Get-RawJobCount -DirPath $JobThaiDir
$InitialJobBkk = Get-RawJobCount -DirPath $JobBkkDir

$EtlRawDirs = @(
    "spike/raw/jobthai/sample",
    "spike/raw/jobthai/by_province",
    "data/raw/jobthai",
    "data/raw/jobbkk"
)

Write-Host "=== Full Harvest + ETL + ML Refresh Plan ==="
Write-Host "ProjectRoot     : $ProjectRoot"
Write-Host "PythonExe       : $PythonExe"
Write-Host "DelayMinSec     : $DelayMinStr s (jitter up to $DelayMaxStr s)"
Write-Host "BatchSize       : $BatchSize postings/batch (max $MaxBatchesPerSite batches/site, stop after $MaxEmptyBatches empty batches)"
Write-Host "JobThai Target  : $TargetJobThai (existing in data/raw/jobthai: $InitialJobThai)"
Write-Host "JobBKK Target   : $TargetJobBKK (existing in data/raw/jobbkk: $InitialJobBkk)"
Write-Host "ETL Raw Dirs    : $($EtlRawDirs -join ', ')"
Write-Host "Run ML Pipeline : $(-not $SkipML)"

if ($IsSimulated) {
    Write-Host "`n[DryRun/WhatIf] ตรวจสอบพารามิเตอร์และแผนรันกระบวนการสำเร็จ (ไม่ได้ยิง HTTP จริง)"
    Write-Host "  1) Process A (JobThai, concurrency=1): $PythonExe -B -X utf8 -m pipeline.scraper.harvest_batch --batch-size $BatchSize --out-dir data/raw/jobthai --min-delay $DelayMinStr --max-delay $DelayMaxStr"
    Write-Host "  2) Process B (JobBKK,  concurrency=1): $PythonExe -B -X utf8 -m pipeline.scraper.jobbkk_harvest (batch=$BatchSize, out-dir=data/raw/jobbkk, delay>=$DelayMinStr)"
    Write-Host "  3) Sequential ETL                   : $PythonExe -B -X utf8 -m pipeline.etl.run_pipeline --raw-dirs $($EtlRawDirs -join ' ') --out-dir data/processed --dq-report docs/dq-report.md"
    if (-not $SkipML) {
        Write-Host "  4) Sequential ML (benchmark->export): $PythonExe -B -X utf8 -m pipeline.ml.export_model --input data/processed/clean_postings.csv --models-dir models --out-dir data/processed --report docs/ml-report.md --merge-seed"
    } else {
        Write-Host "  4) ML Pipeline                      : SKIPPED (-SkipML)"
    }
    exit 0
}

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
if (-not (Test-Path $JobThaiDir)) { New-Item -ItemType Directory -Force -Path $JobThaiDir | Out-Null }
if (-not (Test-Path $JobBkkDir)) { New-Item -ItemType Directory -Force -Path $JobBkkDir | Out-Null }

Push-Location -LiteralPath $ProjectRoot
try {

function Write-MasterLog {
    param([string]$Message)
    $line = "[" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "] " + $Message
    Write-Host $line
    Add-Content -LiteralPath $MasterLog -Value $line -Encoding UTF8
}

function Start-DomainWorker {
    param(
        [string]$SiteName,
        [string]$ModuleName,
        [string]$ModuleFileRelative,
        [string]$OutDir,
        [int]$TargetCount,
        [int]$BatchSize,
        [string]$MinDelayStr,
        [string]$MaxDelayStr,
        [int]$MaxBatches,
        [int]$MaxEmpty,
        [string]$LogFile
    )

    $moduleFile = Join-Path $ProjectRoot $ModuleFileRelative
    if (-not (Test-Path $moduleFile)) {
        Write-MasterLog "[$SiteName] ไม่พบโมดูล $ModuleFileRelative — ข้ามการเก็บข้อมูลฝั่ง $SiteName"
        return $null
    }

    $currentCount = Get-RawJobCount -DirPath $OutDir
    if ($TargetCount -le 0 -or $currentCount -ge $TargetCount) {
        Write-MasterLog "[$SiteName] มีไฟล์แล้ว $currentCount / เป้าหมาย $TargetCount — ไม่ต้องดึงเพิ่ม"
        return $null
    }

    # สร้างสคริปต์ย่อยที่ทำงานแบบ sequential (concurrency=1) เฉพาะโดเมนนี้เท่านั้น
    $workerScript = @"
`$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath '$ProjectRoot'
`$py = '$PythonExe'
`$outDir = '$OutDir'
`$target = $TargetCount
`$batchSize = $BatchSize
`$minDelay = '$MinDelayStr'
`$maxDelay = '$MaxDelayStr'
`$maxBatches = $MaxBatches
`$maxEmpty = $MaxEmpty
`$logFile = '$LogFile'
`$module = '$ModuleName'

function Log-Worker([string]`$msg) {
    `$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[`$ts] [$SiteName] `$msg" | Tee-Object -FilePath `$logFile -Append | Out-Null
}

function Count-RawFiles {
    if (-not (Test-Path `$outDir)) { return 0 }
    return @(Get-ChildItem -LiteralPath `$outDir -Filter 'job_*.html' -File -ErrorAction SilentlyContinue | Where-Object { `$_.Length -gt 0 }).Count
}

`$helpText = (& `$py -B -X utf8 -m `$module --help 2>&1 | Out-String)
`$emptyStreak = 0
`$batch = 0

Log-Worker "Worker started (target=`$target, batchSize=`$batchSize, delay>=`$minDelay s)"

while (`$batch -lt `$maxBatches) {
    `$before = Count-RawFiles
    if (`$before -ge `$target) {
        Log-Worker "Target reached: `$before >= `$target"
        break
    }
    `$batch++
    `$remaining = `$target - `$before
    `$thisBatch = [Math]::Min(`$batchSize, `$remaining)

    `$cliArgs = @('-B', '-X', 'utf8', '-m', `$module)
    if (`$helpText -match '--batch-size') {
        `$cliArgs += @('--batch-size', "`$thisBatch")
    } elseif (`$helpText -match '--max-jobs') {
        `$cliArgs += @('--max-jobs', "`$thisBatch")
    }
    if (`$helpText -match '--out-dir') {
        `$cliArgs += @('--out-dir', `$outDir)
    }
    if (`$helpText -match '--min-delay') {
        `$cliArgs += @('--min-delay', "`$minDelay")
    } elseif (`$helpText -match '(?<!\w)--delay\b') {
        `$cliArgs += @('--delay', "`$minDelay")
    }
    if (`$helpText -match '--max-delay') {
        `$cliArgs += @('--max-delay', "`$maxDelay")
    }
    if (`$helpText -match '--label') {
        `$cliArgs += @('--label', "auto_`$batch")
    }

    Log-Worker "Starting batch #`$batch (requesting up to `$thisBatch new postings; current=`$before)"
    & `$py @cliArgs *>> `$logFile
    `$code = `$LASTEXITCODE
    `$after = Count-RawFiles
    `$added = `$after - `$before
    Log-Worker "Batch #`$batch finished: exit=`$code, added=`$added, total=`$after"

    if (`$code -eq 2) {
        Log-Worker "HALTED politely due to HTTP 403/429/CAPTCHA (exit=2). Never bypassing."
        exit 2
    }
    if (`$code -ne 0) {
        Log-Worker "Worker exited with error code `$code. Stopping domain loop."
        exit `$code
    }
    if (`$added -le 0) {
        `$emptyStreak++
        if (`$emptyStreak -ge `$maxEmpty) {
            Log-Worker "Stopping after `$emptyStreak consecutive batches with 0 new files."
            break
        }
    } else {
        `$emptyStreak = 0
    }
}
exit 0
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($workerScript))
    $proc = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru
    $null = $proc.Handle

    Write-MasterLog "[$SiteName] เริ่ม Process PID=$($proc.Id) (log: $LogFile)"
    return $proc
}

Write-MasterLog "=== เริ่มรอบเก็บข้อมูลระยะยาว (JobThai target=$TargetJobThai, JobBKK target=$TargetJobBKK) ==="

$workers = @()
$pJobThai = Start-DomainWorker `
    -SiteName "JobThai" `
    -ModuleName "pipeline.scraper.harvest_batch" `
    -ModuleFileRelative "pipeline\scraper\harvest_batch.py" `
    -OutDir $JobThaiDir `
    -TargetCount $TargetJobThai `
    -BatchSize $BatchSize `
    -MinDelayStr $DelayMinStr `
    -MaxDelayStr $DelayMaxStr `
    -MaxBatches $MaxBatchesPerSite `
    -MaxEmpty $MaxEmptyBatches `
    -LogFile (Join-Path $LogDir "harvest_jobthai.log")
if ($pJobThai) { $workers += @{ Name = "JobThai"; Proc = $pJobThai } }

$pJobBkk = Start-DomainWorker `
    -SiteName "JobBKK" `
    -ModuleName "pipeline.scraper.jobbkk_harvest" `
    -ModuleFileRelative "pipeline\scraper\jobbkk_harvest.py" `
    -OutDir $JobBkkDir `
    -TargetCount $TargetJobBKK `
    -BatchSize $BatchSize `
    -MinDelayStr $DelayMinStr `
    -MaxDelayStr $DelayMaxStr `
    -MaxBatches $MaxBatchesPerSite `
    -MaxEmpty $MaxEmptyBatches `
    -LogFile (Join-Path $LogDir "harvest_jobbkk.log")
if ($pJobBkk) { $workers += @{ Name = "JobBKK"; Proc = $pJobBkk } }

foreach ($w in $workers) {
    $w.Proc.WaitForExit()
    $exitCode = $w.Proc.ExitCode
    if ($exitCode -eq 2) {
        Write-MasterLog "[$($w.Name)] หยุดการดึงข้อมูลทันทีตามกติกา 403/429/CAPTCHA (exit=2) — จะประมวลผลเฉพาะไฟล์ที่เก็บมาได้แล้ว"
    } elseif ($exitCode -ne 0) {
        Write-MasterLog "[$($w.Name)] จบการทำงานด้วย exit code $exitCode"
    } else {
        Write-MasterLog "[$($w.Name)] จบการเก็บข้อมูลเรียบร้อย (exit=0)"
    }
}

$FinalJobThai = Get-RawJobCount -DirPath $JobThaiDir
$FinalJobBkk = Get-RawJobCount -DirPath $JobBkkDir
Write-MasterLog "สรุปไฟล์ดิบหลังจบ Harvest: data/raw/jobthai=$FinalJobThai, data/raw/jobbkk=$FinalJobBkk"

# 2. รัน ETL (pipeline.etl.run_pipeline)
Write-MasterLog "เริ่มรัน ETL pipeline -> data/processed/ ..."
& $PythonExe -B -X utf8 -m pipeline.etl.run_pipeline `
    --raw-dirs $EtlRawDirs `
    --out-dir data/processed `
    --dq-report docs/dq-report.md *>> $MasterLog
$etlExit = $LASTEXITCODE
if ($etlExit -ne 0) {
    Write-MasterLog "ERROR: pipeline.etl.run_pipeline ล้มเหลว (exit=$etlExit)"
    exit $etlExit
}
Write-MasterLog "ETL pipeline สำเร็จ (exit=0)"

# 3. รัน ML Benchmark + Champion Selection + Export (pipeline.ml.export_model)
if (-not $SkipML) {
    Write-MasterLog "เริ่มรัน ML Benchmark -> Champion -> Export (models/ + seed_marts.json) ..."
    & $PythonExe -B -X utf8 -m pipeline.ml.export_model `
        --input data/processed/clean_postings.csv `
        --models-dir models `
        --out-dir data/processed `
        --report docs/ml-report.md `
        --merge-seed *>> $MasterLog
    $mlExit = $LASTEXITCODE
    if ($mlExit -ne 0) {
        Write-MasterLog "ERROR: pipeline.ml.export_model ล้มเหลว (exit=$mlExit)"
        exit $mlExit
    }
    Write-MasterLog "ML Benchmark + Export สำเร็จ (exit=0)"
} else {
    Write-MasterLog "ข้ามขั้นตอน ML ตามพารามิเตอร์ -SkipML"
}

Write-MasterLog "=== เสร็จสิ้นรอบ Full Harvest + ETL + ML Refresh ==="
exit 0
}
finally {
    Pop-Location
}
