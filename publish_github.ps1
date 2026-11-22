# VA AILOCK AI Studio - GitHub Pages publisher
# Creates a NEW public repository belonging to the signed-in GitHub account.
# Commits ONLY the explicit project source files listed below (never .env, datasets, or model weights).
# Uses GitHub CLI login in YOUR OWN browser: no personal access token is requested by this script.
param([string]$RepoName = "va-ailock-ai-studio")

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Run-Or-Stop {
    param([string]$Action, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit code $LASTEXITCODE)." }
}

function Ensure-Command {
    param([string]$Name, [string]$WingetId, [string]$AddedPath)
    if (Get-Command $Name -ErrorAction SilentlyContinue) { return }
    Write-Host "$Name is not installed or not on PATH." -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Install $Name and run this script again. Windows Package Manager (winget) is unavailable."
    }
    Write-Host "Installing $WingetId with Windows Package Manager..." -ForegroundColor Yellow
    & winget install --exact --id $WingetId --source winget --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install $WingetId. Install it manually and rerun." }
    if (Test-Path $AddedPath) { $env:PATH = "$AddedPath;$env:PATH" }
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Installed $Name, but the new PATH isn't loaded. Open a new PowerShell window and rerun this script."
    }
}

try {
    if ($RepoName -notmatch '^[a-zA-Z0-9._-]+$') { throw "Invalid repository name." }
    foreach ($required in @('docs/index.html','docs/app.js','docs/style.css','README.md','app.py')) {
        if (-not (Test-Path $required -PathType Leaf)) { throw "Missing file: $required. Extract the entire ZIP first." }
    }

    Ensure-Command -Name 'git' -WingetId 'Git.Git' -AddedPath "${env:ProgramFiles}\Git\cmd"
    Ensure-Command -Name 'gh' -WingetId 'GitHub.cli' -AddedPath "${env:ProgramFiles}\GitHub CLI"

    & gh auth status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Sign in to YOUR GitHub account in the browser window." -ForegroundColor Cyan
        Run-Or-Stop 'GitHub sign-in' { & gh auth login --web --git-protocol https }
    }
    Run-Or-Stop 'GitHub Git authentication setup' { & gh auth setup-git }

    $Owner = (& gh api user --jq .login).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Owner) { throw 'Could not verify the signed-in GitHub username.' }
    $Repository = "$Owner/$RepoName"
    Write-Host "Publishing $Repository" -ForegroundColor Cyan

    if (-not (Test-Path '.git' -PathType Container)) {
        Run-Or-Stop 'Initialize Git repository' { & git init -b main }
    }
    $CurrentBranch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the current Git branch.' }
    if ($CurrentBranch -ne 'main') { Run-Or-Stop 'Set main branch' { & git branch -M main } }

    $GitName = (& git config user.name)
    if (-not $GitName) { Run-Or-Stop 'Set Git author name' { & git config user.name $Owner } }
    $GitEmail = (& git config user.email)
    if (-not $GitEmail) { Run-Or-Stop 'Set Git author email' { & git config user.email "$Owner@users.noreply.github.com" } }

    # Explicit allowlist: don't ever add .env, private user images, model weights, or exported MP4s.
    Run-Or-Stop 'Stage approved website and source files' {
        & git add -- .gitignore .env.example README.md GITHUB_LIVE_SETUP.md docs app.py static train requirements.txt start_windows.bat publish_github.ps1 SETUP_AND_PUBLISH.bat OPEN_LOCAL_PREVIEW.bat
    }
    $Staged = (& git diff --cached --name-only)
    if ($LASTEXITCODE -ne 0) { throw 'Failed to check Git staging area.' }
    if ($Staged) { Run-Or-Stop 'Commit source files' { & git commit -m 'Publish VA AILOCK AI Studio website and starter backend' } }

    & gh repo view $Repository --json name --jq .name *> $null
    $Exists = ($LASTEXITCODE -eq 0)
    if (-not $Exists) {
        Write-Host "Creating PUBLIC GitHub repository: $Repository" -ForegroundColor Cyan
        Run-Or-Stop 'Create and push GitHub repository' {
            & gh repo create $Repository --public --source . --remote origin --push --description 'VA AILOCK 2D art scene editor, storyboard planner, and creative AI starter'
        }
    } else {
        $Remotes = @(& git remote)
        if ('origin' -notin $Remotes) {
            Run-Or-Stop 'Link existing GitHub repository' { & git remote add origin "https://github.com/$Repository.git" }
        } else {
            $Remote = (& git remote get-url origin)
            if (($Remote -notmatch [regex]::Escape("github.com/$Repository")) -and ($Remote -notmatch [regex]::Escape("github.com:$Repository"))) {
                throw "Git remote 'origin' points somewhere else: $Remote. Refusing to overwrite or publish to the wrong repository."
            }
        }
        Run-Or-Stop 'Push website to GitHub' { & git push -u origin main }
    }

    # Set GitHub Pages to publish /docs from the main branch. This API call does NOT host the AI model.
    & gh api "repos/$Repository/pages" --jq .html_url 2>$null | Out-Null
    $PagesExists = ($LASTEXITCODE -eq 0)
    if ($PagesExists) {
        & gh api -X PUT "repos/$Repository/pages" -f 'source[branch]=main' -f 'source[path]=/docs' 2>$null | Out-Null
    } else {
        & gh api -X POST "repos/$Repository/pages" -f 'source[branch]=main' -f 'source[path]=/docs' 2>$null | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Files were published, but Pages could not be enabled automatically. Open https://github.com/$Repository/settings/pages and select Deploy from a branch > main > /docs."
    } else {
        Write-Host 'GitHub Pages publishing configuration saved.' -ForegroundColor Green
    }

    Write-Host "`nRepository: https://github.com/$Repository" -ForegroundColor Green
    Write-Host "Website (after GitHub deploys it): https://$Owner.github.io/$RepoName/" -ForegroundColor Green
    Write-Host "Deployment status: https://github.com/$Repository/actions" -ForegroundColor Cyan
    Write-Host "`nNOTE: This deploys the FREE WEBSITE/POSE EDITOR. AI image model, AI chat, and video rendering still require a separately secured backend/GPU host." -ForegroundColor Yellow
} catch {
    Write-Host "`nSETUP FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'The script never deletes GitHub repositories and does not use git --force.' -ForegroundColor Yellow
    exit 1
}
