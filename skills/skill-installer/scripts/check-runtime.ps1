#requires -Version 5.1
<#
Runtime preflight for skill-installer under Windows PowerShell 5.1 and
PowerShell 7+. Verifies a supported Python, a usable Git, and that the
supplied path is the actual root of its Git working tree, then classifies
the consumer as bootstrap or managed by installation-manifest presence
alone. Prints exactly one state line to stdout on success; diagnostics go
to stderr. Non-mutating.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ConsumerRoot
)

$ErrorActionPreference = 'Stop'

function Write-Failure([string]$Message) {
    [Console]::Error.WriteLine("check-runtime: $Message")
    exit 1
}

function Test-EntryExists([string]$Path) {
    # True for any filesystem entry at Path, including a broken symlink —
    # File/Directory ::Exists resolve reparse points and miss those, so a
    # raw parent-directory listing is the fallback.
    if ([System.IO.File]::Exists($Path)) { return $true }
    if ([System.IO.Directory]::Exists($Path)) { return $true }
    $parent = Split-Path -Path $Path -Parent
    $name = Split-Path -Path $Path -Leaf
    if ([System.IO.Directory]::Exists($parent)) {
        foreach ($entry in [System.IO.Directory]::GetFileSystemEntries($parent)) {
            if ((Split-Path -Path $entry -Leaf) -eq $name) { return $true }
        }
    }
    return $false
}

if (-not (Test-Path -LiteralPath $ConsumerRoot)) {
    Write-Failure "consumer root does not exist: $ConsumerRoot"
}
if (-not (Test-Path -LiteralPath $ConsumerRoot -PathType Container)) {
    Write-Failure "consumer root is not a directory: $ConsumerRoot"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Failure "git executable not found"
}

$toplevel = $null
try {
    $toplevel = (& git -C $ConsumerRoot rev-parse --show-toplevel 2>$null)
} catch {
    $toplevel = $null
}
if ($LASTEXITCODE -ne 0 -or -not $toplevel) {
    Write-Failure "consumer root does not resolve as a Git working tree: $ConsumerRoot"
}

$resolvedRoot = (Resolve-Path -LiteralPath $ConsumerRoot).ProviderPath.TrimEnd('\', '/')
$resolvedTop = (Resolve-Path -LiteralPath $toplevel).ProviderPath.TrimEnd('\', '/')
if ($resolvedRoot -ne $resolvedTop) {
    Write-Failure "consumer root is not the root of its Git working tree: $ConsumerRoot (root is $toplevel)"
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

$manifestPath = Join-Path (Join-Path $ConsumerRoot ".agents") "infurnet-skills.manifest.json"
if (Test-EntryExists $manifestPath) {
    Write-Output "state=managed"
} else {
    Write-Output "state=bootstrap"
}
