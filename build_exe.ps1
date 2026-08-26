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
$ProjectSmokePdf = Join-Path $ProjectRoot 'output\pdf\EXE_Project_Smoke_Test_2027_QLD.pdf'
$ProjectSmokeDocx = Join-Path $ProjectRoot 'output\docx\EXE_Project_Smoke_Test_2027_QLD.docx'
$FixtureProject = Join-Path $ProjectRoot 'tests\fixtures\sample_calendar.rocproject'

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
    --collect-all docx `
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

if (Test-Path -LiteralPath $ProjectSmokePdf) { Remove-Item -LiteralPath $ProjectSmokePdf -Force }
$ProjectProcess = Start-Process -FilePath $ReleaseExe -ArgumentList @('--project',('"' + $FixtureProject + '"'),'--generate-pdf','--output',('"' + $ProjectSmokePdf + '"')) -Wait -PassThru -WindowStyle Hidden
if ($ProjectProcess.ExitCode -ne 0) { throw "Packaged project smoke test failed with exit code $($ProjectProcess.ExitCode)." }
& $VenvPython (Join-Path $ProjectRoot 'verify_release.py') $ProjectSmokePdf
if ($LASTEXITCODE -ne 0) { throw 'The packaged executable produced an invalid project PDF.' }
if (Test-Path -LiteralPath $ProjectSmokeDocx) { Remove-Item -LiteralPath $ProjectSmokeDocx -Force }
$DocxParent = Split-Path -Parent $ProjectSmokeDocx
if (-not (Test-Path -LiteralPath $DocxParent)) { New-Item -ItemType Directory -Path $DocxParent | Out-Null }
$DocxProcess = Start-Process -FilePath $ReleaseExe -ArgumentList @('--project',('"' + $FixtureProject + '"'),'--generate-docx','--output',('"' + $ProjectSmokeDocx + '"')) -Wait -PassThru -WindowStyle Hidden
if ($DocxProcess.ExitCode -ne 0) { throw "Packaged project DOCX smoke test failed with exit code $($DocxProcess.ExitCode)." }
& $VenvPython (Join-Path $ProjectRoot 'verify_docx.py') $ProjectSmokeDocx --expect 'TEST PARISH DIVINE LITURGY'
if ($LASTEXITCODE -ne 0) { throw 'The packaged executable produced an invalid DOCX.' }
$GuiProcess = Start-Process -FilePath $ReleaseExe -ArgumentList @('--gui-smoke-test','--project',('"' + $FixtureProject + '"')) -Wait -PassThru -WindowStyle Hidden
if ($GuiProcess.ExitCode -ne 0) { throw "Packaged GUI project launch/close test failed with exit code $($GuiProcess.ExitCode)." }

Write-Host "BUILD VERIFIED: $ReleaseExe"
Write-Host "EXE-GENERATED PDF VERIFIED: $SmokePdf"
Write-Host "EXE PROJECT REOPEN/PDF VERIFIED: $ProjectSmokePdf"
Write-Host "EXE PROJECT REOPEN/DOCX VERIFIED: $ProjectSmokeDocx"
Write-Host "EXE GUI PROJECT LAUNCH/CLOSE VERIFIED"
