#!/bin/bash

# Be-Invest Docker Deployment Helper Script
# This script helps with common Docker deployment tasks

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker from: https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    print_success "Docker is installed: $(docker --version)"
}

check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        echo "Please install Docker Compose from: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose is installed: $(docker-compose --version)"
}

check_docker_daemon() {
    if ! docker ps > /dev/null 2>&1; then
        print_error "Docker daemon is not running"
        echo "Please start Docker Desktop or the Docker daemon"
        exit 1
    fi
    print_success "Docker daemon is running"
}

check_env_file() {
    if [ ! -f .env ]; then
        print_error ".env file not found"
        print_info "Creating .env from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success ".env file created"
            print_info "Please edit .env with your API keys"
        else
            print_error ".env.example not found"
            exit 1
        fi
    else
        print_success ".env file exists"
    fi
}

build_images() {
    print_header "Building Docker Images"
    docker-compose build
    print_success "Docker images built successfully"
}

start_services() {
    print_header "Starting Services"
    docker-compose up -d
    print_success "Services started"
    print_info "Waiting for services to be ready..."
    sleep 5
}

stop_services() {
    print_header "Stopping Services"
    docker-compose stop
    print_success "Services stopped"
}

restart_services() {
    print_header "Restarting Services"
    docker-compose restart
    print_success "Services restarted"
}

view_logs() {
    local service=$1
    if [ -z "$service" ]; then
        print_header "Viewing All Logs"
        docker-compose logs -f
    else
        print_header "Viewing $service Logs"
        docker-compose logs -f "$service"
    fi
}

check_health() {
    print_header "Checking Service Health"
    
    echo ""
    echo "Checking Docker containers..."
    docker-compose ps
    
    echo ""
    echo "Testing be-invest API..."
    if curl -s http://localhost:8000/health > /dev/null; then
        print_success "be-invest is running (http://localhost:8000)"
    else
        print_error "be-invest is not responding"
        return 1
    fi
    
    echo ""
    echo "Testing Langfuse..."
    if curl -s http://localhost:3000 > /dev/null; then
        print_success "Langfuse is running (http://localhost:3000)"
    else
        print_error "Langfuse is not responding"
        return 1
    fi
}

list_endpoints() {
    print_header "Be-Invest API Endpoints"
    echo ""
    echo "Health & Status:"
    echo "  GET /health"
    echo ""
    echo "Brokers:"
    echo "  GET /brokers"
    echo "  GET /cost-analysis"
    echo "  GET /cost-analysis/{broker_name}"
    echo ""
    echo "Cost Comparison:"
    echo "  GET /cost-comparison-tables"
    echo "  POST /refresh-and-analyze"
    echo ""
    echo "Financial Analysis:"
    echo "  GET /financial-analysis"
    echo ""
    echo "News:"
    echo "  GET /news"
    echo "  GET /news/broker/{broker_name}"
    echo "  GET /news/recent"
    echo "  POST /news/scrape"
    echo "  POST /news"
    echo "  DELETE /news"
    echo ""
    echo "Chat:"
    echo "  POST /chat"
    echo ""
    echo "Documentation:"
    echo "  GET /docs (Swagger UI)"
    echo "  GET /redoc (ReDoc)"
}

cleanup() {
    print_header "Cleanup Options"
    echo ""
    echo "1) Stop containers only (preserve data)"
    echo "2) Remove containers (preserve volumes)"
    echo "3) Remove everything including volumes (DESTRUCTIVE)"
    echo ""
    read -p "Select option (1-3): " choice
    
    case $choice in
        1)
            print_info "Stopping containers..."
            docker-compose stop
            print_success "Containers stopped"
            ;;
        2)
            print_info "Removing containers..."
            docker-compose down
            print_success "Containers removed"
            ;;
        3)
            print_error "WARNING: This will delete all data including Langfuse database!"
            read -p "Are you sure? Type 'yes' to confirm: " confirm
            if [ "$confirm" = "yes" ]; then
                docker-compose down -v
                print_success "All services and data removed"
            else
                print_info "Cleanup cancelled"
            fi
            ;;
        *)
            print_error "Invalid option"
            ;;
    esac
}

# Display usage
usage() {
    echo "Be-Invest Docker Deployment Helper"
    echo ""
    echo "Usage: ./docker-deploy.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup          - Run full setup (recommended for first time)"
    echo "  check          - Check prerequisites and Docker installation"
    echo "  build          - Build Docker images"
    echo "  start          - Start all services"
    echo "  stop           - Stop all services"
    echo "  restart        - Restart all services"
    echo "  logs [service] - View service logs (service: be-invest, langfuse-server, langfuse-db)"
    echo "  health         - Check health of all services"
    echo "  endpoints      - List all API endpoints"
    echo "  cleanup        - Stop and remove services"
    echo "  help           - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./docker-deploy.sh setup"
    echo "  ./docker-deploy.sh start"
    echo "  ./docker-deploy.sh logs be-invest"
    echo "  ./docker-deploy.sh health"
}

# Main script logic
main() {
    local command=${1:-help}
    
    case $command in
        check)
            check_docker
            check_docker_compose
            check_docker_daemon
            check_env_file
            print_success "All prerequisites met!"
            ;;
        setup)
            print_header "Be-Invest Docker Setup"
            check_docker
            check_docker_compose
            check_docker_daemon
            check_env_file
            build_images
            start_services
            check_health
            print_success "Setup complete!"
            echo ""
            echo "Next steps:"
            echo "1. Edit .env file with your API keys"
            echo "2. Initialize Langfuse at: http://localhost:3000"
            echo "3. Access API at: http://localhost:8000/docs"
            ;;
        build)
            check_docker
            check_docker_compose
            build_images
            ;;
        start)
            check_docker
            check_docker_compose
            check_docker_daemon
            check_env_file
            start_services
            check_health
            ;;
        stop)
            check_docker
            check_docker_compose
            stop_services
            ;;
        restart)
            check_docker
            check_docker_compose
            restart_services
            ;;
        logs)
            check_docker
            check_docker_compose
            view_logs "$2"
            ;;
        health)
            check_docker
            check_docker_compose
            check_health
            ;;
        endpoints)
            list_endpoints
            ;;
        cleanup)
            check_docker
            check_docker_compose
            cleanup
            ;;
        help)
            usage
            ;;
        *)
            print_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
