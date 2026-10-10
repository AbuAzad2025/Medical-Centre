<#
.SYNOPSIS
    Runs the test suite with the exact environment .github/workflows/ci.yml uses.

.DESCRIPTION
    Local pytest runs were failing for reasons that had nothing to do with the
    code: this repo's CI is green on the same commit. The gap was environmental.
    The core-test job in ci.yml sets eleven variables and installs a restricted
    PostgreSQL role; running pytest without them exercises different code paths
    (IdempotencyLock falls back to in-memory without REDIS_URL, Celery behaves
    differently, Stripe-dependent billing branches never execute, and the SQL
    RLS tests cannot connect at all).

    This script is the single source of truth for that environment. Do not add
    ad-hoc $env: assignments elsewhere; change ci.yml and this together.

.PARAMETER Reset
    Drop and recreate the dedicated test database before running. Use this when
    a previous run left committed rows behind, which is how cross-run state
    leaks into assertions about counts.

.PARAMETER NoReset
    Skip the recreate. Faster, and the default.

.EXAMPLE
    .\scripts\ops\local_test_env.ps1 -Reset
    .\scripts\ops\local_test_env.ps1 tests/test_scenarios_grounded.py -q
#>
[CmdletBinding()]
param(
    [switch]$Reset,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs = @()
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))

# ---------------------------------------------------------------------------
# A database name nothing else uses. The default postgres DBs on this machine
# belong to other projects; touching them is how one repo's fixtures end up
# breaking another's tests.
# ---------------------------------------------------------------------------
$DbName = 'medical_test'
$DbUser = 'postgres'
$DbPass = 'testpass'
$DbHost = 'localhost:5432'
$DbUrl = "postgresql://${DbUser}:${DbPass}@${DbHost}/${DbName}"

$RlsRole = 'med_app_runtime'
$RlsPass = 'rlstest'

function Invoke-Sql {
    param([string]$Sql, [string]$Database = 'postgres')
    $env:PGPASSWORD = $DbPass
    & $psqlExe "-h" "localhost" "-p" "5432" "-U" $DbUser "-d" $Database `
              "-v" "ON_ERROR_STOP=1" "-tAc" $Sql
}

# The PostgreSQL client is installed but not on PATH on this machine, and the
# repo pins no server version, so discover it rather than hardcoding a guess.
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlCmd) {
    $found = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $found) {
        throw "psql not found. Install the PostgreSQL client tools, or put them on PATH."
    }
    $psqlCmd = $found
}
$psqlExe = if ($psqlCmd -is [System.Management.Automation.CommandInfo]) { $psqlCmd.Source }
            else { $psqlCmd.FullName }
if (-not (Test-Path -LiteralPath $psqlExe)) { throw "resolved psql path is invalid: $psqlExe" }

if ($Reset) {
    Write-Host "[reset] recreating $DbName" -ForegroundColor Cyan
    # Terminate stragglers so DROP cannot block on an idle-in-transaction session.
    Invoke-Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                WHERE datname = '$DbName' AND pid <> pg_backend_pid()" | Out-Null
    Invoke-Sql "DROP DATABASE IF EXISTS $DbName" | Out-Null
    Invoke-Sql "CREATE DATABASE $DbName" | Out-Null
}

# ---------------------------------------------------------------------------
# Environment, copied from the `env:` block of the core-test job in ci.yml.
# ---------------------------------------------------------------------------
$env:SECRET_KEY                 = 'ci-test-secret-key-for-jwt-hs256-min32'
$env:APP_ENV                    = 'testing'
$env:FLASK_ENV                  = 'testing'
$env:FLASK_APP                  = 'wsgi:app'
$env:SUPPRESS_BACKGROUND_WORKER = '1'
$env:SUPPRESS_LOGGING           = '1'
$env:DATABASE_URL               = $DbUrl
$env:TEST_DATABASE_URL          = $DbUrl
$env:RLS_TEST_DATABASE_URL      = "postgresql://${RlsRole}:${RlsPass}@${DbHost}/${DbName}"
$env:REDIS_URL                  = 'redis://localhost:6379/0'
$env:CELERY_BROKER_URL          = 'redis://localhost:6379/0'
$env:CELERY_ENABLED             = 'true'
$env:CELERY_TASK_ALWAYS_EAGER   = 'true'
$env:ENABLE_SAAS_MODE           = 'true'
$env:PLATFORM_CAP_WEBAUTHN      = 'true'
$env:PLATFORM_CAP_SSO           = 'true'
$env:RLS_BYPASS_ALLOWED         = '1'
$env:STRIPE_SECRET_KEY          = 'sk_test_ci_e2e'
$env:STRIPE_WEBHOOK_SECRET      = 'whsec_test_ci_e2e'
$env:PYTHONPATH                 = '.'

if (-not $env:COVERAGE_FILE) { $env:COVERAGE_FILE = '.coverage.local' }

if ($Reset) {
    Write-Host "[reset] applying migrations (this is what creates the RLS policies)" -ForegroundColor Cyan
    & .\.venv\Scripts\python.exe -m flask db upgrade heads
    if ($LASTEXITCODE -ne 0) { throw "migrations failed" }

    # Mirrors the "Create restricted runtime role" step of
    # .github/actions/test-env, which runs psql against $DATABASE_URL, so every
    # GRANT lands in the test database. Connecting to `postgres` here instead
    # fails with "schema public does not exist" on a fresh cluster.
    Write-Host "[reset] creating restricted runtime role $RlsRole in $DbName" -ForegroundColor Cyan
    Invoke-Sql "DROP ROLE IF EXISTS $RlsRole" | Out-Null
    Invoke-Sql "CREATE ROLE $RlsRole WITH LOGIN PASSWORD '$RlsPass'
                NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS" | Out-Null
    Invoke-Sql "GRANT USAGE ON SCHEMA public TO $RlsRole" $DbName | Out-Null
    Invoke-Sql "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $RlsRole" $DbName | Out-Null
    Invoke-Sql "GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO $RlsRole" $DbName | Out-Null
    Invoke-Sql "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $RlsRole" $DbName | Out-Null
    Invoke-Sql "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
                GRANT USAGE ON SEQUENCES TO $RlsRole" $DbName | Out-Null
}

if (-not $PytestArgs) { $PytestArgs = @('tests/') }

& .\.venv\Scripts\python.exe -m pytest @PytestArgs
exit $LASTEXITCODE