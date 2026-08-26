param(
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ReleaseDir = Join-Path $ProjectRoot 'dist\RussianOrthodoxCalendar'
$ReleaseExe = Join-Path $ReleaseDir 'RussianOrthodoxCalendar.exe'
$SmokePdf = Join-Path $ProjectRoot 'output\pdf\EXE_Smoke_Test_2027_QLD.pdf'

Set-Location -LiteralPath $ProjectRoot
if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.13 -m venv (Join-Path $ProjectRoot '.venv')
}
if (-not $SkipInstall) {
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements-dev.txt')
}
if (-not $SkipTests) {
    & $VenvPython -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; packaging stopped.' }
}

$ResolvedRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$BuildPath = Join-Path $ResolvedRoot 'build'
if (Test-Path -LiteralPath $BuildPath) { Remove-Item -LiteralPath $BuildPath -Recurse -Force }
if (Test-Path -LiteralPath $ReleaseDir) { Remove-Item -LiteralPath $ReleaseDir -Recurse -Force }

& $VenvPython -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name RussianOrthodoxCalendar `
    --icon (Join-Path $ProjectRoot 'assets\icons\app.ico') `
    --add-data "assets;assets" `
    --add-data "orthodox_calendar\database\schema.sql;orthodox_calendar\database" `
    --collect-all holidays `
    --collect-all reportlab `
    --hidden-import PySide6.QtPdf `
    --hidden-import PySide6.QtPdfWidgets `
    (Join-Path $ProjectRoot 'app.py')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ReleaseExe)) { throw 'PyInstaller did not produce the expected executable.' }

$SmokeParent = Split-Path -Parent $SmokePdf
if (-not (Test-Path -LiteralPath $SmokeParent)) { New-Item -ItemType Directory -Path $SmokeParent | Out-Null }
if (Test-Path -LiteralPath $SmokePdf) { Remove-Item -LiteralPath $SmokePdf -Force }
$Process = Start-Process -FilePath $ReleaseExe -ArgumentList @('--generate-pdf','--year','2027','--state','QLD','--output',('"' + $SmokePdf + '"')) -Wait -PassThru -WindowStyle Hidden
if ($Process.ExitCode -ne 0) { throw "Packaged executable smoke test failed with exit code $($Process.ExitCode)." }
& $VenvPython (Join-Path $ProjectRoot 'verify_release.py') $SmokePdf
if ($LASTEXITCODE -ne 0) { throw 'The packaged executable produced an invalid PDF.' }

Write-Host "BUILD VERIFIED: $ReleaseExe"
Write-Host "EXE-GENERATED PDF VERIFIED: $SmokePdf"

