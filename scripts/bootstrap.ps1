param(
    [switch]$Dev,
    [switch]$Exchange,
    [switch]$Ibkr,
    [switch]$NoSubmodules,
    [switch]$NoPipUpgrade,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Arguments = @()
if ($Dev) { $Arguments += "--dev" }
if ($Exchange) { $Arguments += "--exchange" }
if ($Ibkr) { $Arguments += "--ibkr" }
if ($NoSubmodules) { $Arguments += "--no-submodules" }
if ($NoPipUpgrade) { $Arguments += "--no-pip-upgrade" }
$Arguments += @("--python", $Python)

& $Python "$PSScriptRoot\bootstrap.py" @Arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
