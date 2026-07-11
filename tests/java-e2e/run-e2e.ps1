param(
    [string]$AgentBaseUrl = "http://127.0.0.1:8001",
    [switch]$KeepInfrastructure
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."
$compose = Join-Path $PSScriptRoot "docker-compose.yml"

try {
    $agentHealth = Invoke-WebRequest -Uri "$AgentBaseUrl/docs" -UseBasicParsing -TimeoutSec 5
    if ($agentHealth.StatusCode -ne 200) { throw "Python Agent is not ready." }

    docker compose -f $compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw "Failed to start E2E infrastructure." }

    $env:JAVA_E2E_ENABLED = "true"
    $env:E2E_DB_URL = "jdbc:mysql://127.0.0.1:13306/thumb_e2e?useSSL=false&allowPublicKeyRetrieval=true"
    $env:E2E_DB_PASSWORD = "e2e_root"
    $env:E2E_AGENT_BASE_URL = $AgentBaseUrl
    $env:JAVA_HOME = "D:\jdk17"
    $env:Path = "D:\jdk17\bin;" + $env:Path

    Push-Location $root
    try {
        mvn -Dtest=JavaFullChainE2ETest test
        if ($LASTEXITCODE -ne 0) { throw "Java full-chain E2E test failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if (-not $KeepInfrastructure) {
        docker compose -f $compose down -v
    }
}
