param(
    [ValidateSet("public", "authenticated", "test-order", "virtual-cancel")]
    [string]$Mode = "public",
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$checker = Join-Path $PSScriptRoot "check_binance_spot_testnet.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Aurex virtual environment is missing. Run the repository setup first."
}

$arguments = @($checker, "--mode", $Mode)
if ($Output) {
    $arguments += @("--output", $Output)
}

if ($Mode -eq "public") {
    & $python @arguments
    exit $LASTEXITCODE
}

if ($Mode -eq "virtual-cancel") {
    Write-Host "This will submit and cancel one bounded order using virtual Testnet funds."
    $acknowledgement = Read-Host "Type VIRTUAL FUNDS ONLY to continue"
    if ($acknowledgement -cne "VIRTUAL FUNDS ONLY") {
        throw "Exact Testnet virtual-order acknowledgement was not supplied."
    }
    $arguments += "--acknowledge-testnet-virtual-order"
}

$secureApiKey = Read-Host "Binance Spot Testnet API key (hidden)" -AsSecureString
$secureSecret = Read-Host "Binance Spot Testnet secret key (hidden)" -AsSecureString
$apiKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureApiKey)
$secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureSecret)

try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($apiKeyPointer)
    $secret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
    $env:AUREX_BINANCE_TESTNET_API_KEY = $apiKey
    $env:AUREX_BINANCE_TESTNET_SECRET_KEY = $secret
    & $python @arguments
    $childExitCode = $LASTEXITCODE
}
finally {
    Remove-Item Env:AUREX_BINANCE_TESTNET_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:AUREX_BINANCE_TESTNET_SECRET_KEY -ErrorAction SilentlyContinue
    if ($apiKeyPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($apiKeyPointer)
    }
    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    $secret = $null
    $apiKey = $null
    $secureApiKey = $null
    $secureSecret = $null
}

exit $childExitCode
