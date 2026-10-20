# Quick Start Guide

**Cold Start Demo - Get the MVP Running in Minutes**

TASK-024: How to start the system from zero to working MVP.

## Prerequisites

- Python 3.13
- Node.js 18+
- Git

## Setup (First Time)

### 1. Backend Setup

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create .env file
Copy-Item .env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_key_here
```

### 2. Frontend Setup

```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

### 3. Get Gemini API Key (Free)

1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Paste it in `backend/.env` as `GEMINI_API_KEY=your_key_here`

**Cost: ₪0 (Free Tier)**

## Running the System

### Terminal 1: Start Backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend will be available at: http://127.0.0.1:8000

### Terminal 2: Start Frontend

```powershell
cd frontend
npm run dev
```

Frontend will be available at: http://localhost:5173

## Using the System

### Step 1: Upload Documents

1. Open http://localhost:5173
2. Click "Choose Files" or drag & drop
3. Select PDF or image files of virology lab commitment forms
4. Click "Upload" (max 10 files, 20MB per file)

### Step 2: Process Batch

```powershell
# Get the batch_id from upload response, then:
curl -X POST http://127.0.0.1:8000/api/batches/{batch_id}/process
```

Or use the frontend UI to trigger processing (if integrated).

### Step 3: Review Extracted Data

- View extraction results in the Review screen
- Fields are color-coded:
  - **Green**: Valid
  - **Orange**: Needs review (uncertain/missing)
  - **Red**: Invalid (failed validation)
- Click "Edit" to manually correct fields

### Step 4: Export to Excel

- Export is automatically blocked if any fields need review
- Fix all orange/red fields first
- Click "Export to Excel" when all fields are green
- Download the Excel file

## API Endpoints

### Upload
```
POST /api/batches
Content-Type: multipart/form-data
```

### Process
```
POST /api/batches/{batch_id}/process
```

### Get Status
```
GET /api/batches/{batch_id}
```

### Export
```
POST /api/batches/{batch_id}/export
Returns: Excel file download
```

### Health Check
```
GET /health
GET /docs  # Swagger UI
```

## Testing

### Run All Tests

```powershell
cd backend
pytest tests/ -v
```

**Expected: 84 tests passing**

### Run Specific Test Suites

```powershell
# Upload tests
pytest tests/test_upload_limits.py -v

# Validation tests
pytest tests/test_validation.py -v

# Export tests
pytest tests/test_export.py -v

# Sender normalization (34 institutions)
pytest tests/test_sender_normalization.py -v
```

## Troubleshooting

### "SSL Certificate Verify Failed" Error

**Solution**: The code already handles this with `truststore.inject_into_ssl()` in `main.py`.

If you still see SSL errors:
```powershell
pip install truststore
```

### "Gemini API Key Not Found"

1. Check `backend/.env` exists
2. Verify `GEMINI_API_KEY=...` is set
3. No quotes needed around the key
4. Restart the backend server

### "ModuleNotFoundError"

```powershell
# Make sure virtual environment is activated
.\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend Won't Start

```powershell
# Delete node_modules and reinstall
Remove-Item -Recurse -Force node_modules
npm install
npm run dev
```

## System Architecture

```
┌─────────────────┐
│  Frontend       │  React + TypeScript + Vite
│  localhost:5173 │
└────────┬────────┘
         │
         │ HTTP API
         │
┌────────▼────────┐
│  Backend        │  FastAPI + Python 3.13
│  127.0.0.1:8000│
└────────┬────────┘
         │
    ┌────┴─────┬────────────┬──────────┐
    │          │            │          │
┌───▼───┐ ┌───▼────┐ ┌─────▼─────┐ ┌─▼──────┐
│Gemini │ │Validator│ │Normalizer │ │Exporter│
│API    │ │ID/Date  │ │34 Inst.   │ │Excel   │
└───────┘ └─────────┘ └───────────┘ └────────┘
```

## Budget Compliance

✅ **Total Cost: ₪0**
- Gemini 3.5 Flash Lite: Free Tier
- No paid services used
- No cloud deployment costs (local development)

## Next Steps

1. Test with real forms from `reference/` directory
2. Add more institutions to closed sender list if needed
3. Enhance frontend integration (connect Review screen to API)
4. Deploy to Render free tier (when ready)

## Support

**For issues:**
1. Check logs in backend terminal
2. Check browser console for frontend errors
3. Verify API endpoints work with `curl` or `/docs`
4. Run tests to verify system health
