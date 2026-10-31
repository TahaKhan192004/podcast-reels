# One-time setup for Windows 10/11.
# Run from the podcast-reels folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# (ASCII-only on purpose: Windows PowerShell 5.1 misreads UTF-8 scripts without a BOM.)
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

function Say($m)  { Write-Host "> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "X $m" -ForegroundColor Red; exit 1 }
function Has($c)  { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User")
}
function Winget-Install($id, $name) {
  Say "Installing $name ..."
  winget install -e --id $id --accept-source-agreements --accept-package-agreements
  Refresh-Path
}

# --- system tools (winget) ----------------------------------------------------
if (-not (Has winget)) { Fail "winget not found. Install 'App Installer' from the Microsoft Store, then run setup again." }
if (-not (Has git))    { Winget-Install "Git.Git" "Git for Windows (needed by Claude Code)" }
if (-not (Has ffmpeg)) { Winget-Install "Gyan.FFmpeg" "ffmpeg" }
if (-not (Has node))   { Winget-Install "OpenJS.NodeJS.LTS" "Node.js" }
# Only trust the 'py' launcher: a bare 'python' is often the Microsoft Store placeholder.
if (-not (Has py))     { Winget-Install "Python.Python.3.12" "Python 3.12" }

foreach ($tool in "ffmpeg", "node", "py") {
  if (-not (Has $tool)) { Fail "'$tool' is installed but not on PATH yet. Close PowerShell, open a new one, and run setup again." }
}

# --- python env ------------------------------------------------------------------
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
  Say "Creating Python virtual environment ..."
  foreach ($v in "-3.12", "-3.11", "-3.13", "-3") {
    & py $v -m venv .venv 2>&1 | Out-Null
    if (Test-Path $PY) { break }
  }
}
if (-not (Test-Path $PY)) { Fail "Could not create .venv. Check that Python 3.10+ works: py -3 --version" }

& $PY -m pip install --upgrade pip -q
Say "Installing Python packages (yt-dlp, faster-whisper, OpenCV) - a few minutes ..."
& $PY -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { Fail "pip install failed (see the messages above)." }

if (Has nvidia-smi) {
  Say "NVIDIA GPU detected -> installing CUDA libraries for faster-whisper ..."
  & $PY -m pip install -q nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
}

# --- remotion -------------------------------------------------------------------
Say "Installing Remotion (npm) ..."
Push-Location remotion
npm install --no-audit --no-fund --loglevel=error
$npmOk = ($LASTEXITCODE -eq 0)
if ($npmOk) { npx remotion browser ensure }
Pop-Location
if (-not $npmOk) { Fail "npm install failed (see the messages above)." }

# --- assets + check -----------------------------------------------------------------
$env:PYTHONUTF8 = "1"
Say "Downloading fonts + face model ..."
& $PY -m pipeline assets
& $PY -m pipeline doctor
Say "Setup complete. Run 'claude' in this folder, then:  /make-reels <youtube-url>"
