# start.ps1 — ReclaimAgent ko hamesha FRESH chalao (backend + latest UI).
#
#   powershell -ExecutionPolicy Bypass -File .\start.ps1
#   (ya bas start.bat pe double-click)
#
# Kya karta hai:
#   1. Port 8000 (FastAPI) aur 5173 (Vite) pe chal rahe PURANE servers band karta hai
#      — wahi stale UI dikhane ki asli wajah hote hain.
#   2. Backend aur frontend dono ko nayi windows mein start karta hai.
#   3. Browser mein sahi URL kholta hai: http://127.0.0.1:5173

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($procId in ($conns.OwningProcess | Sort-Object -Unique)) {
        Write-Host "Port $port pe purana process (pid $procId) band kar raha hoon..."
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

Write-Host "Backend start: http://127.0.0.1:8000"
Start-Process powershell -WorkingDirectory $root -ArgumentList @(
    '-NoExit', '-Command', 'python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload'
)

Write-Host "Frontend start: http://127.0.0.1:5173"
Start-Process powershell -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList @(
    '-NoExit', '-Command', 'npm run dev'
)

# Vite ready hone tak ruko, phir browser kholo
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:5173/ | Out-Null; break } catch {}
}
Start-Process 'http://127.0.0.1:5173'
Write-Host "Done. Agar purana UI dikhe to browser mein Ctrl+Shift+R dabao."
