# Langfuse Nginx Deployment Guide

## Overview
Deploy Langfuse server via Docker with nginx reverse proxy at `/langfuse/` path.

## Current Setup
- **nginx location**: `C:\Users\rajes\Downloads\nginx-1.29.4`
- **Langfuse**: Docker-compose configuration already exists
- **Target URL**: `http://localhost/langfuse/`

## Step 1: Update Langfuse Docker Configuration

First, update the existing docker-compose to work properly with nginx proxy:

```yaml
# File: docker-compose.langfuse.yml (update NEXTAUTH_URL)
version: "3.8"

services:
  langfuse-server:
    image: langfuse/langfuse:3
    depends_on:
      langfuse-db:
        condition: service_healthy
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      - NEXTAUTH_SECRET=mysecret
      - SALT=mysalt
      - ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000
      - NEXTAUTH_URL=http://localhost/langfuse  # Updated for nginx proxy
      - TELEMETRY_ENABLED=false
    restart: unless-stopped

  langfuse-db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=langfuse
      - POSTGRES_PASSWORD=langfuse
      - POSTGRES_DB=langfuse
    ports:
      - "5433:5432"
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped

volumes:
  langfuse_pgdata:
```

## Step 2: Create Nginx Configuration

### Main nginx.conf
Replace `C:\Users\rajes\Downloads\nginx-1.29.4\conf\nginx.conf`:

```nginx
# nginx.conf - Langfuse deployment
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log  logs/access.log  main;
    error_log   logs/error.log;

    # Basic settings
    sendfile        on;
    keepalive_timeout  65;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/atom+xml
        image/svg+xml
        application/json;

    # Rate limiting for Langfuse
    limit_req_zone $binary_remote_addr zone=langfuse:10m rate=5r/s;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";

    # Upstream for Langfuse
    upstream langfuse_backend {
        server 127.0.0.1:3000;
        keepalive 32;
    }

    # Main server block
    server {
        listen       80;
        server_name  localhost;
        
        # Root redirect to Langfuse
        location = / {
            return 301 /langfuse/;
        }
        
        # Langfuse observability platform
        location /langfuse/ {
            limit_req zone=langfuse burst=20 nodelay;
            
            proxy_pass http://langfuse_backend/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Prefix /langfuse;
            
            # WebSocket support for real-time features
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
            
            # Buffer settings
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
        }
        
        # Health check endpoint
        location /health {
            access_log off;
            return 200 "Langfuse proxy OK\n";
            add_header Content-Type text/plain;
        }
        
        # Security - block common attack paths
        location ~ /\.(ht|git|svn) {
            deny all;
            return 404;
        }
        
        location ~ /(wp-admin|wp-content|wp-includes|phpmyadmin) {
            deny all;
            return 404;
        }
        
        # Error pages
        error_page   500 502 503 504  /50x.html;
        location = /50x.html {
            root   html;
        }
    }
}
```

## Step 3: Create Deployment Scripts

### Start Langfuse Script
Create `C:\Users\rajes\PycharmProjects\start-langfuse.bat`:

```batch
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
```

### Stop Langfuse Script
Create `C:\Users\rajes\PycharmProjects\stop-langfuse.bat`:

```batch
@echo off
echo Stopping Langfuse deployment...

echo.
echo 1. Stopping nginx...
cd /d "C:\Users\rajes\Downloads\nginx-1.29.4"
nginx.exe -s quit
echo Nginx stopped.

echo.
echo 2. Stopping Docker services...
cd /d "C:\Users\rajes\PycharmProjects\be-invest - claude"
docker-compose -f docker-compose.langfuse.yml down
echo Docker services stopped.

echo.
echo All services stopped!
pause
```

### Test Langfuse Script
Create `C:\Users\rajes\PycharmProjects\test-langfuse.bat`:

```batch
@echo off
echo Testing Langfuse deployment...

echo.
echo 1. Testing nginx health endpoint...
curl -s http://localhost/health
echo.

echo 2. Testing Langfuse direct access...
curl -s -I http://localhost:3000 | find "200" && echo "✓ Direct Langfuse access works" || echo "✗ Direct Langfuse access failed"

echo.
echo 3. Testing Langfuse via nginx proxy...
curl -s -I http://localhost/langfuse/ | find "200" && echo "✓ Nginx proxy to Langfuse works" || echo "✗ Nginx proxy to Langfuse failed"

echo.
echo 4. Testing database connection...
cd /d "C:\Users\rajes\PycharmProjects\be-invest - claude"
docker-compose -f docker-compose.langfuse.yml exec -T langfuse-db pg_isready -U langfuse && echo "✓ Database is ready" || echo "✗ Database connection failed"

echo.
echo Test completed!
pause
```

## Step 4: Implementation Instructions

1. **Update Docker Compose**:
   ```bash
   # Edit docker-compose.langfuse.yml to change NEXTAUTH_URL
   NEXTAUTH_URL=http://localhost/langfuse
   ```

2. **Replace nginx configuration**:
   - Backup existing: `copy conf\nginx.conf conf\nginx.conf.backup`
   - Replace with the new configuration above

3. **Create batch files**:
   - `start-langfuse.bat`
   - `stop-langfuse.bat` 
   - `test-langfuse.bat`

4. **Deploy**:
   ```bash
   # Run the start script
   start-langfuse.bat
   ```

5. **Verify**:
   - Open browser to `http://localhost/langfuse/`
   - Should see Langfuse login/dashboard
   - Check `http://localhost/health` for proxy status

## Step 5: Troubleshooting

### Common Issues

**Langfuse not accessible via nginx**:
```bash
# Check nginx logs
tail -f C:\Users\rajes\Downloads\nginx-1.29.4\logs\error.log

# Check if Langfuse is running directly
curl http://localhost:3000
```

**Database connection issues**:
```bash
# Check database status
docker-compose -f docker-compose.langfuse.yml logs langfuse-db

# Reset database if needed
docker-compose -f docker-compose.langfuse.yml down -v
docker-compose -f docker-compose.langfuse.yml up -d
```

**Port conflicts**:
```bash
# Check what's using port 3000
netstat -ano | findstr :3000

# Check what's using port 80
netstat -ano | findstr :80
```

### Logs Locations
- **Nginx logs**: `C:\Users\rajes\Downloads\nginx-1.29.4\logs\`
- **Docker logs**: `docker-compose -f docker-compose.langfuse.yml logs`

## Expected Result

After successful deployment:
- **Langfuse UI**: `http://localhost/langfuse/` → Full Langfuse dashboard
- **Health check**: `http://localhost/health` → "Langfuse proxy OK"
- **Direct access**: `http://localhost:3000` → Also works (bypass nginx)

The nginx proxy provides:
- ✅ Clean URLs at `/langfuse/` path
- ✅ Rate limiting and security headers
- ✅ WebSocket support for real-time features  
- ✅ Proper error handling and logging
- ✅ Easy integration with other services later
