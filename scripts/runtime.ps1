[CmdletBinding()]
param(
    [ValidateSet("start", "status", "stop", "restart", "health", "migrate", "seed", "reset")]
    [string]$Command = "status",
    [int]$BackendPort = 8020,
    [int]$FrontendPort = 4174,
    [int]$DemoPort = 8021
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
$Vite = Join-Path $Root "frontend\node_modules\vite\bin\vite.js"
$RuntimeRoot = if ($env:AUTHZDIFF_RUNTIME_DIR) {
    $env:AUTHZDIFF_RUNTIME_DIR
} else {
    Join-Path $env:LOCALAPPDATA "AuthZDiff"
}
$PidFile = Join-Path $RuntimeRoot "processes.json"
$SecretFile = Join-Path $RuntimeRoot "local-secrets.json"
$LogRoot = Join-Path $RuntimeRoot "logs"

function New-RandomBase64([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    } finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($buffer)
}

function Initialize-Runtime {
    New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null
    if (-not (Test-Path -LiteralPath $SecretFile)) {
        $database = (Join-Path $RuntimeRoot "authzdiff.sqlite").Replace("\", "/")
        @{
            app_secret = New-RandomBase64
            encryption_key = New-RandomBase64
            setup_token = New-RandomBase64
            demo_reset_token = New-RandomBase64
            database_url = "sqlite+aiosqlite:///$database"
        } | ConvertTo-Json | Set-Content -LiteralPath $SecretFile -Encoding utf8
    }
}

function Get-Secrets {
    Initialize-Runtime
    return Get-Content -LiteralPath $SecretFile -Raw | ConvertFrom-Json
}

function Get-Records {
    if (-not (Test-Path -LiteralPath $PidFile)) { return @() }
    try {
        return @(Get-Content -LiteralPath $PidFile -Raw | ConvertFrom-Json)
    } catch {
        throw "Runtime PID record is unreadable: $PidFile"
    }
}

function Test-RecordOwned($Record) {
    $process = Get-Process -Id $Record.pid -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    return $process.StartTime.ToUniversalTime().ToString("o") -eq $Record.started_at
}

function Get-ListeningOwner([int]$Port) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($connection) { return $connection.OwningProcess }
    return $null
}

function Assert-PortsFree {
    foreach ($port in @($BackendPort, $FrontendPort, $DemoPort)) {
        $owner = Get-ListeningOwner $port
        if ($owner) {
            throw "Port $port is already owned by PID $owner. AuthZDiff will not terminate it."
        }
    }
}

function Start-OwnedProcess(
    [string]$Name,
    [string]$FileName,
    [string]$Arguments,
    [string]$WorkingDirectory,
    [hashtable]$Environment
) {
    $stdout = Join-Path $LogRoot "$Name.stdout.log"
    $stderr = Join-Path $LogRoot "$Name.stderr.log"
    $previous = @{}
    try {
        foreach ($entry in $Environment.GetEnumerator()) {
            $previous[$entry.Key] = [Environment]::GetEnvironmentVariable(
                $entry.Key,
                [EnvironmentVariableTarget]::Process
            )
            [Environment]::SetEnvironmentVariable(
                $entry.Key,
                [string]$entry.Value,
                [EnvironmentVariableTarget]::Process
            )
        }
        $process = Start-Process `
            -FilePath $FileName `
            -ArgumentList $Arguments `
            -WorkingDirectory $WorkingDirectory `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru
    } finally {
        foreach ($entry in $Environment.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable(
                $entry.Key,
                $previous[$entry.Key],
                [EnvironmentVariableTarget]::Process
            )
        }
    }
    Start-Sleep -Milliseconds 150
    if ($process.HasExited) {
        throw "$Name exited during startup. Run it directly to inspect its error."
    }
    # Attach independent log pumps so the caller remains detached.
    $logInfo = @{
        name = $Name
        pid = $process.Id
        started_at = $process.StartTime.ToUniversalTime().ToString("o")
        stdout = $stdout
        stderr = $stderr
    }
    return [pscustomobject]$logInfo
}

function Invoke-Migration {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw "Python environment is missing. Install backend requirements into .venv first."
    }
    $secrets = Get-Secrets
    $previous = $env:DATABASE_URL
    try {
        $env:DATABASE_URL = $secrets.database_url
        Push-Location (Join-Path $Root "backend")
        try {
            & $Python -m alembic upgrade head
        } finally {
            Pop-Location
        }
        if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
    } finally {
        $env:DATABASE_URL = $previous
    }
}

function Wait-Ready([string]$Url, [string]$Name, [int]$Seconds = 30) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    } while ((Get-Date) -lt $deadline)
    throw "$Name did not become ready within $Seconds seconds."
}

function Start-All {
    Initialize-Runtime
    $records = Get-Records
    $live = @($records | Where-Object { Test-RecordOwned $_ })
    if ($live.Count -gt 0) {
        throw "AuthZDiff already has owned processes. Use status or stop first."
    }
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
    Assert-PortsFree
    Invoke-Migration
    if (-not $Node -or -not (Test-Path -LiteralPath $Vite)) {
        throw "Node.js and installed Vite dependencies are required."
    }
    $secrets = Get-Secrets
    $common = @{
        APP_ENV = "development"
        APP_SECRET_KEY = $secrets.app_secret
        FIRST_ADMIN_SETUP_TOKEN = if ($env:AUTHZDIFF_SETUP_TOKEN) { $env:AUTHZDIFF_SETUP_TOKEN } else { $secrets.setup_token }
        ENCRYPTION_MASTER_KEY = $secrets.encryption_key
        DATABASE_URL = $secrets.database_url
        REPORT_STORAGE_PATH = (Join-Path $RuntimeRoot "reports")
        ALLOWED_FRONTEND_ORIGINS = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"
        ALLOWED_HOSTS = "localhost,127.0.0.1"
        APPLICATION_URL = "http://localhost:$BackendPort"
        FRONTEND_URL = "http://localhost:$FrontendPort"
        DEMO_TARGET_URL = "http://127.0.0.1:$DemoPort"
        DEMO_RESET_TOKEN = $secrets.demo_reset_token
        DEMO_MODE = "true"
        FIXTURE_MODE = "true"
        E2E_MODE = if ($env:AUTHZDIFF_E2E_MODE) { $env:AUTHZDIFF_E2E_MODE } else { "false" }
        REPLAY_EXECUTION_MODE = "external"
    }
    $started = @()
    try {
        $demoEnv = @{ APP_ENV = "development"; DEMO_MODE = "true"; DEMO_RESET_TOKEN = $secrets.demo_reset_token }
        $started += Start-OwnedProcess "demo" $Python "-m uvicorn app.main:app --host 127.0.0.1 --port $DemoPort" (Join-Path $Root "demo-target") $demoEnv
        $started += Start-OwnedProcess "backend" $Python "-m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort" (Join-Path $Root "backend") $common
        $started += Start-OwnedProcess "worker" $Python "-m app.worker" (Join-Path $Root "backend") $common
        $started += Start-OwnedProcess "frontend" $Node "`"$Vite`" --host 127.0.0.1 --port $FrontendPort --strictPort" (Join-Path $Root "frontend") @{ VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort" }
        $started | ConvertTo-Json | Set-Content -LiteralPath $PidFile -Encoding utf8
        Wait-Ready "http://127.0.0.1:$DemoPort/ready" "Demo target"
        Wait-Ready "http://127.0.0.1:$BackendPort/api/v1/ready" "Backend"
        Wait-Ready "http://127.0.0.1:$FrontendPort/" "Frontend"
        Write-Output "AuthZDiff is ready: frontend http://localhost:$FrontendPort"
    } catch {
        foreach ($record in $started) {
            if (Test-RecordOwned $record) {
                Stop-Process -Id $record.pid -Force -ErrorAction SilentlyContinue
            }
        }
        throw
    }
}

function Stop-All {
    $records = Get-Records
    foreach ($record in $records) {
        if (Test-RecordOwned $record) {
            Stop-Process -Id $record.pid -Force
            Write-Output "Stopped owned $($record.name) PID $($record.pid)."
        } else {
            Write-Output "Skipped stale or non-owned record for $($record.name)."
        }
    }
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
    Start-Sleep -Milliseconds 300
    foreach ($port in @($BackendPort, $FrontendPort, $DemoPort)) {
        $owner = Get-ListeningOwner $port
        if ($owner) { throw "Port $port remains occupied by PID $owner; it was not terminated." }
    }
}

function Show-Status {
    $records = Get-Records
    if (-not $records.Count) {
        Write-Output "AuthZDiff is stopped."
        return
    }
    $records | ForEach-Object {
        [pscustomobject]@{
            Service = $_.name
            PID = $_.pid
            OwnedAndRunning = Test-RecordOwned $_
        }
    } | Format-Table -AutoSize
}

function Invoke-Health {
    Wait-Ready "http://127.0.0.1:$DemoPort/ready" "Demo target" 5
    Wait-Ready "http://127.0.0.1:$BackendPort/api/v1/ready" "Backend" 5
    Wait-Ready "http://127.0.0.1:$FrontendPort/" "Frontend" 5
    $workerRunning = $false
    foreach ($record in (Get-Records)) {
        if ($record.name -eq "worker" -and (Test-RecordOwned $record)) {
            $workerRunning = $true
        }
    }
    if (-not $workerRunning) { throw "Replay worker is not running." }
    Write-Output "Backend, frontend, demo target, and replay worker are healthy."
}

function Invoke-Seed([switch]$ResetOnly) {
    $secrets = Get-Secrets
    $email = if ($env:AUTHZDIFF_ADMIN_EMAIL) { $env:AUTHZDIFF_ADMIN_EMAIL } else { "admin@authzdiff.local" }
    if (-not $env:AUTHZDIFF_ADMIN_PASSWORD) {
        throw "Set AUTHZDIFF_ADMIN_PASSWORD to a 12-128 character local password."
    }
    $arguments = @(
        (Join-Path $Root "scripts\seed-demo.py"),
        "--base-url", "http://127.0.0.1:$BackendPort",
        "--setup-token", $secrets.setup_token,
        "--email", $email,
        "--password", $env:AUTHZDIFF_ADMIN_PASSWORD
    )
    if ($ResetOnly) { $arguments += "--reset-only" }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Demo seed/reset failed." }
}

switch ($Command) {
    "start" { Start-All }
    "status" { Show-Status }
    "stop" { Stop-All }
    "restart" { Stop-All; Start-All }
    "health" { Invoke-Health }
    "migrate" { Invoke-Migration }
    "seed" { Invoke-Seed }
    "reset" { Invoke-Seed -ResetOnly }
}
