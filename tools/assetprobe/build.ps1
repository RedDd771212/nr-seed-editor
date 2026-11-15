# build.ps1 -- build probe.dll against Andre.SoulsFormats (manual csc, same reason as regtool)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-Smithbox {
    $root = if ($env:ERTOOLS_ROOT) { $env:ERTOOLS_ROOT } else { 'E:\ERtools' }
    $cands = Get-ChildItem $root -Directory -Filter 'Smithbox*' -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName 'Andre.SoulsFormats.dll') } |
        Sort-Object LastWriteTime -Descending
    if (-not $cands) { throw 'Smithbox not found' }
    return $cands[0].FullName
}

$sdkRoot = 'C:\Program Files\dotnet\sdk'
$sdk = Get-ChildItem $sdkRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
$csc = Join-Path $sdk.FullName 'Roslyn\bincore\csc.dll'
$rt = 'C:\Program Files\dotnet\shared\Microsoft.NETCore.App'
$v = Get-ChildItem $rt -Directory | Where-Object { $_.Name -match '^10\.' } | Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
$skip = 'coreclr|clrjit|clrgc|clrgcexp|clretwrc|hostpolicy|hostfxr|mscord|mscorrc|msquic|Native|DiaSymReader|createdump|ucrtbase'
$refs = Get-ChildItem $v.FullName -Filter '*.dll' | Where-Object { $_.Name -notmatch $skip } | ForEach-Object { "-r:`"$($_.FullName)`"" }

$sb = Find-Smithbox
$outDll = Join-Path $here 'probe.dll'
$cscArgs = @($csc, '-nologo', '-target:exe', "-out:$outDll", '-nostdlib') + $refs + @("-r:$sb\Andre.SoulsFormats.dll", (Join-Path $here 'probe.cs'))

Push-Location $here
try {
    & dotnet @cscArgs
    if ($LASTEXITCODE -ne 0) { throw "compile failed (exit $LASTEXITCODE)" }
} finally { Pop-Location }

$rc = @'
{
  "runtimeOptions": {
    "tfm": "net10.0",
    "framework": { "name": "Microsoft.NETCore.App", "version": "10.0.0" }
  }
}
'@
Set-Content -Path (Join-Path $here 'probe.runtimeconfig.json') -Value $rc -Encoding UTF8
Write-Host "OK -> $outDll"
