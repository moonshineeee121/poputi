param([int]$Port = 8000, [switch]$ExternalDatabase)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $projectUv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (-not (Test-Path -LiteralPath $projectUv)) {
        $projectUv = (Get-Command uv -ErrorAction Stop).Source
    }
    & $projectUv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось подготовить виртуальное окружение.' }
}
if (-not $ExternalDatabase) {
    if (-not (Test-Path -LiteralPath '.tools\postgres\pgsql\bin\initdb.exe')) {
        & $projectPython -X utf8 scripts\setup_local.py download
        if ($LASTEXITCODE -ne 0) { throw 'Не удалось загрузить локальный PostgreSQL.' }
    }
    & $projectPython -X utf8 scripts\setup_local.py start
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось запустить локальный PostgreSQL.' }
}
& $projectPython -X utf8 scripts\prepare.py
if ($LASTEXITCODE -ne 0) { throw 'Не удалось подготовить базу данных.' }
Write-Host "Сайт: http://127.0.0.1:$Port/"
& $projectPython -X utf8 manage.py runserver "127.0.0.1:$Port"
