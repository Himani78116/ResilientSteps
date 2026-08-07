$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$definesFile = Join-Path $scriptDir 'config\dart_defines.json'

if (-not (Test-Path -LiteralPath $definesFile)) {
    throw "Missing dart define file: $definesFile"
}

flutter run --dart-define-from-file="$definesFile" @args
