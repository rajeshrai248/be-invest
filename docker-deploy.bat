@echo off
REM Be-Invest Docker Deployment Helper Script for Windows
REM This script helps with common Docker deployment tasks

setlocal enabledelayedexpansion

REM Display usage
if "%1"=="" (
    call :usage
    exit /b 0
)

if /i "%1"=="check" (
    call :check_docker
    call :check_docker_compose
    call :check_env_file
    echo.
    echo [SUCCESS] All prerequisites met!
    exit /b 0
)

if /i "%1"=="setup" (
    call :print_header "Be-Invest Docker Setup"
    call :check_docker
    call :check_docker_compose
    call :check_env_file
    call :build_images
    call :start_services
    call :check_health
    echo.
    echo [SUCCESS] Setup complete!
    echo.
    echo Next steps:
    echo 1. Edit .env file with your API keys
    echo 2. Initialize Langfuse at: http://localhost:3000
    echo 3. Access API at: http://localhost:8000/docs
    exit /b 0
)

if /i "%1"=="build" (
    call :check_docker
    call :check_docker_compose
    call :build_images
    exit /b 0
)

if /i "%1"=="start" (
    call :check_docker
    call :check_docker_compose
    call :check_env_file
    call :start_services
    echo.
    echo Waiting 5 seconds for services to start...
    timeout /t 5 /nobreak
    call :check_health
    exit /b 0
)

if /i "%1"=="stop" (
    call :check_docker
    call :check_docker_compose
    call :stop_services
    exit /b 0
)

if /i "%1"=="restart" (
    call :check_docker
    call :check_docker_compose
    call :restart_services
    exit /b 0
)

if /i "%1"=="logs" (
    call :check_docker
    call :check_docker_compose
    if "%2"=="" (
        call :print_header "Viewing All Logs"
        docker-compose logs -f
    ) else (
        call :print_header "Viewing %2 Logs"
        docker-compose logs -f %2
    )
    exit /b 0
)

if /i "%1"=="health" (
    call :check_docker
    call :check_docker_compose
    call :check_health
    exit /b 0
)

if /i "%1"=="endpoints" (
    call :list_endpoints
    exit /b 0
)

if /i "%1"=="cleanup" (
    call :check_docker
    call :check_docker_compose
    call :cleanup
    exit /b 0
)

if /i "%1"=="help" (
    call :usage
    exit /b 0
)

echo [ERROR] Unknown command: %1
call :usage
exit /b 1

REM ==================== Subroutines ====================

:usage
echo Be-Invest Docker Deployment Helper for Windows
echo.
echo Usage: docker-deploy.bat [COMMAND]
echo.
echo Commands:
echo   setup          - Run full setup (recommended for first time)
echo   check          - Check prerequisites and Docker installation
echo   build          - Build Docker images
echo   start          - Start all services
echo   stop           - Stop all services
echo   restart        - Restart all services
echo   logs [service] - View service logs (service: be-invest, langfuse-server, langfuse-db)
echo   health         - Check health of all services
echo   endpoints      - List all API endpoints
echo   cleanup        - Stop and remove services
echo   help           - Show this help message
echo.
echo Examples:
echo   docker-deploy.bat setup
echo   docker-deploy.bat start
echo   docker-deploy.bat logs be-invest
echo   docker-deploy.bat health
exit /b 0

:check_docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed
    echo Please install Docker from: https://www.docker.com/products/docker-desktop
    exit /b 1
)
for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VER=%%i
echo [SUCCESS] %DOCKER_VER%
exit /b 0

:check_docker_compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed
    echo Please install Docker Compose from: https://docs.docker.com/compose/install/
    exit /b 1
)
for /f "tokens=*" %%i in ('docker-compose --version') do set DOCKER_COMPOSE_VER=%%i
echo [SUCCESS] %DOCKER_COMPOSE_VER%
exit /b 0

:check_env_file
if not exist .env (
    echo [ERROR] .env file not found
    if exist .env.example (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
        echo [SUCCESS] .env file created
        echo [INFO] Please edit .env with your API keys
    ) else (
        echo [ERROR] .env.example not found
        exit /b 1
    )
) else (
    echo [SUCCESS] .env file exists
)
exit /b 0

:build_images
call :print_header "Building Docker Images"
docker-compose build
if errorlevel 1 (
    echo [ERROR] Failed to build Docker images
    exit /b 1
)
echo [SUCCESS] Docker images built successfully
exit /b 0

:start_services
call :print_header "Starting Services"
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start services
    exit /b 1
)
echo [SUCCESS] Services started
exit /b 0

:stop_services
call :print_header "Stopping Services"
docker-compose stop
if errorlevel 1 (
    echo [ERROR] Failed to stop services
    exit /b 1
)
echo [SUCCESS] Services stopped
exit /b 0

:restart_services
call :print_header "Restarting Services"
docker-compose restart
if errorlevel 1 (
    echo [ERROR] Failed to restart services
    exit /b 1
)
echo [SUCCESS] Services restarted
exit /b 0

:check_health
call :print_header "Checking Service Health"
echo.
echo Checking Docker containers...
docker-compose ps
echo.
echo Testing be-invest API...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] be-invest is not responding
    exit /b 1
)
echo [SUCCESS] be-invest is running (http://localhost:8000)
echo.
echo Testing Langfuse...
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Langfuse is not responding
    exit /b 1
)
echo [SUCCESS] Langfuse is running (http://localhost:3000)
exit /b 0

:list_endpoints
call :print_header "Be-Invest API Endpoints"
echo.
echo Health ^& Status:
echo   GET /health
echo.
echo Brokers:
echo   GET /brokers
echo   GET /cost-analysis
echo   GET /cost-analysis/{broker_name}
echo.
echo Cost Comparison:
echo   GET /cost-comparison-tables
echo   POST /refresh-and-analyze
echo.
echo Financial Analysis:
echo   GET /financial-analysis
echo.
echo News:
echo   GET /news
echo   GET /news/broker/{broker_name}
echo   GET /news/recent
echo   POST /news/scrape
echo   POST /news
echo   DELETE /news
echo.
echo Chat:
echo   POST /chat
echo.
echo Documentation:
echo   GET /docs ^(Swagger UI^)
echo   GET /redoc ^(ReDoc^)
exit /b 0

:cleanup
call :print_header "Cleanup Options"
echo.
echo 1 - Stop containers only (preserve data)
echo 2 - Remove containers (preserve volumes)
echo 3 - Remove everything including volumes (DESTRUCTIVE)
echo.
set /p choice="Select option (1-3): "
if "%choice%"=="1" (
    echo [INFO] Stopping containers...
    docker-compose stop
    echo [SUCCESS] Containers stopped
) else if "%choice%"=="2" (
    echo [INFO] Removing containers...
    docker-compose down
    echo [SUCCESS] Containers removed
) else if "%choice%"=="3" (
    echo [ERROR] WARNING: This will delete all data including Langfuse database!
    set /p confirm="Are you sure? Type 'yes' to confirm: "
    if "!confirm!"=="yes" (
        docker-compose down -v
        echo [SUCCESS] All services and data removed
    ) else (
        echo [INFO] Cleanup cancelled
    )
) else (
    echo [ERROR] Invalid option
)
exit /b 0

:print_header
echo.
echo ==================================================
echo %1
echo ==================================================
exit /b 0
