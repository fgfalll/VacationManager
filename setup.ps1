#!/usr/bin/env pwsh
# VacationManager Setup Script
# This script sets up the complete development environment

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VacationManager Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Store the project root directory
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $ProjectRoot) {
    $ProjectRoot = (Get-Location).Path
}
Set-Location $ProjectRoot
Write-Host "Project root: $ProjectRoot" -ForegroundColor Green

# ============================================================================
# 1. Python Virtual Environment Setup
# ============================================================================
Write-Host "`n[1/5] Setting up Python virtual environment..." -ForegroundColor Yellow

$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath (If ($IsWindows) { "Scripts\python.exe" } Else { "bin/python" })

if (Test-Path $VenvPython) {
    Write-Host "  Virtual environment already exists at .venv" -ForegroundColor Gray
} else {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment"
        exit 1
    }
}

$PythonExec = $VenvPython

# ============================================================================
# 2. Install Python Dependencies
# ============================================================================
Write-Host "`n[2/5] Installing Python dependencies..." -ForegroundColor Yellow

$RequirementsPath = Join-Path $ProjectRoot "requirements.txt"
if (Test-Path $RequirementsPath) {
    Write-Host "  Installing from requirements.txt..." -ForegroundColor Gray
    & $PythonExec -m pip install --upgrade pip
    & $PythonExec -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install Python dependencies"
        exit    1
    }
 Write-Host "  Python dependencies installed successfully" -ForegroundColor Green
} else {
    Write-Warning "requirements.txt not found, skipping Python dependencies"
}

# ============================================================================
# 3. Install npm Dependencies
# ============================================================================
Write-Host "`n[3/5] Installing npm dependencies..." -ForegroundColor Yellow

function Install-NpmDeps($Dir, $Name) {
    if (Test-Path (Join-Path $Dir "package.json")) {
        Write-Host "  Installing npm dependencies for $Name..." -ForegroundColor Gray
        Push-Location $Dir
        try {
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "npm install failed"
            }
            Write-Host "  $Name dependencies installed successfully" -ForegroundColor Green
        }
        finally {
            Pop-Location
        }
    } else {
        Write-Host "  package.json not found in $Name, skipping" -ForegroundColor Gray
    }
}

Install-NpmDeps $ProjectRoot "root"
Install-NpmDeps (Join-Path $ProjectRoot "web") "web"
Install-NpmDeps (Join-Path $ProjectRoot "telegram-mini-app") "telegram-mini-app"

# ============================================================================
# 4. Environment Configuration
# ============================================================================
Write-Host "`n[4/5] Setting up environment configuration..." -ForegroundColor Yellow

$EnvExamplePath = Join-Path $ProjectRoot ".env.example"
$EnvPath = Join-Path $ProjectRoot ".env"

if (Test-Path $EnvExamplePath) {
    if (-not (Test-Path $EnvPath)) {
        Write-Host "  Copying .env.example to .env..." -ForegroundColor Gray
        Copy-Item $EnvExamplePath $EnvPath
        Write-Host "  Created .env file" -ForegroundColor Green
        Write-Host "  WARNING: Please edit .env and update VM_SECRET_KEY for production!" -ForegroundColor Yellow
    } else {
        Write-Host "  .env file already exists, skipping" -ForegroundColor Gray
    }
} else {
    Write-Warning ".env.example not found, skipping environment setup"
}

# ============================================================================
# 5. Database Setup
# ============================================================================
Write-Host "`n[5/5] Setting up database..." -ForegroundColor Yellow

# Create storage directory if it doesn't exist
$StoragePath = Join-Path $ProjectRoot "storage"
if (-not (Test-Path $StoragePath)) {
    New-Item -ItemType Directory -Path $StoragePath | Out-Null
    Write-Host "  Created storage directory" -ForegroundColor Gray
}

# Run Alembic migrations
Write-Host "  Running database migrations..." -ForegroundColor Gray
& $PythonExec -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Alembic migration failed (this is OK for first-time setup if migrations don't exist yet)"
    Write-Host "  Trying to create initial database..." -ForegroundColor Gray
    # Try to initialize the database directly
    & $PythonExec -c "
import asyncio
from backend.db.session import engine, Base
from backend.db.init_db import init_db
async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_db()
    print('Database initialized successfully')
asyncio.run(main())
"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Database initialized successfully" -ForegroundColor Green
    }
} else {
    Write-Host "  Database migrations completed" -ForegroundColor Green
}

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Review and update .env file if needed" -ForegroundColor Gray
Write-Host "  2. Run 'npm run start' to start all services" -ForegroundColor Gray
Write-Host "     or 'npm run start:backend' for backend only" -ForegroundColor Gray
Write-Host "     or 'npm run dev:web' for web dev server" -ForegroundColor Gray
Write-Host ""
Write-Host "For more information, see README.md" -ForegroundColor Gray
