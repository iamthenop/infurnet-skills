#requires -Version 5.1
<#
Platform entry point for Windows PowerShell 5.1 and PowerShell 7+. Accepts
the consuming repository root as an explicit first argument, runs its own
runtime preflight, then delegates installation to install.py unchanged.
Implements no installation semantics of its own.
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

# --- runtime preflight -----------------------------------------------------

if (-not (Test-Path -LiteralPath $ConsumerRoot)) {
    Write-Failure "consumer root does not exist: $ConsumerRoot"
}
if (-not (Test-Path -LiteralPath $ConsumerRoot -PathType Container)) {
    Write-Failure "consumer root is not a directory: $ConsumerRoot"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Failure "git executable not found"
}

$rawCdup = $null
try {
    $rawCdup = (& git -C $ConsumerRoot rev-parse --show-cdup 2>$null)
} catch {
    $rawCdup = $null
}
$cdupExitCode = $LASTEXITCODE
# Coerced through Out-String so a genuinely empty result (the toplevel case)
# reads as "" regardless of whether PowerShell captured no output as $null
# or as an empty string.
$cdup = ($rawCdup | Out-String).Trim()
if ($cdupExitCode -ne 0) {
    Write-Failure "consumer root does not resolve as a Git working tree: $ConsumerRoot"
}
if ($cdup -ne '') {
    Write-Failure "consumer root is not the root of its Git working tree: $ConsumerRoot"
}

$pythonCandidates = @(
    # 'python'/'python3' resolve through PATH, so an activated virtual
    # environment's own interpreter is found first; the 'py' launcher
    # resolves independent of PATH and would otherwise bypass an activated
    # environment in favor of an unrelated system-wide Python.
    @{ Exe = 'python'; Args = @() },
    @{ Exe = 'python3'; Args = @() },
    @{ Exe = 'py'; Args = @('-3') }
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
    Write-Failure "no supported Python interpreter found (requires Python >= 3.12; tried: python, python3, py -3)"
}

# --- dependency preflight ---------------------------------------------------
#
# Confirms the selected interpreter can import the installer's bundled
# runtime dependencies. Never installs anything; a missing dependency is a
# preflight failure naming scripts/requirements.txt.

$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
& $selected.Exe @($selected.Args) -c "import yaml, markdown_it, ruamel.yaml" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Failure ("missing installer runtime dependency; install with: " +
        "pip install -r `"$requirementsPath`" (in an isolated virtual environment)")
}

# --- delegate ---------------------------------------------------------------

$installPy = Join-Path $PSScriptRoot "install.py"
& $selected.Exe @($selected.Args) $installPy --root $ConsumerRoot @InstallerArgs
exit $LASTEXITCODE
