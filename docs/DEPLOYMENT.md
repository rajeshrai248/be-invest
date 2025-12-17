# Deployment Guide

> Complete guide for deploying BE-Invest in various environments from local development to production.

## Table of Contents

- [Local Development](#local-development)
- [Vercel Deployment](#vercel-deployment)  
- [Docker Deployment](#docker-deployment)
- [AWS Deployment](#aws-deployment)
- [Environment Configuration](#environment-configuration)
- [Production Considerations](#production-considerations)
- [Monitoring and Logging](#monitoring-and-logging)
- [Troubleshooting](#troubleshooting)

## Local Development

### Quick Setup

```bash
# Clone and setup
git clone https://github.com/your-username/be-invest.git
cd be-invest

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start development server
uvicorn be_invest.api.server:app --reload --port 8000
```

### Development Environment Variables

Create `.env` file:

```env
# LLM API Keys (required for extraction features)
OPENAI_API_KEY=your-openai-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here

# Development Settings
DEBUG=true
LOG_LEVEL=INFO
ENVIRONMENT=development

# API Configuration
API_HOST=localhost
API_PORT=8000

# Cache Configuration
CACHE_DIR=data/cache
CACHE_TTL_HOURS=24

# Data Sources
BROKER_CONFIG_PATH=data/brokers.yaml
OUTPUT_DIR=data/output
```

### Running Components

```bash
# API Server (development mode)
uvicorn be_invest.api.server:app --reload --port 8000

# Run analysis pipeline
python scripts/analyze_broker_fees.py

# Run validation tests
python tests/test_llm_extraction_validation.py

# Generate comprehensive report
python scripts/final_verification.py
```

### Development Tools

```bash
# Code formatting
black src/ tests/ scripts/

# Linting
flake8 src/ tests/ scripts/

# Type checking
mypy src/

# Run tests
pytest tests/ -v

# Test coverage
pytest tests/ --cov=src/be_invest --cov-report=html
```

## Vercel Deployment

### Project Setup

Vercel provides serverless deployment with automatic scaling and global CDN.

**Prerequisites:**
- Vercel account
- Node.js (for Vercel CLI)
- Git repository

### Installation

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login
```

### Configuration Files

Create `vercel.json`:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python",
      "config": {
        "maxLambdaSize": "50mb",
        "runtime": "python3.11"
      }
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "/api/index.py"
    },
    {
      "src": "/(.*)",
      "dest": "/api/index.py"
    }
  ],
  "env": {
    "PYTHONPATH": "/var/task/src"
  },
  "functions": {
    "api/index.py": {
      "includeFiles": [
        "src/**",
        "data/**",
        "requirements.txt"
      ]
    }
  }
}
```

Create `api/index.py` (Vercel entry point):

```python
"""
Vercel serverless function entrypoint.
"""
import sys
import os
from pathlib import Path

# Add paths for Vercel deployment
current_dir = Path(__file__).parent
root_dir = current_dir.parent
src_dir = root_dir / "src"

for path in [str(src_dir), str(root_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import FastAPI app
from be_invest.api.server import app

# Export for Vercel
__all__ = ["app"]
```

### Environment Variables

Configure in Vercel Dashboard or CLI:

```bash
# Using Vercel CLI
vercel env add OPENAI_API_KEY
vercel env add ANTHROPIC_API_KEY
vercel env add ENVIRONMENT production
vercel env add LOG_LEVEL INFO
vercel env add CACHE_TTL_HOURS 24
```

### Deployment

```bash
# Deploy to preview
vercel

# Deploy to production
vercel --prod

# Check deployment status
vercel ls

# View logs
vercel logs
```

### Custom Domain Setup

```bash
# Add custom domain
vercel domains add your-domain.com

# Configure DNS
# Add CNAME record: your-domain.com -> vercel-domain.vercel.app
```

## Docker Deployment

### Dockerfile

Create optimized production Dockerfile:

```dockerfile
# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH for local packages
ENV PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

# Create cache directory
RUN mkdir -p /app/data/cache && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start application
CMD ["uvicorn", "be_invest.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

Create `docker-compose.yml` for local development:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=development
      - LOG_LEVEL=INFO
    volumes:
      - ./data/cache:/app/data/cache
      - ./data/output:/app/data/output
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  cache_data:
  output_data:
```

### Production Docker Compose

```yaml
version: '3.8'

services:
  api:
    image: your-registry/be-invest:latest
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=WARNING
    env_file:
      - .env.production
    volumes:
      - cache_data:/app/data/cache
      - output_data:/app/data/output
    restart: always
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
      - output_data:/usr/share/nginx/html/reports:ro
    depends_on:
      - api
    restart: always

  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_POLL_INTERVAL=300
      - WATCHTOWER_CLEANUP=true
    restart: always

volumes:
  cache_data:
  output_data:
```

### Building and Running

```bash
# Build image
docker build -t be-invest:latest .

# Run locally
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="your-key" \
  -v $(pwd)/data/cache:/app/data/cache \
  be-invest:latest

# Using docker-compose
docker-compose up -d

# Scale services
docker-compose up -d --scale api=3

# View logs
docker-compose logs -f api

# Update and restart
docker-compose pull && docker-compose up -d
```

## AWS Deployment

### AWS Lambda (Serverless)

Use AWS SAM for Lambda deployment:

Create `template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Globals:
  Function:
    Timeout: 30
    MemorySize: 1024
    Runtime: python3.11
    Environment:
      Variables:
        ENVIRONMENT: production
        LOG_LEVEL: INFO

Resources:
  BeInvestApi:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: lambda_handler.handler
      Events:
        ApiGateway:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY
      Environment:
        Variables:
          OPENAI_API_KEY: !Ref OpenAIApiKey
          ANTHROPIC_API_KEY: !Ref AnthropicApiKey
      
  ApiGatewayDomain:
    Type: AWS::ApiGateway::DomainName
    Properties:
      DomainName: !Ref CustomDomain
      CertificateArn: !Ref SSLCertificate

Parameters:
  OpenAIApiKey:
    Type: String
    NoEcho: true
    
  AnthropicApiKey:
    Type: String
    NoEcho: true
    
  CustomDomain:
    Type: String
    Default: api.your-domain.com
    
  SSLCertificate:
    Type: String
```

Create `lambda_handler.py`:

```python
"""AWS Lambda handler for BE-Invest API."""
import os
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from mangum import Mangum
from be_invest.api.server import app

# Configure for Lambda
handler = Mangum(app, lifespan="off")
```

Deploy with SAM:

```bash
# Build
sam build

# Deploy
sam deploy --guided

# Update
sam deploy
```

### AWS ECS (Container Service)

Create ECS task definition:

```json
{
  "family": "be-invest-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "be-invest-api",
      "image": "your-account.dkr.ecr.region.amazonaws.com/be-invest:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/be-invest",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

## Environment Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM extraction | No* | None |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM extraction | No* | None |
| `ENVIRONMENT` | Deployment environment | Yes | development |
| `LOG_LEVEL` | Logging level | No | INFO |
| `API_HOST` | API server host | No | localhost |
| `API_PORT` | API server port | No | 8000 |
| `CACHE_DIR` | Cache directory path | No | data/cache |
| `CACHE_TTL_HOURS` | Cache TTL in hours | No | 24 |
| `OUTPUT_DIR` | Output directory for reports | No | data/output |
| `MAX_CONCURRENT_EXTRACTIONS` | Max concurrent LLM calls | No | 3 |
| `REQUEST_TIMEOUT_SECONDS` | API request timeout | No | 30 |

*At least one LLM API key required for extraction features

### Configuration Files

**Production `.env`**:
```env
ENVIRONMENT=production
LOG_LEVEL=WARNING
API_HOST=0.0.0.0
API_PORT=8000
CACHE_TTL_HOURS=24
MAX_CONCURRENT_EXTRACTIONS=5
REQUEST_TIMEOUT_SECONDS=60
```

**Staging `.env`**:
```env
ENVIRONMENT=staging
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
CACHE_TTL_HOURS=1
MAX_CONCURRENT_EXTRACTIONS=2
REQUEST_TIMEOUT_SECONDS=30
```

### Security Configuration

```python
# src/be_invest/config.py
import os
from typing import Optional

class SecurityConfig:
    """Security configuration for production deployment."""
    
    # API Keys (use environment variables)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # CORS settings
    ALLOWED_ORIGINS = [
        "https://your-domain.com",
        "https://www.your-domain.com"
    ]
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    
    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'"
    }
```

## Production Considerations

### Performance Optimization

```python
# src/be_invest/api/middleware.py
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

def configure_middleware(app: FastAPI):
    """Configure production middleware."""
    
    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SecurityConfig.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # Trusted hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["your-domain.com", "*.your-domain.com"]
    )
    
    # Security headers
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
```

### Database Configuration

For production, consider adding persistent storage:

```python
# Optional: PostgreSQL for metadata
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost/be_invest"
)

# Redis for caching
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)
```

### Scaling Configuration

```yaml
# Kubernetes deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: be-invest-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: be-invest-api
  template:
    metadata:
      labels:
        app: be-invest-api
    spec:
      containers:
      - name: api
        image: be-invest:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Monitoring and Logging

### Logging Configuration

```python
# src/be_invest/logging_config.py
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Configure structured logging for production."""
    
    # Create formatter
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set library log levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logger
```

### Health Checks

```python
# src/be_invest/api/health.py
from fastapi import APIRouter
from typing import Dict, Any
import time
import os

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check endpoint."""
    
    checks = {}
    overall_status = "healthy"
    
    # Check LLM API availability
    checks["llm_apis"] = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY"))
    }
    
    # Check cache directory
    cache_dir = Path("data/cache")
    checks["cache"] = {
        "accessible": cache_dir.exists() and cache_dir.is_dir(),
        "writable": os.access(cache_dir, os.W_OK) if cache_dir.exists() else False
    }
    
    # Check disk space
    import shutil
    total, used, free = shutil.disk_usage("/")
    checks["disk"] = {
        "free_gb": free // (1024**3),
        "free_percent": (free / total) * 100
    }
    
    # Overall status
    if not any(checks["llm_apis"].values()):
        overall_status = "degraded"
    
    if checks["disk"]["free_percent"] < 10:
        overall_status = "warning"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "version": "0.1.0",
        "checks": checks
    }
```

### Metrics Collection

```python
# Optional: Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest

# Metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration")
LLM_EXTRACTIONS = Counter("llm_extractions_total", "Total LLM extractions", ["broker", "model"])

@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Collect metrics for each request."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    REQUEST_DURATION.observe(duration)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    
    return response

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type="text/plain")
```

## Troubleshooting

### Common Issues

#### 1. LLM API Errors

**Symptoms**: Extraction failures, API timeout errors
**Solutions**:
```bash
# Check API key configuration
echo $OPENAI_API_KEY | head -c 10
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Check rate limits
# Implement exponential backoff
# Use cheaper models for testing
```

#### 2. Memory Issues

**Symptoms**: Out of memory errors, slow performance
**Solutions**:
```python
# Reduce chunk sizes
chunk_chars = 8000  # Instead of 18000

# Limit concurrent extractions
max_concurrent = 1  # Instead of 3

# Clear cache periodically
import shutil
shutil.rmtree("data/cache")
```

#### 3. Docker Issues

**Symptoms**: Container startup failures, permission errors
**Solutions**:
```bash
# Check logs
docker logs container-name

# Debug interactively
docker run -it --entrypoint /bin/bash be-invest:latest

# Fix permissions
chown -R 1000:1000 data/
```

#### 4. Vercel Deployment Issues

**Symptoms**: Function timeouts, cold starts
**Solutions**:
```json
// vercel.json - Increase timeouts
{
  "functions": {
    "api/index.py": {
      "maxDuration": 60
    }
  }
}
```

### Debug Mode

Enable debug mode for detailed logging:

```python
# Environment variable
DEBUG=true

# In code
import logging
logging.basicConfig(level=logging.DEBUG)

# API endpoint for debugging
@app.get("/debug/config")
async def debug_config():
    """Debug configuration endpoint (dev only)."""
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(404)
    
    return {
        "env_vars": dict(os.environ),
        "python_path": sys.path,
        "working_dir": os.getcwd()
    }
```

### Performance Monitoring

```bash
# Monitor resource usage
docker stats

# Check API performance
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8000/api/health

# Monitor logs
tail -f logs/app.log | grep ERROR
```

This deployment guide provides comprehensive instructions for deploying BE-Invest in various environments. Choose the deployment method that best fits your infrastructure requirements and scaling needs.
