[CmdletBinding()]
param(
    [ValidateSet("start", "status", "stop", "restart", "health")]
    [string]$Command = "status",
    [int]$BackendPort = 8020,
    [int]$FrontendPort = 4174
)
$ErrorActionPreference = "Stop"
$TaskRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskPython = Join-Path $TaskRoot ".venv\Scripts\python.exe"
$TaskNode = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
$TaskVite = Join-Path $TaskRoot "frontend\node_modules\vite\bin\vite.js"
$TaskRuntime = Join-Path $TaskRoot "var\runtime"
$TaskPidFile = Join-Path $TaskRuntime "processes.json"

function Get-Records {
    if (-not (Test-Path -LiteralPath $TaskPidFile)) { return @() }
    return @(Get-Content -LiteralPath $TaskPidFile -Raw | ConvertFrom-Json)
}
function Test-Owned($Record) {
    $taskProcess = Get-Process -Id $Record.pid -ErrorAction SilentlyContinue
    if (-not $taskProcess) { return $false }
    $taskStart = if ($Record.started_at -is [datetime]) {
        $Record.started_at.ToUniversalTime().ToString("o")
    } else { [string]$Record.started_at }
    return $taskProcess.StartTime.ToUniversalTime().ToString("o") -eq $taskStart
}
function Wait-Ready([string]$Url) {
    $taskDeadline = (Get-Date).AddSeconds(30)
    do {
        try {
            $taskResponse = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($taskResponse.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 250 }
    } while ((Get-Date) -lt $taskDeadline)
    throw "Service did not become ready: $Url"
}
function Stop-All {
    foreach ($taskRecord in (Get-Records)) {
        if (Test-Owned $taskRecord) { Stop-Process -Id $taskRecord.pid -Force }
    }
    if (Test-Path -LiteralPath $TaskPidFile) { Remove-Item -LiteralPath $TaskPidFile -Force }
}
function Start-All {
    if (@(Get-Records | Where-Object { Test-Owned $_ }).Count) {
        throw "AuthZDiff is already running. Use status or stop."
    }
    if (-not (Test-Path -LiteralPath $TaskPython) -or -not $TaskNode -or -not (Test-Path -LiteralPath $TaskVite)) {
        throw "Install the .venv backend and frontend npm dependencies first."
    }
    foreach ($taskPort in @($BackendPort, $FrontendPort)) {
        if (Get-NetTCPConnection -State Listen -LocalPort $taskPort -ErrorAction SilentlyContinue) {
            throw "Port $taskPort is occupied; no existing process will be terminated."
        }
    }
    New-Item -ItemType Directory -Force -Path $TaskRuntime | Out-Null
    $taskStarted = @()
    $taskPrevious = @{}
    $taskEnvironment = @{
        VITE_API_PROXY_TARGET = "http://127.0.0.1:$BackendPort"
        ALLOWED_HOSTS = "localhost,127.0.0.1"
        ALLOWED_FRONTEND_ORIGINS = "http://localhost:$FrontendPort,http://127.0.0.1:$FrontendPort"
        PYTHONDONTWRITEBYTECODE = "1"
    }
    try {
        foreach ($taskEntry in $taskEnvironment.GetEnumerator()) {
            $taskPrevious[$taskEntry.Key] = [Environment]::GetEnvironmentVariable($taskEntry.Key, "Process")
            [Environment]::SetEnvironmentVariable($taskEntry.Key, $taskEntry.Value, "Process")
        }
        $taskServices = @(
            @{ name = "backend"; executable = $TaskPython; arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --no-access-log"; directory = (Join-Path $TaskRoot "backend") },
            @{ name = "frontend"; executable = $TaskNode; arguments = "`"$TaskVite`" --host 127.0.0.1 --port $FrontendPort --strictPort"; directory = (Join-Path $TaskRoot "frontend") }
        )
        foreach ($taskService in $taskServices) {
            $taskProcess = Start-Process -FilePath $taskService.executable -ArgumentList $taskService.arguments -WorkingDirectory $taskService.directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $TaskRuntime "$($taskService.name).stdout.log") -RedirectStandardError (Join-Path $TaskRuntime "$($taskService.name).stderr.log") -PassThru
            $taskStarted += [pscustomobject]@{ name = $taskService.name; pid = $taskProcess.Id; started_at = $taskProcess.StartTime.ToUniversalTime().ToString("o") }
        }
        $taskStarted | ConvertTo-Json | Set-Content -LiteralPath $TaskPidFile -Encoding utf8
        Wait-Ready "http://127.0.0.1:$BackendPort/api/v1/ready"
        Wait-Ready "http://127.0.0.1:$FrontendPort/"
        Write-Output "AuthZDiff is ready: http://localhost:$FrontendPort"
    } catch {
        foreach ($taskRecord in $taskStarted) {
            if (Test-Owned $taskRecord) { Stop-Process -Id $taskRecord.pid -Force -ErrorAction SilentlyContinue }
        }
        if (Test-Path -LiteralPath $TaskPidFile) { Remove-Item -LiteralPath $TaskPidFile -Force }
        throw
    } finally {
        foreach ($taskEntry in $taskEnvironment.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($taskEntry.Key, $taskPrevious[$taskEntry.Key], "Process")
        }
    }
}
switch ($Command) {
    "start" { Start-All }
    "stop" { Stop-All }
    "restart" { Stop-All; Start-All }
    "status" { Get-Records | ForEach-Object { [pscustomobject]@{ Service = $_.name; PID = $_.pid; Running = Test-Owned $_ } } | Format-Table }
    "health" { Wait-Ready "http://127.0.0.1:$BackendPort/api/v1/ready"; Wait-Ready "http://127.0.0.1:$FrontendPort/"; Write-Output "Backend and frontend are healthy." }
}
