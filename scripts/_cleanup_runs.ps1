$runs = gh run list --limit 200 --json databaseId,status --jq '.[] | select(.status != "in_progress") | .databaseId'
$total = ($runs | Measure-Object).Count
$i = 0
$failed = 0
foreach ($id in $runs) {
    $i++
    gh api -X DELETE "repos/AbuAzad2025/Medical-Centre/actions/runs/$id" 2>$null
    if ($LASTEXITCODE -ne 0) { $failed++ ; Write-Output "FAIL deleting run $id" }
    if ($i % 10 -eq 0) { Write-Output "progress: $i / $total" }
    Start-Sleep -Milliseconds 300
}
Write-Output "DONE deleted=$($total - $failed) failed=$failed"
