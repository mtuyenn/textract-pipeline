param(
    [string]$Stack = 'textract-full',
    [ValidateSet('us-east-1','us-west-2')][string]$Region = 'us-east-1',
    [string]$RunDir,
    [switch]$PurgeData
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$arguments = @((Join-Path $PSScriptRoot 'cleanup_aws.py'), '--stack', $Stack, '--region', $Region)
if ($RunDir) { $arguments += @('--run-dir', $RunDir) }
if ($PurgeData) { $arguments += '--purge-data' }
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) { throw 'Cleanup stopped; inspect output. No permission restrictions are bypassed.' }
