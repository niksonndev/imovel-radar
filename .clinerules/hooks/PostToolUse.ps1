# PostToolUse Hook
# - TS/TSX em apps/frontend: roda `pnpm lint` (eslint + tsc --noEmit)
# - Python em apps/scraper ou apps/bot: roda `uv run ruff check .` + `uv run pyright`
# Bloqueia a continuação se houver erro, forçando o Cline a corrigir antes de prosseguir.

try {
    $rawInput = [Console]::In.ReadToEnd()
    $data = $rawInput | ConvertFrom-Json
} catch {
    Write-Error "[PostToolUse] JSON inválido: $($_.Exception.Message)"
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

$editTools = @("str_replace", "create_file", "write_to_file", "replace_in_file")
if ($data.toolName -notin $editTools) {
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

$filePath = $data.toolInput.path
$output = ""
$hasError = $false

if ($filePath -match "apps[\\/]frontend.*\.(ts|tsx)$") {
    Push-Location "apps/frontend"
    $lintOutput = pnpm lint 2>&1
    $exitCode = $LASTEXITCODE
    Pop-Location
    if ($exitCode -ne 0) {
        $hasError = $true
        $output += "PNPM LINT ERRORS ($filePath):`n$lintOutput`n`n"
    }
}
elseif ($filePath -match "apps[\\/](scraper|bot)[\\/].*\.py$") {
    $appDir = "apps/$($matches[1])"
    Push-Location $appDir
    $lintOutput = uv run ruff check . 2>&1
    $lintExitCode = $LASTEXITCODE
    $typeOutput = uv run pyright 2>&1
    $typeExitCode = $LASTEXITCODE
    Pop-Location
    if ($lintExitCode -ne 0) {
        $hasError = $true
        $output += "RUFF ERRORS ($filePath):`n$lintOutput`n`n"
    }
    if ($typeExitCode -ne 0) {
        $hasError = $true
        $output += "PYRIGHT ERRORS ($filePath):`n$typeOutput`n`n"
    }
}
else {
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

if ($hasError) {
    $result = @{
        cancel = $false
        contextModification = "NOTICE: checks failed after editing $filePath. Fix the errors below before continuing or reporting the task as complete:`n$output"
        errorMessage = ""
    }
} else {
    $result = @{ cancel = $false; contextModification = ""; errorMessage = "" }
}
$result | ConvertTo-Json -Compress