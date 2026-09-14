#requires -Version 5.1
<#
Platform entry point for Windows PowerShell 5.1 and PowerShell 7+. Accepts
the consuming repository root as an explicit first argument, runs runtime
preflight, then delegates installation to install.py unchanged. Implements
no installation semantics of its own.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ConsumerRoot,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InstallerArgs
)

$ErrorActionPreference = 'Stop'

function Write-Failure([string]$Message) {
    [Console]::Error.WriteLine("install.ps1: $Message")
    exit 1
}

if (-not $InstallerArgs) { $InstallerArgs = @() }

foreach ($arg in $InstallerArgs) {
    if ($arg -eq '--root' -or $arg.StartsWith('--root=')) {
        Write-Failure "--root is supplied positionally as <ConsumerRoot>; do not pass it again"
    }
}

$ScriptDir = $PSScriptRoot

& (Join-Path $ScriptDir "check-runtime.ps1") $ConsumerRoot | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Failure "runtime preflight failed"
}

$pythonCandidates = @(
    @{ Exe = 'py'; Args = @('-3') },
    @{ Exe = 'python'; Args = @() },
    @{ Exe = 'python3'; Args = @() }
)
$selected = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    & $candidate.Exe @($candidate.Args) -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $selected = $candidate
        break
    }
}
if (-not $selected) {
    Write-Failure "no supported Python interpreter found (requires Python >= 3.12; tried: py -3, python, python3)"
}

$installPy = Join-Path $ScriptDir "install.py"
& $selected.Exe @($selected.Args) $installPy --root $ConsumerRoot @InstallerArgs
exit $LASTEXITCODE
