# TaskComplete.ps1
# Local: .clinerules/hooks/TaskComplete.ps1
# Aviso não-bloqueante: ao final da task, verifica se algum .md tem
# mudanças pendentes e injeta um lembrete se não houver.
# TaskComplete não é cancelável — isso é só um lembrete, nunca bloqueia nada.

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

    $repoRoot = if ($payload.workspaceRoots -and $payload.workspaceRoots.Count -gt 0) {
        $payload.workspaceRoots[0]
    } else {
        (Get-Location).Path
    }

    Push-Location $repoRoot
    $mdStatus = git status --porcelain -- '*.md'
    Pop-Location

    if (-not $mdStatus) {
        $result.contextModification = "REMINDER: nenhum arquivo .md foi criado ou modificado nesta task. Considere documentar o que foi feito, se relevante."
    }
} catch {
    Write-Error "[TaskComplete] JSON inválido ou erro de git: $($_.Exception.Message)"
}

$result | ConvertTo-Json -Compress