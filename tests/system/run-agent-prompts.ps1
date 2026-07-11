param(
    [string]$AgentBaseUrl = $(if ($env:AGENT_BASE_URL) { $env:AGENT_BASE_URL } else { "http://127.0.0.1:8001/api/agent" }),
    [string]$AgentToken = $env:AGENT_TOKEN,
    [ValidateSet("USER", "ADMIN")][string]$Role = "USER",
    [string]$Dataset = "$PSScriptRoot\agent-prompts.jsonl",
    [string]$Output = "$PSScriptRoot\agent-results.json"
)

$ErrorActionPreference = "Stop"
if (-not $AgentToken) { throw "Set AGENT_TOKEN before running the prompt evaluation." }

$headers = @{ Authorization = "Bearer $AgentToken" }
$cases = Get-Content $Dataset -Encoding utf8 | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }
$results = @()

foreach ($case in $cases) {
    if ($case.requiredRole -and $case.requiredRole -ne $Role) {
        Write-Host "[SKIP] $($case.id) requires $($case.requiredRole)" -ForegroundColor DarkGray
        continue
    }
    $started = Get-Date
    try {
        $response = Invoke-RestMethod -Method POST -Uri "$AgentBaseUrl/chat" -Headers $headers `
            -ContentType "application/json; charset=utf-8" -TimeoutSec 90 `
            -Body (@{
                message = $case.prompt
                mode = $case.mode
                sessionId = "eval-$($case.id)"
            } | ConvertTo-Json)
        $actualMode = $response.data.mode
        $passed = $response.code -eq 0 -and $actualMode -eq $case.expectedMode
        $results += [pscustomobject]@{
            id = $case.id
            passed = $passed
            expectedMode = $case.expectedMode
            actualMode = $actualMode
            latencyMs = [int]((Get-Date) - $started).TotalMilliseconds
            routeReason = $response.data.routeReason
            routeConfidence = $response.data.routeConfidence
            needsClarification = $response.data.needsClarification
            assertions = $case.assertions
            answer = $response.data.answer
            error = $response.error
        }
        Write-Host "[$(if($passed){'PASS'}else{'FAIL'})] $($case.id): $actualMode" `
            -ForegroundColor $(if ($passed) { "Green" } else { "Red" })
    }
    catch {
        $results += [pscustomobject]@{
            id = $case.id
            passed = $false
            expectedMode = $case.expectedMode
            actualMode = $null
            latencyMs = [int]((Get-Date) - $started).TotalMilliseconds
            error = $_.Exception.Message
        }
        Write-Host "[ERROR] $($case.id): $($_.Exception.Message)" -ForegroundColor Red
    }
}

$results | ConvertTo-Json -Depth 10 | Set-Content $Output -Encoding utf8
$executed = @($results).Count
$passedCount = @($results | Where-Object passed).Count
Write-Host "Completed: $passedCount/$executed mode checks passed. Results: $Output" -ForegroundColor Cyan
if ($passedCount -ne $executed) { exit 1 }
