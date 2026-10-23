param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "health", "seed", "demo-reset")]
    [string]$Command
)

python "$PSScriptRoot/adpathlens.py" $Command
exit $LASTEXITCODE
