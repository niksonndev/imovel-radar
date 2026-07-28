# PreToolUse.ps1
# Local: .clinerules/hooks/PreToolUse.ps1
# Blocks attempt_completion if no .md file has pending changes in the working tree.

$result = @{
    cancel = $false
    contextModification = ""
    errorMessage = ""
}

try {
    $rawInput = [Console]::In.ReadToEnd()
    $payload = $null
    if ($rawInput) {
        $payload = $rawInput | ConvertFrom-Json
    }

    $toolName = $payload.preToolUse.toolName

    if ($toolName -eq "attempt_completion") {
        $repoRoot = if ($payload.workspaceRoots -and $payload.workspaceRoots.Count -gt 0) {
            $payload.workspaceRoots[0]
        } else {
            (Get-Location).Path
        }

        Push-Location $repoRoot
        $mdStatus = git status --porcelain -- '*.md'
        Pop-Location

        if (-not $mdStatus) {
            $result.cancel = $true
            $result.errorMessage = "No .md files with pending changes. Create or update the documentation before calling attempt_completion again."
        }
    }
} catch {
    Write-Error "[PreToolUse] Invalid JSON input: $($_.Exception.Message)"
}

$result | ConvertTo-Json -Compress