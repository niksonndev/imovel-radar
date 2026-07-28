# PostToolUse Hook
# Automatically runs lint + typecheck after Cline edits/creates .ts/.tsx files in the frontend.
# Blocks continuation if there is an error, forcing Cline to fix it before proceeding.

try {
    $rawInput = [Console]::In.ReadToEnd()
    $data = $rawInput | ConvertFrom-Json
} catch {
    Write-Error "[PostToolUse] JSON inválido: $($_.Exception.Message)"
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

# It only works on file editing/creation tools.
$editTools = @("str_replace", "create_file", "write_to_file", "replace_in_file")
if ($data.toolName -notin $editTools) {
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

# Only acts on .ts/.tsx files within apps/frontend.
$filePath = $data.toolInput.path
if (-not $filePath -or $filePath -notmatch "apps[\\/]frontend.*\.(ts|tsx)$") {
    @{ cancel = $false; contextModification = ""; errorMessage = "" } | ConvertTo-Json -Compress
    exit 0
}

Push-Location "apps/frontend"
$lintOutput = pnpm lint 2>&1
$exitCode = $LASTEXITCODE
Pop-Location

if ($exitCode -ne 0) {
    $result = @{
        cancel = $false
        contextModification = "NOTICE: pnpm lint failed after editing $filePath. Fix the errors below before continuing or reporting the task as complete:`n$lintOutput"
        errorMessage = ""
    }
} else {
    $result = @{ cancel = $false; contextModification = ""; errorMessage = "" }
}

$result | ConvertTo-Json -Compress