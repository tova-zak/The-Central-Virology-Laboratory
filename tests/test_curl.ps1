# Test Gemini API with curl
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"

Write-Host "Reading .env from: $envFile" -ForegroundColor Gray

if (-not (Test-Path $envFile)) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    exit 1
}

$apiKey = (Get-Content $envFile -Raw | Select-String "GEMINI_API_KEY=(.+)" -AllMatches).Matches.Groups[1].Value.Trim()

if (-not $apiKey) {
    Write-Host "ERROR: GEMINI_API_KEY not found in .env" -ForegroundColor Red
    exit 1
}

Write-Host "API Key loaded successfully" -ForegroundColor Green

$url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=$apiKey"

$body = @'
{
  "contents": [{
    "parts": [{
      "text": "Say OK"
    }]
  }]
}
'@

Write-Host "Testing Gemini API with curl..." -ForegroundColor Cyan
Write-Host "Model: gemini-3.5-flash-lite" -ForegroundColor Gray
Write-Host "Timeout: 20 seconds" -ForegroundColor Gray
Write-Host ""

$bodyFile = "$env:TEMP\gemini_test.json"
$body | Out-File -FilePath $bodyFile -Encoding utf8 -NoNewline

# Sanitize output: never print URLs with keys
$result = curl.exe -4 -X POST `
    -H "Content-Type: application/json" `
    -H "x-goog-api-key: $apiKey" `
    --data-binary "@$bodyFile" `
    --connect-timeout 15 `
    --max-time 20 `
    -w "\nStatus: %{http_code}\nTime: %{time_total}s\n" `
    $baseUrl 2>&1

Remove-Item $bodyFile -ErrorAction SilentlyContinue

# Check for success without exposing key
if ($result -match "Status: 200") {
    Write-Host "SUCCESS!" -ForegroundColor Green
    # Filter output to remove any accidental key exposure
    $result | Where-Object { $_ -notmatch $apiKey }
} else {
    Write-Host "FAILED" -ForegroundColor Red
    $result | Where-Object { $_ -notmatch $apiKey }
}
