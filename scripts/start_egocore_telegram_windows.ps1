$root = "D:\Project\AIProject\MyProject\Ego\EgoCore"
$openEmotion = "D:\Project\AIProject\MyProject\Ego\OpenEmotion"
$stdout = Join-Path $root "logs\egocore_run.log"
$stderr = Join-Path $root "logs\egocore_err.log"

if (Test-Path $stdout) {
    Remove-Item $stdout -Force
}
if (Test-Path $stderr) {
    Remove-Item $stderr -Force
}

$env:PYTHONPATH = $openEmotion
$process = Start-Process `
    -FilePath "py" `
    -ArgumentList "-3", "-u", "-m", "app.main", "--telegram" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Write-Output $process.Id
