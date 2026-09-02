$ErrorActionPreference = "Stop"
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONDONTWRITEBYTECODE = "1"
$plan1CoverageFile = Join-Path ([System.IO.Path]::GetTempPath()) "aim-companion-plan1-$PID.coverage"
$env:COVERAGE_FILE = $plan1CoverageFile

try {
    python -m pytest -q -p no:cacheprovider `
        tests/test_benchmark_definitions.py `
        tests/test_benchmark_calculator.py `
        tests/test_analyzer_official_profile.py `
        tests/test_official_profile_presentation.py `
        tests/test_migrations.py `
        tests/test_database.py `
        tests/test_score_importer.py `
        tests/test_score_watcher.py `
        tests/test_aim_hub.py `
        tests/test_parser.py `
        --cov=core.benchmarks `
        --cov=core.score_importer `
        --cov=core.score_watcher `
        --cov=core.sync_worker `
        --cov=models.migrations `
        --cov=models.profile `
        --cov-report=term-missing `
        --cov-fail-under=80
    $plan1CoverageExit = $LASTEXITCODE
}
finally {
    if (Test-Path -LiteralPath $plan1CoverageFile) {
        Remove-Item -LiteralPath $plan1CoverageFile
    }
    Remove-Item Env:COVERAGE_FILE
}

exit $plan1CoverageExit
