param(
    [string]$ApiBaseUrl = $(if ($env:API_BASE_URL) { $env:API_BASE_URL } else { "http://127.0.0.1:9199/api" }),
    [string]$AgentBaseUrl = $(if ($env:AGENT_BASE_URL) { $env:AGENT_BASE_URL } else { "http://127.0.0.1:8001/api/agent" }),
    [string]$Username = $env:TEST_USERNAME,
    [string]$Password = $env:TEST_PASSWORD
)

$ErrorActionPreference = "Stop"
$createdBlogId = $null
$commentId = $null
$replyId = $null

function Assert-BusinessSuccess($response, [string]$name) {
    if ($null -eq $response -or $response.code -ne 0) {
        throw "$name failed: $($response | ConvertTo-Json -Depth 8 -Compress)"
    }
    Write-Host "[PASS] $name" -ForegroundColor Green
}

function Invoke-Json([string]$Method, [string]$Url, $Body = $null, [hashtable]$Headers = @{}) {
    $params = @{ Method = $Method; Uri = $Url; Headers = $Headers; TimeoutSec = 30 }
    if ($null -ne $Body) {
        $params.ContentType = "application/json; charset=utf-8"
        $params.Body = $Body | ConvertTo-Json -Depth 10
    }
    Invoke-RestMethod @params
}

try {
    $publicBlogs = Invoke-Json GET "$ApiBaseUrl/blog/all"
    Assert-BusinessSuccess $publicBlogs "public blog list"

    if (-not $Username -or -not $Password) {
        throw "Set TEST_USERNAME and TEST_PASSWORD before authenticated smoke testing."
    }

    $login = Invoke-Json POST "$ApiBaseUrl/login" @{ username = $Username; password = $Password }
    Assert-BusinessSuccess $login "login"
    $auth = @{ Authorization = "Bearer $($login.data.token)" }

    $profile = Invoke-Json GET "$ApiBaseUrl/user/profile" $null $auth
    Assert-BusinessSuccess $profile "get profile"
    $profileRoundTrip = Invoke-Json PUT "$ApiBaseUrl/user/profile" @{
        email = $profile.data.email
        fullName = $profile.data.fullName
    } $auth
    Assert-BusinessSuccess $profileRoundTrip "update profile round trip"

    $suffix = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $blog = Invoke-Json POST "$ApiBaseUrl/blog/create" @{
        title = "Smoke Test $suffix"
        content = "# Smoke Test`n`nThis article is created by the automated smoke test."
        contentFormat = "MARKDOWN"
    } $auth
    Assert-BusinessSuccess $blog "create markdown blog"
    $createdBlogId = $blog.data.id

    $detail = Invoke-Json GET "$ApiBaseUrl/blog/$createdBlogId"
    Assert-BusinessSuccess $detail "blog detail"
    if ($detail.data.contentFormat -ne "MARKDOWN") { throw "contentFormat was not persisted" }

    $comment = Invoke-Json POST "$ApiBaseUrl/comment" @{
        blogId = "$createdBlogId"
        content = "smoke root comment"
    } $auth
    Assert-BusinessSuccess $comment "create comment"
    $commentId = $comment.data.id

    $reply = Invoke-Json POST "$ApiBaseUrl/comment/$commentId/replies" @{
        content = "smoke reply"
    } $auth
    Assert-BusinessSuccess $reply "create reply"
    $replyId = $reply.data.id

    Assert-BusinessSuccess (Invoke-Json POST "$ApiBaseUrl/thumb/do" @{ blogId = "$createdBlogId" } $auth) "thumb"
    Assert-BusinessSuccess (Invoke-Json POST "$ApiBaseUrl/thumb/undo" @{ blogId = "$createdBlogId" } $auth) "undo thumb"

    $agentToken = Invoke-Json POST "$ApiBaseUrl/agent/token" $null $auth
    Assert-BusinessSuccess $agentToken "create agent token"
    $agentAuth = @{ Authorization = "Bearer $($agentToken.data.token)" }
    $chat = Invoke-Json POST "$AgentBaseUrl/chat" @{
        message = "解释一下这个博客系统的主要功能"
        mode = "chat"
        sessionId = "smoke-$suffix"
    } $agentAuth
    Assert-BusinessSuccess $chat "agent chat"

    Write-Host "Smoke test completed successfully." -ForegroundColor Cyan
}
finally {
    if ($replyId) {
        try { Invoke-Json DELETE "$ApiBaseUrl/comment/$replyId" $null $auth | Out-Null } catch {}
    }
    if ($commentId) {
        try { Invoke-Json DELETE "$ApiBaseUrl/comment/$commentId" $null $auth | Out-Null } catch {}
    }
    if ($createdBlogId) {
        try { Invoke-Json DELETE "$ApiBaseUrl/blog/$createdBlogId" $null $auth | Out-Null } catch {}
    }
}
