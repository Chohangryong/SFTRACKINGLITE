param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendRoot = Join-Path $RepoRoot "frontend"
$SpecPath = Join-Path $PSScriptRoot "SFTrackingDashboard.spec"
$IssPath = Join-Path $PSScriptRoot "SFTrackingDashboard.iss"
$DistRoot = Join-Path $RepoRoot "dist"
$WorkRoot = Join-Path $RepoRoot "build\\pyinstaller"

Write-Host "[1/3] frontend build"
Push-Location $FrontendRoot
if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
    npm.cmd ci
}
npm.cmd run build
Pop-Location

Write-Host "[2/3] pyinstaller build"
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    throw "PyInstaller가 설치되어 있지 않습니다. `pip install pyinstaller` 후 다시 실행하세요."
}
pyinstaller $SpecPath --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 빌드가 실패했습니다."
}

if ($SkipInstaller) {
    Write-Host "Inno Setup 단계는 건너뜁니다."
    exit 0
}

Write-Host "[3/3] inno setup build"
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $defaultInnoPath = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
    if (Test-Path $defaultInnoPath) {
        $iscc = @{ Source = $defaultInnoPath }
    } else {
        throw "ISCC.exe를 찾을 수 없습니다. Inno Setup 6를 설치하거나 PATH에 추가하세요."
    }
}

& $iscc.Source $IssPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup 빌드가 실패했습니다."
}
