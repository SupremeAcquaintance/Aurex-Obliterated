param(
    [string]$Output = "data\evidence\binance_spot_testnet_restart_soak_latest.json",
    [string]$State = "data\evidence\binance_spot_testnet_restart_soak_state.json",
    [string]$Contract = "data\evidence\binance_spot_testnet_restart_soak_contract_v1.json"
)

$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$Runner = Join-Path $PSScriptRoot "check_binance_spot_testnet_restart_soak.py"
$Acknowledgement = "I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET RESTART AND SOAK CAMPAIGN"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Aurex virtual environment was not found at $Python"
}
if (Test-Path -LiteralPath $Output) {
    throw "Restart-soak evidence already exists at $Output"
}
if (Test-Path -LiteralPath $State) {
    throw "Restart-soak state already exists at $State. Inspect it before any new campaign."
}

$ApiKey = Read-Host "Binance Spot Testnet API key"
$Secret = Read-Host "Binance Spot Testnet secret key" -AsSecureString
$SecretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
try {
    $env:AUREX_BINANCE_TESTNET_API_KEY = $ApiKey
    $env:AUREX_BINANCE_TESTNET_SECRET_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        $SecretPointer
    )
    & $Python $Runner --stage prepare --acknowledgement $Acknowledgement --contract $Contract --state $State --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Phase 2D prepare process failed." }

    & $Python $Runner --stage recover --acknowledgement $Acknowledgement --contract $Contract --state $State --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Phase 2D recovery process failed." }

    Write-Host "Phase 2D recovery passed. Beginning the frozen 10-minute kill-stop soak."
    & $Python $Runner --stage soak --acknowledgement $Acknowledgement --contract $Contract --state $State --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Phase 2D soak process failed." }
}
finally {
    $env:AUREX_BINANCE_TESTNET_API_KEY = $null
    $env:AUREX_BINANCE_TESTNET_SECRET_KEY = $null
    if ($SecretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($SecretPointer)
    }
    $ApiKey = $null
    $Secret = $null
}
