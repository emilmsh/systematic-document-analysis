param(
    [string]$Script = 'start_server.py',
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$ScriptArgs
)
$ErrorActionPreference = 'Stop'
try {
    $pluginRoot = Split-Path $PSScriptRoot -Parent
    $runtimeRoot = if ($env:SDA_RUNTIME_DIR) { $env:SDA_RUNTIME_DIR } else { Join-Path $env:LOCALAPPDATA 'systematic-document-analysis\runtime' }
    $selectedPython = $null
    if ($env:SDA_PYTHON) {
        $selectedPython = $env:SDA_PYTHON
    } elseif ($env:SDA_FORCE_MANAGED_PYTHON -ne '1') {
        $candidates = @((Join-Path $pluginRoot '.venv\Scripts\python.exe'))
        $onPath = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($onPath -and $onPath.Source -notlike '*WindowsApps*') { $candidates += $onPath.Source }
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate) {
                & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>$null
                if ($LASTEXITCODE -eq 0) { $selectedPython = $candidate; break }
            }
        }
    }
    if (-not $selectedPython) {
        $uvPath = Join-Path $runtimeRoot 'uv.exe'
        New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
        if (-not (Test-Path -LiteralPath $uvPath)) {
            [Console]::Error.WriteLine('[Systematic Document Analysis] Downloading a private Python runtime. No system Python or PATH changes.')
            $archive = Join-Path $runtimeRoot 'uv-0.12.17.zip'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/download/0.12.17/uv-x86_64-pc-windows-msvc.zip' -OutFile $archive
            if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower() -ne 'a252121d5b59398fcb137c6ea448176459a44010f33f67e0072305a637119ca7') { throw 'Runtime download checksum mismatch.' }
            Expand-Archive -LiteralPath $archive -DestinationPath $runtimeRoot -Force
        }
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $runtimeRoot 'python'
        & $uvPath python install 3.12 --no-bin --no-registry --no-config
        if ($LASTEXITCODE -ne 0) { throw 'Private Python installation failed.' }
        $selectedPython = (& $uvPath python find --managed-python --no-config 3.12 | Select-Object -Last 1)
        if ($LASTEXITCODE -ne 0 -or -not $selectedPython) { throw 'Private Python was not found.' }
    }
    & $selectedPython -X utf8 (Join-Path $PSScriptRoot $Script) @ScriptArgs
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine('[Systematic Document Analysis] Setup failed: ' + $_.Exception.Message)
    exit 1
}
