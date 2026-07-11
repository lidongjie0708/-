param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("likes", "blogs", "rag", "analytics", "mixed")]
    [string]$Script,

    [string]$JavaBase = "http://host.docker.internal:9199/api",
    [string]$AgentBase = "http://host.docker.internal:8081",
    [int]$Vus = 10,
    [int]$Users = 0,
    [int]$Blogs = 0,
    [string]$RampUp = "",
    [string]$Hold = "1m",
    [string]$RampDown = "",
    [string]$ThinkSeconds = "0.2",
    [string]$Label = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$runName = if ($Label) { "$timestamp-$Script-$Label" } else { "$timestamp-$Script" }
$reportDir = Join-Path $root "reports\k6\$runName"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$summaryPath = "reports/k6/$runName/summary.json"
$textPath = Join-Path $reportDir "console.txt"
$metaPath = Join-Path $reportDir "meta.json"

$envArgs = @(
    "-e", "JAVA_BASE=$JavaBase",
    "-e", "AGENT_BASE=$AgentBase",
    "-e", "VUS=$Vus",
    "-e", "HOLD=$Hold",
    "-e", "THINK_SECONDS=$ThinkSeconds"
)

if ($Users -gt 0) { $envArgs += @("-e", "USERS=$Users") }
if ($Blogs -gt 0) { $envArgs += @("-e", "BLOGS=$Blogs", "-e", "SEED_BLOGS=$Blogs") }
if ($RampUp) { $envArgs += @("-e", "RAMP_UP=$RampUp") }
if ($RampDown) { $envArgs += @("-e", "RAMP_DOWN=$RampDown") }

$metadata = [ordered]@{
    runName = $runName
    startedAt = (Get-Date).ToString("o")
    script = "$Script.js"
    javaBase = $JavaBase
    agentBase = $AgentBase
    vus = $Vus
    users = $Users
    blogs = $Blogs
    rampUp = $RampUp
    hold = $Hold
    rampDown = $RampDown
    thinkSeconds = $ThinkSeconds
    summary = $summaryPath
    console = "reports/k6/$runName/console.txt"
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $metaPath

Write-Host "Writing k6 reports to $reportDir"

& docker run --rm `
    @envArgs `
    -v "${root}:/work" `
    -w /work `
    grafana/k6 run `
    --summary-export $summaryPath `
    "load-tests/k6/$Script.js" 2>&1 | Tee-Object -FilePath $textPath

exit $LASTEXITCODE
