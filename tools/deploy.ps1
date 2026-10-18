param(
    [Parameter(Mandatory=$true)][string]$RunDir,
    [Parameter(Mandatory=$true)][string]$ArtifactBucket,
    [ValidateSet('us-east-1','us-west-2')][string]$Region = 'us-east-1',
    [ValidatePattern('^[a-z][a-z0-9-]{2,25}$')][string]$Prefix = 'textract-full',
    [ValidatePattern('^[0-9]{12}$')][string]$ExpectedAccount = '535709085695',
    [string]$Owner = '24110372-24110381',
    [string]$Email = '',
    [ValidateSet('ENABLED','DISABLED')][string]$PollingState = 'ENABLED'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install dependencies first; see README.md.' }
$taskArguments = @((Join-Path $PSScriptRoot 'deploy.py'), '--run-dir', $RunDir,
    '--artifact-bucket', $ArtifactBucket, '--region', $Region, '--prefix', $Prefix,
    '--expected-account', $ExpectedAccount, '--owner', $Owner, '--polling-state', $PollingState)
if ($Email) { $taskArguments += @('--email', $Email) }
& $pythonPath @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Deployment stopped; inspect the run manifest. Package was not rebuilt.' }
