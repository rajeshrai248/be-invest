@echo off
echo Starting Langfuse deployment...

echo.
echo 1. Starting Langfuse services (Docker)...
cd /d "C:\Users\rajes\PycharmProjects\be-invest - claude"
docker-compose -f docker-compose.langfuse.yml up -d

echo.
echo 2. Waiting for services to be ready...
timeout /t 15 /nobreak

echo.
echo 3. Starting nginx...
cd /d "C:\Users\rajes\Downloads\nginx-1.29.4"
start nginx.exe

echo.
echo 4. Testing services...
timeout /t 5 /nobreak

echo Testing Langfuse backend...
curl -s -I http://localhost:3000 | find "200" && echo "✓ Langfuse backend is running" || echo "✗ Langfuse backend failed"

echo Testing nginx proxy...
curl -s http://localhost/health && echo "✓ Nginx proxy is running" || echo "✗ Nginx proxy failed"

echo.
echo Langfuse deployment completed!
echo.
echo Access Langfuse at: http://localhost/langfuse/
echo Health check: http://localhost/health
echo.
pause
