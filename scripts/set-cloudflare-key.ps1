$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $projectRoot ".env"

Write-Host "Cloudflare Dashboard > AI > Workers AI > Use REST API에서 값을 복사하세요." -ForegroundColor Cyan
Write-Host "토큰 권한: Account > Workers AI > Read, Workers AI > Edit" -ForegroundColor DarkGray

$accountId = (Read-Host "Cloudflare Account ID를 붙여넣고 Enter").Trim()
if ($accountId -notmatch '^[a-fA-F0-9]{32}$') {
  throw "Account ID는 보통 32자리 영문/숫자 값입니다. 다시 확인하세요."
}

$secure = Read-Host "Workers AI API Token을 붙여넣고 Enter (화면에 표시되지 않음)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr).Trim()
  if ($token.Length -lt 20) { throw "API Token이 너무 짧습니다." }

  Write-Host "Workers AI 권한을 확인하고 있습니다..." -ForegroundColor Yellow
  $headers = @{ Authorization = "Bearer $token" }
  $checkUrl = "https://api.cloudflare.com/client/v4/accounts/$accountId/ai/models/search?search=flux-2-klein-4b"
  try {
    $check = Invoke-RestMethod -Method Get -Uri $checkUrl -Headers $headers -TimeoutSec 20
  } catch {
    throw "Cloudflare 인증에 실패했습니다. Account ID와 Workers AI Read/Edit 권한을 확인하세요. ($($_.Exception.Message))"
  }
  if (-not $check.success) { throw "Cloudflare가 Workers AI 인증을 승인하지 않았습니다." }

  $lines = if (Test-Path -LiteralPath $envPath) { @(Get-Content -LiteralPath $envPath -Encoding UTF8) } else { @() }
  $values = [ordered]@{
    CLOUDFLARE_ACCOUNT_ID = $accountId
    CLOUDFLARE_API_TOKEN = $token
    CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
    CLOUDFLARE_FREE_PLAN_CONFIRMED = "true"
  }
  $seen = @{}
  $result = foreach ($line in $lines) {
    $clean = $line.TrimStart([char]0xFEFF)
    $matched = $false
    foreach ($name in $values.Keys) {
      if ($clean -match "^$name=") {
        if (-not $seen[$name]) { "$name=$($values[$name])"; $seen[$name] = $true }
        $matched = $true
        break
      }
    }
    if (-not $matched) { $line }
  }
  foreach ($name in $values.Keys) {
    if (-not $seen[$name]) { $result = @($result) + "$name=$($values[$name])" }
  }
  Set-Content -LiteralPath $envPath -Value $result -Encoding UTF8

  Write-Host "Workers AI 연결 확인 완료: FLUX.2 Klein 4B (Free allocation only)" -ForegroundColor Green
  Write-Host "이제 npm.cmd run backend 로 백엔드를 다시 시작하세요." -ForegroundColor Green
} finally {
  if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  $token = $null
}
