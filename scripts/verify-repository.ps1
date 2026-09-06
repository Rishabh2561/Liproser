$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $repositoryRoot

try {
    $errors = [System.Collections.Generic.List[string]]::new()
    $requiredFiles = @(
        'README.md',
        'ROADMAP.md',
        'AGENTS.md',
        'docs/ai-agents.md',
        'plan.md',
        'architecture.md',
        '.env.example',
        '.gitignore',
        '.editorconfig',
        '.gitattributes',
        'pyproject.toml',
        'package.json',
        'pnpm-lock.yaml',
        'apps/api/liproser/main.py',
        'apps/web/app/page.tsx',
        'migrations/versions/0001_v01_profile_optimizer.py'
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
    $obsoleteAgentFiles = @(Get-ChildItem -LiteralPath . -Recurse -File | Where-Object { $_.Name -ceq 'agents.md' })
    foreach ($obsoleteAgentFile in $obsoleteAgentFiles) {
        $errors.Add("Obsolete lowercase agent file found: $($obsoleteAgentFile.FullName)")
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
        'APP_BIND_HOST',
        'AI_PROVIDER',
        'AI_MONTHLY_BUDGET_USD',
        'AI_BUDGET_HARD_STOP',
        'OLLAMA_BASE_URL',
        'OLLAMA_MODEL',
        'OPENAI_API_KEY',
        'OPENAI_MODEL',
        'ANTHROPIC_API_KEY',
        'ANTHROPIC_MODEL',
        'DATABASE_URL',
        'PRIVATE_STORAGE_ROOT',
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
    if ($environmentTemplate -notmatch '(?m)^AI_PROVIDER=unconfigured$') {
        $errors.Add('No AI provider may be active by default.')
    }

    $specificationFiles = @('README.md', 'ROADMAP.md', 'plan.md', 'architecture.md', 'AGENTS.md', 'docs/ai-agents.md')
    foreach ($specificationFile in $specificationFiles) {
        if (-not (Test-Path -LiteralPath $specificationFile -PathType Leaf)) {
            continue
        }
        $specificationText = Get-Content -LiteralPath $specificationFile -Raw
        if ($specificationText -match '(?i)\bswipe(?:-file)?\b') {
            $errors.Add("Obsolete third-party swipe specification in $specificationFile")
        }
        if ($specificationText -match '(?<!SaaS )\bMVP\b') {
            $errors.Add("Ambiguous MVP terminology in $specificationFile; use an explicit release name.")
        }
    }

    $roadmapText = if (Test-Path -LiteralPath 'ROADMAP.md') { Get-Content -LiteralPath 'ROADMAP.md' -Raw } else { '' }
    foreach ($releaseName in @('v0.1', 'v0.2', 'v0.3', 'v0.4', 'v1', 'SaaS MVP')) {
        if ($roadmapText -notmatch [regex]::Escape($releaseName)) {
            $errors.Add("ROADMAP.md is missing release name: $releaseName")
        }
    }

    $architectureText = if (Test-Path -LiteralPath 'architecture.md') { Get-Content -LiteralPath 'architecture.md' -Raw } else { '' }
    if ($architectureText -notmatch '### Future application resources') {
        $errors.Add('architecture.md must explicitly label future application endpoints.')
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
