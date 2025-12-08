# Vercel Deployment Guide

## Quick Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/rajeshrai248/be-invest)

## Manual Deployment Steps

1. **Install Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**
   ```bash
   vercel login
   ```

3. **Deploy**
   ```bash
   vercel --prod
   ```

## Environment Variables

Set these in your Vercel project settings:

- `OPENAI_API_KEY` - Your OpenAI API key (required for cost analysis)
- `ANTHROPIC_API_KEY` - Your Anthropic API key (optional, for Claude models)

## Endpoints

Once deployed, your API will be available at `https://your-project.vercel.app`:

- `GET /` - Health check
- `GET /brokers` - List all brokers
- `GET /cost-comparison-tables` - Get cost comparison tables
- `GET /financial-analysis` - Get financial analysis
- `POST /refresh-and-analyze` - Refresh PDFs and analyze
- `POST /news/scrape` - Scrape broker news
- `GET /news` - Get all news
- `GET /news/broker/{broker}` - Get news for specific broker

## Limitations

⚠️ **Important**: Vercel serverless functions have limitations:

1. **Execution Time**: 10 seconds (Hobby), 60 seconds (Pro), 300 seconds (Enterprise)
2. **Memory**: 1024 MB (Hobby/Pro), 3008 MB (Enterprise)
3. **No Playwright**: Browser automation (Playwright) won't work in serverless environment

### Recommended Setup

For full functionality (including Playwright for Revolut scraping):
- Use Vercel only for the API endpoints
- Run a separate server (Railway, Render, DigitalOcean) for scraping tasks
- Or use Vercel Edge Functions with Puppeteer

## Files Created for Deployment

- `vercel.json` - Vercel configuration
- `api/index.py` - Serverless function entrypoint
- `requirements.txt` - Python dependencies
- `.vercelignore` - Files to exclude from deployment

## Troubleshooting

### "No fastapi entrypoint found"
✅ Fixed by creating `api/index.py` that imports the app from `be_invest.api.server`

### "ModuleNotFoundError: No module named 'be_invest'"
✅ **Fixed!** This error occurs when Vercel can't find the `be_invest` package.

**Solution implemented:**
1. **Updated `api/index.py`** to add `src/` directory to Python path:
   ```python
   import sys
   from pathlib import Path
   
   root_dir = Path(__file__).parent.parent
   src_dir = root_dir / "src"
   sys.path.insert(0, str(src_dir))
   
   from be_invest.api.server import app
   ```

2. **Created `setup.py`** for proper package installation

3. **Updated `vercel.json`** to set `PYTHONPATH` environment variable

4. **Updated `.vercelignore`** to ensure `src/` directory is included

### Import errors
Make sure `requirements.txt` includes all dependencies and `src/` directory is deployed

### Timeout errors
Long-running operations (PDF processing, LLM analysis) may timeout. Use async operations or background tasks.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python scripts/run_api.py

# Test API
curl http://localhost:8000/
```

## Production Considerations

1. **Caching**: Use Vercel KV or Redis for caching LLM responses
2. **Background Jobs**: Use Vercel Cron or external job queue for scraping
3. **File Storage**: Use Vercel Blob or S3 for storing PDFs and analysis results
4. **Database**: Consider PostgreSQL or MongoDB for persistent data

## Support

For issues, see the main README or open an issue on GitHub.

