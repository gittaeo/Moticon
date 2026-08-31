$ErrorActionPreference = "Stop"
$secure = Read-Host "Kakao Developers REST API 키를 붙여넣고 Enter" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim()
  if ($key.Length -lt 20) { throw "REST API 키가 너무 짧습니다." }
  $envPath = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
  $lines = if (Test-Path -LiteralPath $envPath) { @(Get-Content -LiteralPath $envPath -Encoding UTF8) } else { @() }
  $updated = $false
  $result = foreach ($line in $lines) {
    if ($line -match '^KAKAO_REST_API_KEY=') { $updated = $true; "KAKAO_REST_API_KEY=$key" } else { $line }
  }
  if (-not $updated) { $result += "KAKAO_REST_API_KEY=$key" }
  Set-Content -LiteralPath $envPath -Value $result -Encoding UTF8
  Write-Host "Kakao REST API 키를 .env에 안전하게 저장했습니다. npm.cmd run backend 로 서버를 다시 시작하세요." -ForegroundColor Green
} finally {
  if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  $key = $null
}
