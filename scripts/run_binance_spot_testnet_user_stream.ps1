param(
    [Parameter(Mandatory = $true)]
    [string]$Output
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Script = Join-Path $PSScriptRoot "check_binance_spot_testnet_user_stream.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Aurex virtual environment Python was not found at $Python"
}

Write-Host "This may place and cancel two resting Binance Spot Testnet BUY orders."
Write-Host "Each order is capped at USD 10. All assets are virtual."
Write-Host "This does not enable production, live trading, or real capital."
$Acknowledgement = Read-Host "Type I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET USER STREAM CAMPAIGN to continue"
if ($Acknowledgement -cne "I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET USER STREAM CAMPAIGN") {
    throw "Exact Testnet user-stream acknowledgement was not supplied."
}

$SecureApiKey = Read-Host "Binance Spot Testnet API key (hidden)" -AsSecureString
$SecureSecret = Read-Host "Binance Spot Testnet secret key (hidden)" -AsSecureString
$ApiKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureApiKey)
$SecretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureSecret)

try {
    $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ApiKeyPointer)
    $Secret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($SecretPointer)
    $env:AUREX_BINANCE_TESTNET_API_KEY = $ApiKey
    $env:AUREX_BINANCE_TESTNET_SECRET_KEY = $Secret
    & $Python $Script `
        --acknowledgement $Acknowledgement `
        --output $Output
    $ChildExitCode = $LASTEXITCODE
}
finally {
    Remove-Item Env:AUREX_BINANCE_TESTNET_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:AUREX_BINANCE_TESTNET_SECRET_KEY -ErrorAction SilentlyContinue
    if ($ApiKeyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ApiKeyPointer)
    }
    if ($SecretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($SecretPointer)
    }
    $Secret = $null
    $ApiKey = $null
    $SecureApiKey = $null
    $SecureSecret = $null
}

exit $ChildExitCode
