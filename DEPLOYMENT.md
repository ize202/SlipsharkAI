# Deployment Checklist

## 1. Environment Variables
Make sure these are set in Railway's environment variables:
- [ ] `API_KEY` (Generate using `python generate_key.py`)
- [ ] `OPENAI_API_KEY` (Your OpenAI API key)
- [ ] `EXA_API_KEY` (Your Exa API key)

## 2. Files to Deploy
Ensure these files are in your repository:
- [ ] `main.py` (FastAPI application)
- [ ] `exa_search.py` (Core functionality)
- [ ] `requirements.txt` (Dependencies)
- [ ] `railway.json` (Railway configuration)

## 3. Railway Configuration
Verify railway.json has:
- [ ] Correct build command
- [ ] Correct start command
- [ ] Proper port configuration

## 4. Testing Before Deploy
Run these tests locally:
```bash
# 1. Generate API key
python generate_key.py

# 2. Set up .env file with all keys
# 3. Start server
uvicorn main:app --reload

# 4. Test health check
curl http://localhost:8000/

# 5. Test research endpoint
curl -X POST "http://localhost:8000/research" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{"query": "What NBA games are scheduled for tonight?"}'
```

## 5. Deployment Steps
1. Push code to GitHub
2. Connect repository to Railway
3. Add environment variables in Railway
4. Deploy
5. Test production endpoints with new API key

## 6. Post-Deployment Verification
- [ ] Health check endpoint responds
- [ ] Research endpoint works with API key
- [ ] Invalid API keys are rejected
- [ ] Error responses are proper JSON
- [ ] Logs show no errors 