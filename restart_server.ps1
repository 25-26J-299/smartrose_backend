# Kill all Python processes related to smartrose_backend
Write-Host "Stopping all Python processes..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*smartrose_backend*" -or 
    $_.CommandLine -like "*uvicorn*" -or
    $_.CommandLine -like "*smartrose*"
} | Stop-Process -Force -ErrorAction SilentlyContinue

# Kill processes on port 8000
$ports = netstat -ano | findstr ":8000" | findstr "LISTENING"
foreach ($line in $ports) {
    $processId = ($line -split '\s+')[-1]
    if ($processId -match '^\d+$') {
        Write-Host "Killing process $processId on port 8000..."
        taskkill /F /PID $processId 2>&1 | Out-Null
    }
}

Start-Sleep -Seconds 2

# Verify port is free
$stillListening = netstat -ano | findstr ":8000" | findstr "LISTENING"
if ($stillListening) {
    Write-Host "WARNING: Port 8000 still in use. Please manually stop processes."
    Write-Host $stillListening
} else {
    Write-Host "Port 8000 is now free. You can start the server with:"
    Write-Host "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
}

