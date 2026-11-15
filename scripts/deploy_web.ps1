<#
.SYNOPSIS
  Build the phone app and deploy it to Cloudflare Pages (project armrest-app).

.DESCRIPTION
  Production deploy: phones load https://armrest-app.pages.dev, so this changes what every user gets.
  Refuses to run with uncommitted changes under web-remote/ (the live app should always match a commit),
  unless -AllowDirty is passed. Log in once first with: npx wrangler login

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy_web.ps1
#>
param(
    [string]$RelayUrl = "wss://ltqv0kbaoc.execute-api.us-east-2.amazonaws.com/prod",
    [string]$Project = "armrest-app",
    [string]$Branch = "main",
    [switch]$AllowDirty,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$web = Join-Path $repo "web-remote"

function Invoke-Step([string]$label, [scriptblock]$block) {
    Write-Host "==> $label" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$label failed (exit $LASTEXITCODE)" }
}

Push-Location $repo
try {
    $dirty = git status --porcelain -- web-remote
    if ($dirty -and -not $AllowDirty) {
        Write-Host $dirty
        throw "web-remote/ has uncommitted changes. Commit them first, or pass -AllowDirty."
    }
    $dirtyFlag = if ($dirty) { "true" } else { "false" }
    $commit = (git rev-parse --short HEAD).Trim()
    $gitBranch = (git rev-parse --abbrev-ref HEAD).Trim()
    Write-Host "Deploying commit $commit ($gitBranch) to Cloudflare Pages project '$Project' (branch $Branch)"
} finally {
    Pop-Location
}

Push-Location $web
try {
    if (-not $SkipInstall) { Invoke-Step "npm ci" { npm ci } }
    $env:VITE_RELAY_WS_URL = $RelayUrl
    Invoke-Step "npm run build" { npm run build }
    Invoke-Step "wrangler pages deploy" {
        npx wrangler pages deploy dist --project-name $Project --branch $Branch --commit-hash $commit "--commit-dirty=$dirtyFlag"
    }
    Write-Host "Done: https://$Project.pages.dev (commit $commit)" -ForegroundColor Green
} finally {
    Remove-Item Env:VITE_RELAY_WS_URL -ErrorAction SilentlyContinue
    Pop-Location
}
