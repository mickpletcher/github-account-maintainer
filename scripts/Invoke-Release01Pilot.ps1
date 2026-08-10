[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$Config,

    [ValidateRange(2, 5)]
    [int]$Repeat = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Uv {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & uv @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "uv command failed with exit code $LASTEXITCODE"
    }
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$resolvedConfig = (Resolve-Path -LiteralPath $Config).Path
$pilotExitCode = 0

Push-Location $repositoryRoot
try {
    Invoke-Uv -Arguments @('sync', '--locked', '--dev')
    Invoke-Uv -Arguments @('lock', '--check')
    Invoke-Uv -Arguments @('run', 'ruff', 'check', '.')
    Invoke-Uv -Arguments @('run', 'ruff', 'format', '--check', '.')
    Invoke-Uv -Arguments @('run', 'pyright')
    Invoke-Uv -Arguments @('run', 'pytest')
    $pilotArguments = @(
        'run',
        'python',
        '-m',
        'github_account_maintainer.pilot',
        '--config',
        $resolvedConfig,
        '--repeat',
        $Repeat.ToString(),
        '--format',
        'markdown'
    )
    & uv @pilotArguments
    $pilotExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $pilotExitCode
