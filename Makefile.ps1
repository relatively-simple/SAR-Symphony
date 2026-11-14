param(
    [Parameter(Position=0)]
    [ValidateSet("test", "prewarm", "build", "dev", "serve", "all")]
    [string]$Task = "test"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Pytest = Join-Path $Root "backend\.venv\Scripts\pytest.exe"

switch ($Task) {
    "test" {
        Push-Location (Join-Path $Root "backend")
        & $Pytest -m "not network" -v
        Pop-Location
    }
    "prewarm" {
        & $Py (Join-Path $Root "backend\scripts\prewarm.py") --per-pass-det 5
    }
    "build" {
        Push-Location (Join-Path $Root "frontend")
        npm run build
        Pop-Location
    }
    "dev" {
        Push-Location (Join-Path $Root "backend")
        Start-Process -NoNewWindow -FilePath $Py -ArgumentList "-m", "uvicorn", "app.main:create_app", "--factory", "--port", "7860"
        Pop-Location
        Push-Location (Join-Path $Root "frontend")
        npm run dev
        Pop-Location
    }
    "serve" {
        Push-Location (Join-Path $Root "backend")
        & $Py -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 7860
        Pop-Location
    }
    "all" {
        & $PSCommandPath test
        & $PSCommandPath build
    }
}
