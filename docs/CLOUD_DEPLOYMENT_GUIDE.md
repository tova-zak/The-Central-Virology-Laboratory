# Cloud Deployment Guide
**Project:** Central Virology Laboratory - Commitment Extraction System  
**Platform:** Render.com (Free Tier)  
**Date:** 2026-10-14  
**Status:** READY FOR DEPLOYMENT (Pending Approval)

---

## ⚠️ CRITICAL: DO NOT DEPLOY WITHOUT EXPLICIT APPROVAL

This guide prepares all deployment files and procedures, but **NO actual deployment should occur** without separate explicit approval from the project stakeholder.

**Reasons for Approval Requirement:**
1. **No live Gemini testing performed** - accuracy unknown
2. **Quota exhaustion risk** - free tier limited to 15 RPM
3. **Data persistence limitations** - Render free tier has ephemeral storage
4. **NO real patient data** - demo with synthetic data only
5. **Security considerations** - MVP is NOT HIPAA compliant

**When approved to deploy:** Follow the steps in this guide. Deployment should take 15-30 minutes.

---

## Prerequisites

Before deploying, ensure you have:

### Required
- ✅ GitHub repository with latest code pushed to `main` branch
- ✅ Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- ✅ Render.com account (free tier)
- ✅ Synthetic test data prepared (NO real PII)
- ✅ **Deployment approval obtained from stakeholder**

### Recommended
- ✅ Git repository is public OR Render has access to private repo
- ✅ `.env` file NOT committed (verify with `git status`)
- ✅ All secrets stored securely (password manager, not plain text)

---

## Render.com Free Tier Limitations

**Understand these constraints before deploying:**

### Backend Service (Web Service)
| Resource | Free Tier Limit | Impact |
|----------|----------------|--------|
| RAM | 512 MB | ⚠️ May limit PDF size (10 pages safer than 30) |
| CPU | 0.1 CPU | Slow processing, expect 30-60s per form |
| Bandwidth | 100 GB/month | Sufficient for demo (thousands of PDFs) |
| Spin Down | After 15 min idle | First request after idle: 30-60s cold start |
| Build Time | 15 min max | Should complete in 5-10 min |
| Storage | 1 GB ephemeral | ⚠️ Data lost on redeploy or restart |

### Frontend (Static Site)
| Resource | Free Tier Limit | Impact |
|----------|----------------|--------|
| Bandwidth | 100 GB/month | CDN-backed, very fast |
| Build Time | 10 min max | Should complete in 2-3 min |
| HTTPS | ✅ Free | Automatic Let's Encrypt SSL |
| Custom Domain | ✅ Supported | Optional |

### Critical Limitations

1. **Ephemeral Disk** 🔴
   - Data stored in JSON files is LOST on redeploy or service restart
   - Use Render disk for temporary processing only
   - For production, migrate to database (PostgreSQL)

2. **Cold Starts** 🟡
   - Service spins down after 15 minutes of inactivity
   - Next request takes 30-60 seconds to wake up
   - Keep-alive ping can prevent this (see below)

3. **Memory Constraints** 🟡
   - 512 MB RAM may be insufficient for 30-page PDFs with OCR
   - Test with 10-page PDFs first
   - Monitor memory usage via Render dashboard

4. **No Database** 🔴
   - Free tier does NOT include PostgreSQL
   - MVP uses JSON file storage
   - Data lost on restart

---

## Deployment Steps

### Step 1: Prepare GitHub Repository

**1.1 Verify .env is NOT committed:**
```powershell
git status
git log --all --oneline --decorate --graph -- .env
```

If `.env` appears, **REMOVE IT IMMEDIATELY:**
```powershell
git rm --cached .env
git commit -m "Remove .env from git (security)"
git push origin main
```

**1.2 Verify .gitignore includes .env:**
```powershell
# .gitignore should contain:
.env
.env.local
.env.production
*.env
```

**1.3 Push latest code:**
```powershell
git add .
git commit -m "chore: prepare for cloud deployment"
git push origin main
```

---

### Step 2: Deploy Backend to Render

**2.1 Create New Web Service**

1. Log in to [Render.com](https://render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure service:
   - **Name:** `virology-lab-backend` (or your choice)
   - **Region:** Choose closest to your users (e.g., Frankfurt for Europe, Oregon for Israel-adjacent)
   - **Branch:** `main`
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`

**2.2 Set Environment Variables**

Click **"Environment"** tab and add these variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `GEMINI_API_KEY` | `your_key_here` | ⚠️ Secret - get from Google AI Studio |
| `DEMO_MODE` | `true` | ⚠️ REQUIRED for demo to avoid quota exhaustion |
| `HYBRID_ENGINE_ENABLED` | `true` | Enable OCR + Gemini hybrid engine |
| `TEMP_STORAGE_PATH` | `./temp` | Local disk (ephemeral) |
| `MAX_FILES_PER_BATCH` | `10` | Limit to avoid memory issues |
| `MAX_FILE_SIZE_MB` | `20` | Per-file limit |
| `CORS_ORIGINS` | `https://your-frontend.onrender.com,http://localhost:5173` | Frontend URLs |
| `TESSERACT_CMD` | `/usr/bin/tesseract` | Default Linux path |
| `TESSDATA_PREFIX` | `/usr/share/tesseract-ocr/4.00/tessdata/` | Tesseract data directory |

**⚠️ CRITICAL: Keep DEMO_MODE=true for public demo to prevent Gemini quota exhaustion**

**2.3 Add Tesseract to Build**

Create `backend/Dockerfile` (if not exists):
```dockerfile
FROM python:3.13-slim

# Install Tesseract OCR with Hebrew language pack
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-heb \
    tesseract-ocr-eng \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**OR** if using Render auto-build (no Dockerfile), add this to a build script:

Create `backend/render_build.sh`:
```bash
#!/usr/bin/env bash
# Install Tesseract OCR
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-heb tesseract-ocr-eng

# Install Python dependencies
pip install -r requirements.txt
```

Update Render **Build Command** to:
```bash
bash render_build.sh
```

**2.4 Deploy**

Click **"Create Web Service"**

Render will:
1. Clone your repo
2. Run build command (~5-10 min)
3. Start the service
4. Assign a URL: `https://virology-lab-backend.onrender.com`

**2.5 Verify Deployment**

Once deployed, test the health endpoint:
```powershell
curl https://virology-lab-backend.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "checks": {
    "tesseract": {"available": true, "hebrew": true, "english": true},
    "storage": {"writable": true},
    "gemini": {"configured": true, "demo_mode": true}
  }
}
```

If `status: "unhealthy"`, check logs in Render dashboard.

---

### Step 3: Deploy Frontend to Render

**3.1 Create Frontend Production Config**

Create `frontend/.env.production`:
```env
VITE_API_BASE_URL=https://virology-lab-backend.onrender.com
```

**⚠️ Replace with your actual backend URL from Step 2**

**3.2 Commit and Push**

```powershell
git add frontend/.env.production
git commit -m "feat: add production API URL"
git push origin main
```

**3.3 Create New Static Site**

1. In Render dashboard, click **"New +"** → **"Static Site"**
2. Connect same GitHub repository
3. Configure:
   - **Name:** `virology-lab-frontend` (or your choice)
   - **Branch:** `main`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`

**3.4 Deploy**

Click **"Create Static Site"**

Render will:
1. Clone repo
2. Run `npm install` (~2 min)
3. Run `npm run build` (~1 min)
4. Deploy to CDN
5. Assign URL: `https://virology-lab-frontend.onrender.com`

**3.5 Update Backend CORS**

Go back to backend service → **Environment** tab:

Update `CORS_ORIGINS`:
```
https://virology-lab-frontend.onrender.com,http://localhost:5173
```

Click **"Save Changes"** → Backend will redeploy (~1 min)

**3.6 Verify Integration**

1. Open `https://virology-lab-frontend.onrender.com`
2. You should see the upload screen
3. Upload a test PDF (synthetic data only!)
4. Verify processing works end-to-end

---

### Step 4: Test the Full Workflow

**4.1 Upload Test**

1. Open frontend URL
2. Click **"Upload Files"**
3. Select a 1-page synthetic test PDF
4. Verify upload completes

**4.2 Processing Test**

1. Click **"Process Batch"**
2. Wait for completion (may take 30-60s on free tier)
3. Verify extracted fields appear
4. Check for errors in Render backend logs if processing fails

**4.3 Review Test**

1. Verify extracted fields are displayed
2. Test editing a field (e.g., correct patient name)
3. Click **"Save"**
4. Refresh page → verify edit persists (within same session)

**4.4 Export Test**

1. Verify export button is blocked if there are uncertain fields
2. Approve/correct all uncertain fields
3. Click **"Export to Excel"**
4. Download Excel file
5. Verify data is correct

**4.5 Cold Start Test**

1. Wait 20 minutes (backend will spin down)
2. Try uploading again
3. First request will take 30-60s (cold start)
4. Subsequent requests should be fast

---

## Monitoring and Maintenance

### Logs

**View Backend Logs:**
1. Render Dashboard → Backend Service → **"Logs"** tab
2. Real-time log streaming
3. Search and filter by timestamp

**View Frontend Build Logs:**
1. Render Dashboard → Frontend Site → **"Deploys"** tab
2. Click latest deploy → **"View Logs"**

### Health Checks

Render automatically monitors `/health` endpoint:
- HTTP 200: Service healthy
- HTTP 503: Service unhealthy → Render may restart

**Monitor health manually:**
```powershell
curl https://virology-lab-backend.onrender.com/health
```

### Restart Service

If backend becomes unresponsive:
1. Render Dashboard → Backend Service
2. Click **"Manual Deploy"** → **"Clear build cache & deploy"**
3. Wait ~5-10 min for rebuild

### Update Environment Variables

To change env vars (e.g., disable DEMO_MODE for testing):
1. Backend Service → **"Environment"** tab
2. Edit variable
3. Click **"Save Changes"**
4. Service will automatically redeploy

⚠️ **Remember:** Redeploy = data loss (ephemeral disk)

---

## Data Persistence (CRITICAL WARNING)

### ⚠️ Ephemeral Storage Limitation

**What This Means:**
- All JSON files are stored on Render's ephemeral disk
- Disk is wiped on:
  - Service restart
  - Manual deploy
  - Automatic deploy (e.g., git push)
  - Service plan change
  - Render maintenance

**Impact:**
- **All uploaded PDFs are lost**
- **All extracted data is lost**
- **All manual corrections are lost**

### Mitigation Strategies

**For Demo (Acceptable):**
1. Use DEMO_MODE=true (no Gemini calls, deterministic mock data)
2. Process same test files repeatedly
3. Document "this is ephemeral demo storage"
4. Warn users NOT to expect data persistence

**For Production (Required):**
1. Migrate to Render PostgreSQL ($7/month starter tier)
2. Store PDFs in external blob storage (AWS S3, Cloudflare R2)
3. Implement backup/restore procedures
4. Use Render persistent disk (paid tier only)

---

## Security Considerations

### Environment Variables

✅ **DO:**
- Store secrets in Render Environment Variables (encrypted at rest)
- Use different API keys for dev/staging/prod
- Rotate Gemini API key regularly
- Enable "Secret" checkbox for sensitive vars in Render

❌ **DON'T:**
- Commit `.env` to git
- Share Gemini API key in chat, email, or Slack
- Use production API keys in local development
- Log or print secrets in application code

### HTTPS

✅ Render provides automatic HTTPS (Let's Encrypt SSL)
✅ All traffic encrypted in transit

### CORS

Current config allows:
- Frontend domain
- `localhost:5173` (for local dev)

⚠️ Do NOT set CORS_ORIGINS=`*` (allows any origin)

### Demo Data Only

⚠️ **CRITICAL:** This MVP is NOT production-ready for real patient data

**Why:**
- No authentication (anyone can access)
- No encryption at rest (JSON files in plaintext)
- No audit logging (cannot track who accessed what)
- No HIPAA compliance
- Data lost on restart (no backup)

**Use Only With:**
- Synthetic test data (fake patient info)
- Anonymized forms (all PII removed/redacted)
- Public demo data (non-sensitive)

---

## Cost Monitoring

### Free Tier Limits

**Backend:**
- 750 hours/month (sufficient for 24/7 uptime)
- 100 GB bandwidth/month
- No database included

**Frontend:**
- Unlimited bandwidth (100 GB soft limit)
- Unlimited builds

### Upgrade Triggers

You'll need to upgrade if:
- Backend exceeds 512 MB RAM (upgrade to $7/month)
- Need persistent storage (PostgreSQL: $7/month)
- Need faster processing (CPU upgrade: $25/month)
- Exceed 100 GB bandwidth (rare for MVP)

### Billing Alerts

Render does NOT support spending limits. To avoid unexpected charges:
1. Check dashboard weekly
2. Monitor bandwidth usage
3. Stick to free tier unless approved

---

## Troubleshooting

### Backend Build Fails

**Symptom:** Render build fails with dependency errors

**Fix:**
1. Verify `requirements.txt` is up to date
2. Check Render build logs for specific error
3. Test locally: `pip install -r requirements.txt`

### Frontend Build Fails

**Symptom:** Render build fails with TypeScript errors

**Fix:**
1. Verify `package.json` and `package-lock.json` committed
2. Test locally: `npm install && npm run build`
3. Check Render build logs

### CORS Errors in Browser

**Symptom:** Browser console shows "CORS policy: No 'Access-Control-Allow-Origin'"

**Fix:**
1. Verify backend `CORS_ORIGINS` includes frontend URL
2. Verify HTTPS (not HTTP) in URLs
3. Check backend logs for CORS middleware loading

### 503 Service Unavailable

**Symptom:** `/health` returns 503

**Possible Causes:**
1. Tesseract not installed → Check build script
2. Storage directory not writable → Check file permissions
3. Gemini API key missing → Verify env var set

**Fix:**
1. Check Render logs for specific error
2. Verify environment variables
3. Restart service (Manual Deploy)

### Data Lost After Restart

**Symptom:** Uploaded files and extractions disappear

**Explanation:** This is EXPECTED with ephemeral storage

**Fix:**
- For demo: Re-upload test files
- For production: Migrate to PostgreSQL

### Cold Start Slow (30-60s)

**Symptom:** First request after 15 min idle is very slow

**Explanation:** Render free tier spins down after idle

**Mitigation (Optional):**
1. Implement keep-alive ping (ping backend every 10 min from frontend)
2. Upgrade to paid tier (no spin down)

**Keep-Alive Implementation:**

Create `frontend/src/utils/keepAlive.ts`:
```typescript
export function startKeepAlive(apiBaseUrl: string) {
  setInterval(async () => {
    try {
      await fetch(`${apiBaseUrl}/health`);
    } catch (e) {
      console.warn('Keep-alive ping failed', e);
    }
  }, 10 * 60 * 1000); // Every 10 minutes
}
```

In `frontend/src/App.tsx`:
```typescript
import { startKeepAlive } from './utils/keepAlive';

useEffect(() => {
  startKeepAlive(import.meta.env.VITE_API_BASE_URL);
}, []);
```

---

## Rollback Procedure

### If Deployment Fails

**Option 1: Rollback to Previous Deploy**
1. Render Dashboard → Service → **"Deploys"** tab
2. Find last successful deploy
3. Click **"Rollback"**

**Option 2: Revert Git Commit**
```powershell
git revert HEAD
git push origin main
```
Render will auto-deploy previous version.

### If Production Breaks

1. Set `DEMO_MODE=true` (if not already)
2. Check logs for errors
3. If critical bug:
   - Rollback deploy (Option 1 above)
   - OR disable service temporarily (Render Dashboard → Suspend)
4. Fix bug locally, test, then redeploy

---

## Next Steps

### For Demo

1. ✅ Deploy backend and frontend following this guide
2. ✅ Test full workflow with synthetic data
3. ✅ Share frontend URL with stakeholders
4. ✅ Demo upload → process → review → export
5. ✅ Collect feedback

### For Production

1. 🔲 Migrate to PostgreSQL database
2. 🔲 Implement authentication (OAuth2, Azure AD)
3. 🔲 Add role-based access control
4. 🔲 Enable encryption at rest
5. 🔲 Implement audit logging
6. 🔲 Set up automated backups
7. 🔲 Conduct security audit
8. 🔲 Obtain HIPAA compliance (if US data)
9. 🔲 Test with real forms (accuracy validation)
10. 🔲 Set up monitoring/alerting (Sentry, DataDog)

---

## Deployment Checklist

Before deploying, verify:

- [ ] `.env` NOT committed to git
- [ ] Gemini API key obtained and stored securely
- [ ] `DEMO_MODE=true` set in Render environment
- [ ] Synthetic test data prepared (NO real PII)
- [ ] Deployment approval obtained from stakeholder
- [ ] GitHub repository pushed to `main`
- [ ] Backend Dockerfile or build script includes Tesseract
- [ ] Frontend `.env.production` created with backend URL
- [ ] CORS_ORIGINS includes frontend URL
- [ ] Health check endpoint tested locally
- [ ] Rollback procedure understood
- [ ] Stakeholders warned about ephemeral storage

---

**Deployment Guide Status:** READY  
**Next Action:** Obtain deployment approval from stakeholder  
**Deployment Time Estimate:** 15-30 minutes  
**Responsible:** Agent D (QA, Cloud & Submission)  
**Date:** 2026-10-14

