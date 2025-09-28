# setup.ps1 - Full-Stack Question Bank Management System Setup Script
# Usage: from project root run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\setup.ps1

# Ensure UTF-8 output (helps if console doesn't render emojis)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Setting up Question Bank Management System..." -ForegroundColor Green

# Save original location
$origLocation = Get-Location

# Helper - check command existence
function Command-Exists($name) {
    return (Get-Command $name -ErrorAction SilentlyContinue) -ne $null
}

# Check Node.js
if (Command-Exists "node") {
    try {
        $nodeVersion = (& node --version).ToString().Trim()
        Write-Host "Node.js found: $nodeVersion" -ForegroundColor Green
    } catch {
        Write-Host "Node.js executable found but failed to run 'node --version'." -ForegroundColor Yellow
    }
} else {
    Write-Host "Node.js not found. Please install Node.js 18+ and ensure 'node' is on PATH." -ForegroundColor Red
    exit 1
}

# Check Python (try python then python3)
$pythonCmd = $null
if (Command-Exists "python") {
    $pythonCmd = "python"
} elseif (Command-Exists "python3") {
    $pythonCmd = "python3"
}

if ($null -ne $pythonCmd) {
    try {
        $pythonVersion = (& $pythonCmd --version).ToString().Trim()
        Write-Host "Python found: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "Python executable found but failed to run '--version'." -ForegroundColor Yellow
    }
} else {
    Write-Host "Python not found. Please install Python 3.8+ and ensure 'python' or 'python3' is on PATH." -ForegroundColor Red
    exit 1
}

# Install frontend deps
if (Test-Path -Path "frontend") {
    Write-Host "`nInstalling frontend dependencies..." -ForegroundColor Yellow
    Push-Location "frontend"
    if (Command-Exists "npm") {
        & npm install
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Frontend dependencies installed successfully." -ForegroundColor Green
        } else {
            Write-Host "Failed to install frontend dependencies (npm install returned non-zero)." -ForegroundColor Red
            Pop-Location
            exit 1
        }
    } else {
        Write-Host "npm not found. Please install Node.js/npm." -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
} else {
    Write-Host "frontend directory not found. Skipping frontend installation." -ForegroundColor Yellow
}

# Install backend deps (pip or pip3)
if (Test-Path -Path "backend") {
    Write-Host "`nInstalling backend dependencies..." -ForegroundColor Yellow
    Push-Location "backend"

    $pipCmd = $null
    if (Command-Exists "pip") { $pipCmd = "pip" }
    elseif (Command-Exists "pip3") { $pipCmd = "pip3" }

    if ($null -ne $pipCmd) {
        & $pipCmd install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Backend dependencies installed successfully." -ForegroundColor Green
        } else {
            Write-Host "Failed to install backend dependencies (pip returned non-zero)." -ForegroundColor Red
            Pop-Location
            exit 1
        }
    } else {
        Write-Host "pip not found. Please install pip (or pip3) for your Python installation." -ForegroundColor Red
        Pop-Location
        exit 1
    }

    Pop-Location
} else {
    Write-Host "backend directory not found. Skipping backend installation." -ForegroundColor Yellow
}

# Setup environment files (copy templates if missing)
Write-Host "`nSetting up environment files..." -ForegroundColor Yellow

# Frontend .env.local
$frontendTemplate = Join-Path -Path $origLocation -ChildPath "frontend\env.local.example"
$frontendEnv = Join-Path -Path $origLocation -ChildPath "frontend\.env.local"
if (Test-Path $frontendTemplate) {
    if (-not (Test-Path $frontendEnv)) {
        Copy-Item -Path $frontendTemplate -Destination $frontendEnv
        Write-Host "Created frontend/.env.local from template." -ForegroundColor Green
    } else {
        Write-Host "frontend/.env.local already exists." -ForegroundColor Cyan
    }
} else {
    Write-Host "frontend/env.local.example not found; please create frontend/.env.local manually." -ForegroundColor Yellow
}

# Backend .env
$backendTemplate = Join-Path -Path $origLocation -ChildPath "backend\env.example"
$backendEnv = Join-Path -Path $origLocation -ChildPath "backend\.env"
if (Test-Path $backendTemplate) {
    if (-not (Test-Path $backendEnv)) {
        Copy-Item -Path $backendTemplate -Destination $backendEnv
        Write-Host "Created backend/.env from template." -ForegroundColor Green
    } else {
        Write-Host "backend/.env already exists." -ForegroundColor Cyan
    }
} else {
    Write-Host "backend/env.example not found; please create backend/.env manually." -ForegroundColor Yellow
}

# Final instructions
Write-Host "`nSetup completed." -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host " 1) Create a Supabase project at https://supabase.com and get your keys." -ForegroundColor White
Write-Host " 2) Update environment files:" -ForegroundColor White
Write-Host "      frontend/.env.local  (use NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY)" -ForegroundColor Gray
Write-Host "      backend/.env         (use SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)" -ForegroundColor Gray
Write-Host " 3) Run DB schema in Supabase SQL editor (docs/database-schema.md)." -ForegroundColor White
Write-Host " 4) Start servers:" -ForegroundColor White
Write-Host "      Backend: cd backend; $pythonCmd -m uvicorn app.main:app --reload" -ForegroundColor Gray
Write-Host "      Frontend: cd frontend; npm run dev" -ForegroundColor Gray
Write-Host "`nUseful URLs:" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Gray
Write-Host "  Backend API: http://localhost:8000" -ForegroundColor Gray
Write-Host "  Backend Health: http://localhost:8000/api/health" -ForegroundColor Gray
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor Gray

# Restore original location
Set-Location $origLocation
