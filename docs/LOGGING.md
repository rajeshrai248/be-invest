# API Logging Configuration

## Overview
The API now includes comprehensive logging with detailed timestamps (milliseconds), timing information, client IP tracking, and more. The logging system uses a JSON configuration file to ensure all API requests and responses are properly logged to both console and file.

## Log Files Location
All logs are stored in: `logs/` directory in your project root.

### Log Files Generated
1. **logs/api.log** - Main application log with all API requests, responses, and debugging information
2. **logs/uvicorn_access.log** - Uvicorn server access logs with HTTP method, path, status code, and response time

## Log Format
All logs use the following format with **millisecond precision**:
```
YYYY-MM-DD HH:MM:SS.mmm - logger_name - LOG_LEVEL - message
```

Example output in both console and file:
```
2025-12-20 14:35:42.123 - be_invest.api.server - INFO - API Request | Time: 125.45ms | GET /cost-comparison-tables | Status: 200 | Client: 127.0.0.1
2025-12-20 14:35:44.567 - be_invest.sources.llm_extract - DEBUG - Processing LLM response
2025-12-20 14:35:46.890 - be_invest.api.server - INFO - API Request | Time: 4267.00ms | GET /financial-analysis | Status: 200 | Client: 192.168.1.100
```

## What Gets Logged

### API Requests
Every HTTP request is logged with:
- **Time (ms)**: Execution duration in milliseconds (e.g., 125.45ms)
- **Method**: HTTP method (GET, POST, DELETE, etc.)
- **Path**: API endpoint and query parameters
- **Status Code**: HTTP response status (200, 404, 500, etc.)
- **Client IP**: Source IP address making the request

Example:
```
API Request | Time: 125.45ms | GET /cost-comparison-tables?model=claude | Status: 200 | Client: 127.0.0.1
```

### API Errors
When an error occurs, all details are logged:
- **Time (ms)**: Duration before error occurred
- **Method & Path**: Which endpoint failed
- **Error Message**: Description of what went wrong
- **Stack Trace**: Full error traceback for debugging
- **Client IP**: Source IP address

Example:
```
API Error | Time: 2345.67ms | POST /financial-analysis | Error: LLM API timeout | Client: 192.168.1.100
```

### Debug Messages
Detailed debugging information from modules:
```
2025-12-20 14:35:44.567 - be_invest.sources.llm_extract - DEBUG - Sending request to Claude API with model=claude-sonnet-4-20250514
2025-12-20 14:35:46.234 - be_invest.sources.scrape - DEBUG - Scraping broker fees from website
```

## Log Levels

- **DEBUG**: Detailed diagnostic information (scraping, LLM extraction, data processing)
- **INFO**: General informational messages (API requests, completion status)
- **WARNING**: Warning messages (deprecated features, unusual conditions)
- **ERROR**: Error messages (failures, exceptions, errors)

## Console vs File Logging

### Console Output
- **INFO and above** messages are shown in real-time
- Includes API request logs for monitoring
- Clean, readable format for development
- Updates as requests come in

### File Logging (logs/api.log & logs/uvicorn_access.log)
- **All DEBUG and above** messages are logged
- Complete history of all requests, responses, and operations
- Persistent storage survives server restarts
- Useful for debugging production issues

## Configuration Files

### logging_config.json
Located at: `scripts/logging_config.json`

This JSON file configures:
- **Formatters**: How log messages are formatted (includes timestamp with milliseconds)
- **Handlers**: Where logs go (console and file)
- **Loggers**: Which modules log what and at what level
- **Log Files**: Location and encoding (UTF-8)

The JSON format allows Uvicorn to properly integrate with your logging setup.

### run_api.py
Located at: `scripts/run_api.py`

This script:
- Loads the logging configuration from `logging_config.json`
- Ensures the `logs/` directory exists
- Starts the Uvicorn server with proper logging enabled

## Accessing Logs

### View Recent API Logs (PowerShell)
```powershell
# Last 50 lines
Get-Content -Path "logs/api.log" -Tail 50

# Search for specific endpoint
Select-String -Path "logs/api.log" -Pattern "cost-comparison-tables"

# Follow logs in real-time
Get-Content -Path "logs/api.log" -Wait

# View last 100 lines with timestamps
Get-Content -Path "logs/api.log" -Tail 100 | Select-String "2025-12-20"
```

### View Uvicorn Access Logs (PowerShell)
```powershell
Get-Content -Path "logs/uvicorn_access.log" -Tail 50
```

## Example Log Output

When you start the server and make API requests, you'll see logs like this:

**In Console:**
```
2025-12-20 14:35:42.123 - uvicorn.access - INFO - GET /health HTTP/1.1 200
2025-12-20 14:35:42.456 - be_invest.api.server - INFO - API Request | Time: 12.34ms | GET /health | Status: 200 | Client: 127.0.0.1
2025-12-20 14:35:45.789 - be_invest.api.server - INFO - API Request | Time: 3456.78ms | GET /cost-comparison-tables | Status: 200 | Client: 192.168.1.100
```

**In logs/api.log:**
```
2025-12-20 14:35:42.123 - uvicorn - INFO - Uvicorn running on http://0.0.0.0:8000
2025-12-20 14:35:42.123 - uvicorn.access - INFO - GET /health HTTP/1.1 200
2025-12-20 14:35:42.456 - be_invest.api.server - INFO - API Request | Time: 12.34ms | GET /health | Status: 200 | Client: 127.0.0.1
2025-12-20 14:35:42.890 - be_invest.sources.llm_extract - DEBUG - Initializing LLM extractor with model: claude-sonnet-4-20250514
2025-12-20 14:35:45.789 - be_invest.api.server - INFO - API Request | Time: 3456.78ms | GET /cost-comparison-tables | Status: 200 | Client: 192.168.1.100
```

**In logs/uvicorn_access.log:**
```
2025-12-20 14:35:42.123 - uvicorn.access - INFO - GET /health HTTP/1.1 200
2025-12-20 14:35:42.456 - uvicorn.access - INFO - GET /cost-comparison-tables HTTP/1.1 200
```

## Performance Tracking

The logging system provides multiple ways to track API performance:

1. **Request Duration (milliseconds)**: Total time from request start to response
   - Visible in console and file logs
   - Example: `Time: 125.45ms`

2. **Endpoint Execution Time (seconds)**: Processing time of specific endpoint functions
   - Logged when endpoint completes
   - Example: `completed in 3.850s`

3. **Debug-Level Timing**: Time spent in LLM calls, scraping, data processing
   - Only visible when debug logging is enabled
   - Useful for identifying bottlenecks

## Adjusting Log Levels

To modify logging behavior, edit `scripts/logging_config.json`:

### Increase Verbosity (More Debug Info)
```json
"be_invest": {
  "level": "DEBUG"  // Change from INFO to DEBUG
}
```

### Decrease Verbosity (Less Noise)
```json
"be_invest.sources.scrape": {
  "level": "WARNING"  // Only show warnings and errors
}
```

### Disable Specific Module Logging
```json
"be_invest.sources.llm_extract": {
  "handlers": ["file"],  // Remove "default" to hide from console
  "level": "WARNING"
}
```

## Filtering Logs

### Find All Errors
```powershell
Select-String -Path "logs/api.log" -Pattern "ERROR"
```

### Find Slow API Calls (> 1 second)
```powershell
Select-String -Path "logs/api.log" -Pattern "API Request" | 
  Where-Object {[regex]::Match($_.Line, '(\d+\.\d+)ms').Groups[1].Value -gt 1000}
```

### Find Specific Endpoint Requests
```powershell
Select-String -Path "logs/api.log" -Pattern "GET /cost-comparison"
```

### Find All Requests from Specific Client
```powershell
Select-String -Path "logs/api.log" -Pattern "Client: 192.168.1.100"
```

## Log File Management

### Current Log File Size
```powershell
Get-Item "logs/api.log" | Select-Object -ExpandProperty Length
```

### Archive Old Logs
```powershell
# Create archive of logs older than 7 days
Get-ChildItem "logs/*.log" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | 
  Copy-Item -Destination "logs/archive/"
```

### Clear Old Logs
```powershell
# Delete logs older than 30 days
Get-ChildItem "logs/*.log" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | 
  Remove-Item
```

## Log File Rotation

Currently, logs append to the same file. To implement log rotation, edit `scripts/logging_config.json`:

```json
"file": {
  "class": "logging.handlers.RotatingFileHandler",
  "filename": "logs/api.log",
  "maxBytes": 10485760,
  "backupCount": 5,
  "formatter": "detailed",
  "encoding": "utf-8"
}
```

This configuration:
- Rotates when log file reaches 10MB
- Keeps 5 backup files (api.log.1, api.log.2, etc.)
- Automatically manages old log files

## Troubleshooting

### No Logs Appearing
1. Check that the server is running
2. Make an API request: `curl http://localhost:8000/health`
3. Wait a moment for logs to flush to disk
4. Check that `logs/` directory exists and is writable

### Logs Not in Console
- Verify `be_invest.api.server` level is `INFO` in `logging_config.json`
- Check that console handler is attached to the logger
- Ensure handler level is `INFO` or lower

### Logs Not in File
- Verify file handler path is correct: `logs/api.log`
- Check that `logs/` directory is writable
- Check disk space
- Verify `encoding: "utf-8"` is set in file handler

### Empty Log Files
- API requests must be made for logs to appear
- Server must be running
- Check timestamps to see if logs are being written

### Encoding Issues (Special Characters)
- UTF-8 encoding is configured in `logging_config.json`
- Windows console may not display all characters, but file logs will be correct

## Best Practices

1. **Monitor Console During Development**
   - Real-time feedback on API requests
   - Quick identification of errors

2. **Check Files for Debugging**
   - Complete history with debug-level details
   - Search for specific patterns or timeframes

3. **Adjust Log Levels**
   - Use INFO in production for better performance
   - Use DEBUG during development and troubleshooting

4. **Track Performance**
   - Use millisecond timestamps to identify slow requests
   - Watch for patterns in response times

5. **Log Client IPs**
   - Identify problematic clients
   - Spot abuse patterns

6. **Use Timestamps for Correlation**
   - Match request/response logs with external systems
   - Create timeline of events

