@echo off
echo Iniciando o servidor de desenvolvimento do Frontend (Next.js)...
cd frontend

echo O navegador vai abrir automaticamente em 5 segundos...
start "" cmd /c "timeout /t 5 >nul && start http://localhost:3000"

npm run dev
pause
