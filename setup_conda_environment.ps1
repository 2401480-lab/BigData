$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$envDirectory = Join-Path $projectRoot '.conda\envs\netflix-eda'
$environmentFile = Join-Path $projectRoot 'environment.yml'
$env:CONDARC = Join-Path $projectRoot '.condarc'
$env:CONDA_NO_PLUGINS = 'true'
$condaRoot = Join-Path $projectRoot '.conda'
$env:CONDA_PKGS_DIRS = Join-Path $condaRoot 'pkgs'
$env:CONDA_NOTICES_CACHE_DIR = Join-Path $condaRoot 'notices'
# Conda notices derive their cache location from LOCALAPPDATA on Windows.
$env:LOCALAPPDATA = Join-Path $condaRoot 'localappdata'

$condaCandidates = @(
    (Get-Command conda -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path $env:USERPROFILE 'miniconda3\Scripts\conda.exe'),
    (Join-Path $env:USERPROFILE 'anaconda3\Scripts\conda.exe'),
    'C:\ProgramData\miniconda3\Scripts\conda.exe',
    'C:\ProgramData\anaconda3\Scripts\conda.exe'
) | Where-Object { $_ -and (Test-Path $_) }
$condaCandidates = @($condaCandidates)

if ($condaCandidates.Count -eq 0) {
    throw 'Conda was not found. Install Miniconda or Anaconda and rerun this script.'
}

$condaExe = $condaCandidates[0]
& $condaExe --no-plugins env create --solver classic --prefix $envDirectory --file $environmentFile
if ($LASTEXITCODE -ne 0) {
    throw "Conda environment creation failed. Exit code: $LASTEXITCODE"
}

& $condaExe --no-plugins run --prefix $envDirectory python -m ipykernel install --user --name netflix-eda --display-name 'Python (netflix-eda)'
if ($LASTEXITCODE -ne 0) {
    throw "Jupyter kernel registration failed. Exit code: $LASTEXITCODE"
}

Write-Host "Environment created: $envDirectory"
Write-Host "Restart VS Code, then select Python (netflix-eda)."
