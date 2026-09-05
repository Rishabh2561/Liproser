$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $repositoryRoot

try {
    $errors = [System.Collections.Generic.List[string]]::new()
    $requiredFiles = @(
        'README.md',
        'ROADMAP.md',
        'AGENTS.md',
        'plan.md',
        'architecture.md',
        '.env.example',
        '.gitignore',
        '.editorconfig',
        '.gitattributes'
    )

    foreach ($requiredFile in $requiredFiles) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            $errors.Add("Missing required file: $requiredFile")
        }
    }

    $trackedFiles = @(git -c "safe.directory=$repositoryRoot" ls-files)
    if ($LASTEXITCODE -ne 0) {
        $errors.Add('Unable to list tracked files.')
        $trackedFiles = @()
    }

    $forbiddenTrackedPatterns = @(
        '^\.env$',
        '^\.env\.(?!example$)',
        '(^|/)data/private/',
        '(^|/)data/imports/',
        '(^|/)uploads/',
        '(^|/)exports/',
        '(^|/)backups/'
    )
    foreach ($trackedFile in $trackedFiles) {
        foreach ($pattern in $forbiddenTrackedPatterns) {
            if ($trackedFile -match $pattern) {
                $errors.Add("Forbidden private/local file is tracked: $trackedFile")
            }
        }
    }

    $actualRootNames = @(Get-ChildItem -LiteralPath . -File | ForEach-Object Name)
    if ('AGENTS.md' -cnotin $actualRootNames) {
        $errors.Add('AGENTS.md must use uppercase repository-standard casing.')
    }
    if ('agents.md' -cin $actualRootNames) {
        $errors.Add('Lowercase agents.md must not coexist with AGENTS.md.')
    }

    $markdownFiles = @($trackedFiles | Where-Object { $_ -match '\.md$' })
    foreach ($markdownFile in $markdownFiles) {
        $content = Get-Content -LiteralPath $markdownFile -Raw
        $fenceCount = ([regex]::Matches($content, '```')).Count
        if (($fenceCount % 2) -ne 0) {
            $errors.Add("Unbalanced code fences: $markdownFile")
        }

        foreach ($match in [regex]::Matches($content, '\[[^\]]+\]\(([^)]+\.md)(?:#[^)]+)?\)')) {
            $relativeTarget = $match.Groups[1].Value
            if ($relativeTarget -match '^https?://') {
                continue
            }
            $sourceDirectory = Split-Path -Parent (Join-Path $repositoryRoot $markdownFile)
            $target = Join-Path $sourceDirectory $relativeTarget
            if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
                $errors.Add("Broken local Markdown link in ${markdownFile}: $relativeTarget")
            }
        }
    }

    $requiredEnvironmentKeys = @(
        'APP_ENV',
        'PERSONAL_MODE',
        'AI_PROVIDER',
        'AI_MONTHLY_BUDGET_USD',
        'AI_BUDGET_HARD_STOP',
        'OLLAMA_BASE_URL',
        'OLLAMA_MODEL',
        'OPENAI_API_KEY',
        'OPENAI_MODEL',
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_MODEL',
        'LINKEDIN_INTEGRATION_ENABLED'
    )
    $environmentTemplate = if (Test-Path -LiteralPath '.env.example') {
        Get-Content -LiteralPath '.env.example' -Raw
    } else {
        ''
    }
    foreach ($environmentKey in $requiredEnvironmentKeys) {
        if ($environmentTemplate -notmatch "(?m)^$([regex]::Escape($environmentKey))=") {
            $errors.Add("Missing environment key: $environmentKey")
        }
    }
    if ($environmentTemplate -notmatch '(?m)^AI_MONTHLY_BUDGET_USD=10\.00$') {
        $errors.Add('Default monthly AI budget must be USD 10.00.')
    }
    if ($environmentTemplate -notmatch '(?m)^AI_PROVIDER=ollama$') {
        $errors.Add('Ollama must be the default AI provider.')
    }

    $credentialPatterns = @(
        'github_pat_[A-Za-z0-9_]{20,}',
        'ghp_[A-Za-z0-9]{20,}',
        'sk-[A-Za-z0-9_-]{20,}',
        '-----BEGIN [A-Z ]*PRIVATE KEY-----'
    )
    foreach ($trackedFile in $trackedFiles) {
        if (-not (Test-Path -LiteralPath $trackedFile -PathType Leaf)) {
            continue
        }
        $fileText = Get-Content -LiteralPath $trackedFile -Raw -ErrorAction SilentlyContinue
        foreach ($pattern in $credentialPatterns) {
            if ($fileText -match $pattern) {
                $errors.Add("Possible credential in tracked file: $trackedFile")
            }
        }
    }

    $jsonlFiles = @(Get-ChildItem -LiteralPath 'evals' -Filter '*.jsonl' -File -ErrorAction SilentlyContinue)
    if ($jsonlFiles.Count -eq 0) {
        $errors.Add('No JSONL evaluation fixtures found.')
    }
    foreach ($jsonlFile in $jsonlFiles) {
        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $jsonlFile.FullName) {
            $lineNumber++
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }
            try {
                $null = $line | ConvertFrom-Json
            } catch {
                $errors.Add("Invalid JSONL in $($jsonlFile.Name) at line $lineNumber")
            }
        }
    }

    if ($errors.Count -gt 0) {
        $errors | ForEach-Object { Write-Error $_ }
        exit 1
    }

    Write-Host "Repository verification passed: $($trackedFiles.Count) tracked files, $($markdownFiles.Count) Markdown files, $($jsonlFiles.Count) JSONL fixture files."
} finally {
    Pop-Location
}
