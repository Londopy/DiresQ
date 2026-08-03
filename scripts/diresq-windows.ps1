<#
    DiresQ — run it on your own machine.

    Windows, any processor. There is nothing compiled in this project, so
    there is no 32-bit build and no 64-bit build: it is Python source, and
    Python source does not have an architecture. If it runs on your machine
    at all, this is the file that runs it.

    Two ways to use it, and it works out which by itself:

      * Downloaded on its own from the Releases page — it fetches the source
        for the version it was published with, into a folder beside itself.
      * Sitting inside a clone of the repository — it uses the checkout it is
        in, so you can run your own working copy.

    Everything it installs goes in a virtual environment inside the project
    folder. Delete the folder and nothing is left behind.

    Right-click the file and choose "Run with PowerShell", or:

        powershell -ExecutionPolicy Bypass -File diresq-windows.ps1
#>

$ErrorActionPreference = "Stop"

$Repo = "Skythe7/DiresQ"

# The workflow rewrites this when it attaches the script to a release, so a
# downloaded copy pins the version it shipped with rather than drifting to
# whatever main happens to be that day.
$Version = "__VERSION__"

$Port = if ($env:PORT) { $env:PORT } else { "5000" }

function Say  ($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Die  ($m) { Write-Host "`nx $m`n" -ForegroundColor Red; exit 1 }

# ----------------------------------------------------------------- python ---
# 3.10 is the floor because CI tests 3.10 and 3.12, and a version nobody has
# ever run this on is not a version we are going to claim support for.
# The interpreter is kept as a command plus its arguments, never as one array
# used as a command. `& $array` does not invoke `py -3.12` — PowerShell
# flattens the array to a single string and looks for a program with a space
# in its name. Splatting with @PyArgs is the form that works.
$script:PyExe  = $null
$script:PyArgs = @()

function Find-Python {
    $tries = @()

    # The py launcher first: it is the one that knows about every install,
    # including the ones that were never added to PATH.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @("-3.12", "-3.11", "-3.10", "-3")) {
            $tries += ,@("py", @($v))
        }
    }
    foreach ($name in @("python3", "python")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $tries += ,@($name, @())
        }
    }

    foreach ($try in $tries) {
        $exe   = $try[0]
        # Not $args — that is an automatic variable holding a function's own
        # unbound arguments, and writing to it inside a function is a trap.
        $pyArg = $try[1]

        # Answer on stdout rather than through the exit code. A native command
        # writing to stderr under ErrorActionPreference=Stop raises, and the
        # Windows Store python stub exits 9009 in ways that are not worth
        # interpreting. A printed "1" is unambiguous.
        try {
            $probe = & $exe @pyArg -c "import sys; print(1 if sys.version_info[:2] >= (3,10) else 0)" 2>&1
            if ("$probe".Trim() -eq "1") {
                $script:PyExe  = $exe
                $script:PyArgs = $pyArg
                return $true
            }
        } catch { }
    }
    return $false
}

if (-not (Find-Python)) {
    Die "DiresQ needs Python 3.10 or newer.

   Install it from https://www.python.org/downloads/
   Tick 'Add Python to PATH' in the installer, then run this again."
}

Say ("Using " + (& $PyExe @PyArgs "--version" 2>&1))

# ----------------------------------------------------------------- source ---
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path (Join-Path $Here "app.py")) {
    $Project = $Here
} elseif (Test-Path (Join-Path $Here "..\app.py")) {
    $Project = (Resolve-Path (Join-Path $Here "..")).Path
} else {
    # Standing on its own, so go and get the code.
    $Ref = $Version
    if ($Ref -eq "__VERSION__") { $Ref = "main" }
    elseif (-not $Ref.StartsWith("v")) { $Ref = "v$Ref" }

    $Project = Join-Path $Here "diresq-$Ref"

    if (Test-Path $Project) {
        Say "Source already here: $Project"
    } else {
        Say "Downloading DiresQ $Ref"

        $Url = if ($Ref -eq "main") {
            "https://github.com/$Repo/archive/refs/heads/main.zip"
        } else {
            "https://github.com/$Repo/archive/refs/tags/$Ref.zip"
        }

        $Zip = Join-Path $env:TEMP "diresq-$Ref.zip"
        try {
            Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
        } catch {
            Die "Could not download $Url

   Check the tag exists, or clone the repository instead:
   git clone https://github.com/$Repo"
        }

        $Staging = Join-Path $env:TEMP "diresq-unpack-$([guid]::NewGuid())"
        Expand-Archive -Path $Zip -DestinationPath $Staging -Force

        # GitHub wraps the archive in a single folder named for the tag.
        $Inner = Get-ChildItem $Staging -Directory | Select-Object -First 1
        Move-Item $Inner.FullName $Project

        Remove-Item $Zip, $Staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Set-Location $Project
Say "Project: $Project"

# --------------------------------------------------------------- packages ---
$Venv = Join-Path $Project ".venv"

if (-not (Test-Path $Venv)) {
    Say "Creating a virtual environment"
    & $PyExe @PyArgs -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Die "Could not create a virtual environment." }
}

# Everything from here uses the venv's interpreter directly rather than
# Activate.ps1, which needs an execution policy this script should not assume.
$VPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VPy)) { Die "The virtual environment has no python.exe. Delete .venv and try again." }

Say "Installing dependencies"
& $VPy -m pip install --quiet --upgrade pip
& $VPy -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Die "Installing dependencies failed." }

# --------------------------------------------------------------- database ---
# Rebuilt every run, on purpose. This is a demo of an emergency tool: you want
# to open it and find the same incident two hours old with somebody already
# overdue, not whatever you left behind last time.
Say "Building the database"
$Db = Join-Path $Project "diresq.db"
if (Test-Path $Db) { Remove-Item $Db -Force }

& $VPy -m flask --app app init-db
& $VPy -m flask --app app seed

# -------------------------------------------------------------------- run ---
Write-Host @"

  DiresQ is starting.

    http://127.0.0.1:$Port

    Sign in as   londo / diresq

  Nothing in it is real. Please don't type a real address into something
  that looks like an emergency service and is not one.

  Ctrl-C to stop.

"@

# Give the server a moment before the browser goes looking for it.
#
# A detached process rather than Start-Job: `$using:` inside an interpolated
# string is not reliably expanded, and a background job that silently fails to
# open a browser is a bug nobody reports and everybody works around.
$Url = "http://127.0.0.1:" + $Port
Start-Process -WindowStyle Hidden powershell -ArgumentList @(
    "-NoProfile", "-Command", "Start-Sleep -Seconds 2; Start-Process '$Url'"
) -ErrorAction SilentlyContinue | Out-Null

# The Flask development server, deliberately. gunicorn does not run on
# Windows at all, and this is one person on their own laptop — the case the
# dev server is actually correct for. The hosted demo uses gunicorn.
& $VPy -m flask --app app run --port $Port
