# Deployment Guide - Cloud Deployment

**Integration Package 5: Production deployment on Render (Free Tier)**

Budget: ₪0 - Uses only free services

---

## Prerequisites

1. GitHub account
2. Render account (free): https://render.com
3. Gemini API key (free): https://aistudio.google.com/app/apikey

---

## Option A: Deploy with render.yaml (Recommended)

### Step 1: Push Code to GitHub

```powershell
# Make sure your code is committed
git status

# Push to GitHub
git push origin main
```

### Step ct Render to GitHub

1. Go to https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Select `The-Central-Virology-Laboratory` repository
5. Click "Apply"

### Step 3: Configure Environment Variables

Render will create both services automatically. You need to set:

**Backend Service**:
- Go to virology-lab-backend service
- Navigate to "Environment"
- Add:
  - `GEMINI_API_KEY`: Your Gemini API key (from https://aistudio.google.com)
  
**Frontend Service**:
- Already configured in render.yaml
- `VITE_API_URL` will point to your backend URL

### Step 4: Deploy

- Render will automatically deploy both services
- Backend: `https://virology-lab-backend.onrender.com`
- Frontend: `https://virology-lab-frontend.onrender.com`

### Step 5: Update CORS

After first deployment, update backend CORS:
1. Get your actual frontend URL
2. Go to backend Environment
3. Update `CORS_ORIGINS` to include your frontend URL

---

## Option B: Manual Deploy

### Backend Deployment

1. **Create Web Service**:
   - Go to https://dashboard.render.com
   - Click "New" → "Web Service"
   - Connect GitHub repository
   - Name: `virology-lab-backend`
   - Region: Frankfurt (or closest to you)
   - Branch: `main`
   - Root Directory: `backend`
   - Runtime: Python 3.13
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Plan: Free

2. **Environment Variables**:
   ```
   GEMINI_API_KEY=your_key_here
   GEMINI_MODEL=gemini-3.5-flash-lite
   APP_NAME=Virology Lab API
   APP_VERSION=1.0.0-mvp
   TEMP_STORAGE_PATH=/opt/render/project/src/temp_storage
   CORS_ORIGINS=http://localhost:5173
   ```

3. **Deploy**: Click "Create Web Service"

### Frontend Deployment

1. **Create Static Site**:
   - Go to https://dashboard.render.com
   - Click "New" → "Static Site"
   - Connect same repository
   - Name: `virology-lab-frontend`
   - Branch: `main`
   - Root Directory: Leave empty
   - Build Command: `cd frontend && npm install && npm run build`
   - Publish Directory: `frontend/dist`

2. **Environment Variables**:
   ```
   VITE_API_URL=https://virology-lab-backend.onrender.com
   ```
   (Replace with your actual backend URL after backend is deployed)

3. **Deploy**: Click "Create Static Site"

4. **Update Backend CORS**:
   - Go back to backend service
   - Update `CORS_ORIGINS` to include your frontend URL

---

## Post-Deployment

### Test the Deployment

1. Open your frontend URL: `https://virology-lab-frontend.onrender.com`
2. Check that system status shows "✅ System Online"
3. Try uploading a test document
4. Verify processing works
5. Check review screen loads
6. Test Excel export

### Monitor Usage

**Free Tier Limits**:
- Backend: Spins down after 15 minutes of inactivity
- Cold start: ~30-60 seconds on first request
- 750 hours/month free compute time
- Gemini: 15 requests per minute (free tier)

### Logs

View logs in Render dashboard:
- Backend: Click service → "Logs" tab
- Frontend: Build logs available, runtime logs N/A (static site)

---

## Important Security Notes

### ⚠ API Key Protection

**NEVER commit `.env` files to Git!**

The `.gitignore` file already excludes:
- `backend/.env`
- `frontend/.env.local`
- `*.env`

Always set API keys through:
1. Render Dashboard → Environment variables
2. Or local `.env` files (not committed)

### ⚠ Rate Limiting

The free deployment has NO rate limiting or authentication.

**To prevent abuse**:

1. **Add Basic Auth** (if needed):
   ```python
   # In backend/app/main.py
   from fastapi import Depends, HTTPException, status
   from fastapi.security import HTTPBasic, HTTPBasicCredentials
   
   security = HTTPBasic()
   
   def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
       # Simple demo protection
       correct_password = settings.demo_password  # Set in env
       if credentials.password != correct_password:
           raise HTTPException(status_code=401, detail="Invalid credentials")
   
   # Apply to sensitive endpoints:
   @app.post("/api/batches/{batch_id}/process", dependencies=[Depends(verify_credentials)])
   ```

2. **Monitor Render Logs**:
   - Watch for unusual activity
   - Set up email alerts in Render

3. **Gemini Quotas**:
   - Monitor usage at https://aistudio.google.com
   - Free tier: 15 RPM, 1500 RPD
   - Will fail gracefully if quota exceeded

### ⚠ Demo Data Only

**Never upload real patient data to this MVP!**

This is a hackathon demo with:
- No encryption at rest
- No HIPAA compliance
- No audit logging
- No user authentication

Use only synthetic/test data.

---

## Troubleshooting

### Backend Won't Start

**Check logs for**:
1. Missing `GEMINI_API_KEY` environment variable
2. Import errors (missing dependencies in requirements.txt)
3. Port binding issues (should use `$PORT` from Render)

**Solution**:
- Verify all environment variables are set
- Check `requirements.txt` is complete
- Ensure `uvicorn` command uses `--port $PORT`

### Frontend Build Fails

**Common causes**:
1. Node version mismatch
2. Missing dependencies
3. TypeScript errors

**Solution**:
- Check build command includes `npm install`
- Verify `frontend/package.json` is committed
- Fix any TypeScript errors locally first

### CORS Errors

**Symptoms**: Frontend can't call backend API

**Solution**:
1. Check backend logs for CORS errors
2. Verify `CORS_ORIGINS` includes your frontend URL
3. Make sure frontend URL is correct (https, not http)
4. Redeploy backend after CORS changes

### Cold Start Slow

**Expected behavior**: Free tier spins down after 15 min inactivity

**Solution**:
- First request after idle: 30-60 seconds
- Keep alive script (optional):
  ```javascript
  // Ping every 10 minutes to keep warm
  setInterval(() => {
    fetch('https://your-backend.onrender.com/health');
  }, 600000);
  ```

### Storage Issues

**Symptoms**: Data lost after redeploy

**Expected**: Files in `temp_storage` are ephemeral on Render free tier

**Solution**:
- For persistent storage, upgrade to paid Render plan with disk
- Or use external storage (S3, Cloud Storage) - requires code changes

---

## Cost Breakdown

| Service | Usage | Cost |
|---------|-------|------|
| Render Backend (Free) | 750 hours/month | ₪0 |
| Render Frontend (Free) | Unlimited bandwidth | ₪0 |
| Gemini API (Free Tier) | 15 RPM, 1500 RPD | ₪0 |
| **Total** | | **₪0** |

---

## Next Steps

After successful deployment:

1. **Share demo link** with stakeholders
2. **Document limitations** (no auth, demo data only, cold starts)
3. **Collect feedback** on extraction accuracy
4. **Plan production features**:
   - User authentication
   - Database (PostgreSQL)
   - File storage (S3/CloudStorage)
   - Rate limiting
   - Monitoring/alerts
   - HIPAA compliance (if handling real data)

---

## Rollback

If deployment fails:

1. **Render Dashboard** → Service → "Manual Deploy"
2. Select previous successful commit
3. Click "Deploy"

Or:
```powershell
# Revert locally
git revert HEAD
git push origin main
```

Render will auto-redeploy on push (if auto-deploy enabled).

---

## Support

For deployment issues:
- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- GitHub Issues: Create issue in repository

---

*Last Updated: Current Session*  
*Status: Ready for Cloud Deployment*
