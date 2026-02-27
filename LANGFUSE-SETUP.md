# Quick Setup Instructions for Langfuse

## Files Created
✅ `langfuse-nginx-deployment.md` - Complete deployment guide
✅ `start-langfuse.bat` - Start script
✅ `stop-langfuse.bat` - Stop script  
✅ `test-langfuse.bat` - Testing script
✅ `nginx-langfuse.conf` - Nginx configuration
✅ Updated `docker-compose.langfuse.yml` - Fixed NEXTAUTH_URL

## Quick Deployment (3 steps)

### Step 1: Replace Nginx Config
```bash
# Backup current nginx config
copy "C:\Users\rajes\Downloads\nginx-1.29.4\conf\nginx.conf" "C:\Users\rajes\Downloads\nginx-1.29.4\conf\nginx.conf.backup"

# Copy new config
copy "nginx-langfuse.conf" "C:\Users\rajes\Downloads\nginx-1.29.4\conf\nginx.conf"
```

### Step 2: Deploy Langfuse
```bash
# Run the start script
start-langfuse.bat
```

### Step 3: Verify Deployment
Open browser to: `http://localhost/langfuse/`

## Expected Result
- **Langfuse Dashboard**: `http://localhost/langfuse/`
- **Health Check**: `http://localhost/health` → "Langfuse proxy OK"
- **Direct Access**: `http://localhost:3000` (still works)

## If Something Goes Wrong
1. Run `test-langfuse.bat` to diagnose issues
2. Check nginx logs at `C:\Users\rajes\Downloads\nginx-1.29.4\logs\error.log`
3. Check docker logs: `docker-compose -f docker-compose.langfuse.yml logs`
4. Run `stop-langfuse.bat` and try again

## Features Enabled
✅ Clean URL at `/langfuse/` path
✅ Rate limiting (5 requests/sec burst 20)  
✅ Security headers and attack blocking
✅ WebSocket support for real-time features
✅ Proper error handling and logging
✅ Easy start/stop with batch scripts
