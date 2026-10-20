# Virology Lab Commitment Extraction System

**Hackathon MVP - Ministry of Health**  
**Budget: ₪0 | Timeline: 7 Days | Status: ✅ Complete & Deployment-Ready**

Automated extraction of commitment data from virology lab forms using Gemini AI (Free Tier).

---

## 🎯 Quick Links

- **[MVP Validation Report](docs/MVP_VALIDATION_REPORT.md)** - Test results and limitations
- **[Cloud Deployment Guide](docs/CLOUD_DEPLOYMENT_GUIDE.md)** - Deploy to Render.com (free tier)
- **[Quick Start Guide](QUICKSTART.md)** - Get running locally in minutes
- **[Deployment Guide](DEPLOYMENT.md)** - Original deployment guide
- **[Integration Report](INTEGRATION_COMPLETE.md)** - Complete technical details
- **[Project Status](STATUS.md)** - Metrics, test coverage, roadmap

---

## ✨ Features

### Core Workflow
1. **Upload** - PDF or images (max 10 files, 20MB each)
2. **Process** - AI extraction with Gemini 3.5 Flash Lite (free)
3. **Review** - Color-coded fields (🟠 uncertain, 🔴 invalid)
4. **Edit** - Manual correction with instant save
5. **Export** - Excel download (blocked until all fields verified)

### Technical Highlights
- ✅ **Zero-guess extraction**: Never invents data, marks uncertain when unclear
- ✅ **Closed sender list**: 34 Israeli medical institutions (4 health funds + 30 hospitals)
- ✅ **ID validation**: Israeli ID checksum (Luhn-like algorithm)
- ✅ **Date validation**: Format check, no future dates
- ✅ **Persistent storage**: Survives server restart, page refresh
- ✅ **Export blocking**: Backend-enforced, cannot bypass
- ✅ **84 tests passing**: Automated unit + integration tests

---

## 🏗 Architecture

```
┌─────────────────────┐
│  React Frontend     │  TypeScript + Vite
│  (Workflow UI)      │  Upload → Process → Review → Export
└──────────┬──────────┘
           │ REST API
           │
┌──────────▼──────────┐
│  FastAPI Backend    │  Python 3.13
│  (Processing)       │  Gemini + Validation + Storage
└──────────┬──────────┘
           │
    ┌──────┴─────┬────────────┬───────────┐
    │            │            │           │
┌───▼────┐  ┌───▼────┐  ┌────▼────┐  ┌──▼──────┐
│ Gemini │  │Validator│  │Normalizer│  │ Storage │
│  API   │  │ID/Date │  │34 Inst. │  │  JSON   │
└────────┘  └────────┘  └─────────┘  └─────────┘
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.13
- Node.js 18+
- Gemini API key (free): https://aistudio.google.com/app/apikey

### Local Setup (5 minutes)

**Backend**:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create .env from template
Copy-Item .env.example .env
# Edit .env and add: GEMINI_API_KEY=your_key_here

# Run
uvicorn app.main:app --reload
```

**Frontend**:
```powershell
cd frontend
npm install
npm run dev
```

**Access**: Open http://localhost:5173

See [QUICKSTART.md](QUICKSTART.md) for detailed instructions.

---

## 📊 Current Status

- **Tests**: 84 passing ✅
- **Frontend Build**: Success ✅
- **Backend**: All endpoints working ✅
- **Persistence**: JSON file storage ✅
- **Deployment**: Ready for cloud ✅

### What Works
✅ Full workflow: Upload → AI extraction → Human review → Excel export  
✅ Field editing with backend persistence  
✅ Color-coded review (orange for uncertain, red for invalid)  
✅ Export blocking until all fields verified  
✅ ID validation (Israeli checksum)  
✅ Date validation (format + future check)  
✅ Sender normalization (34 institutions)  
✅ Survives server restart & page refresh  

### Known Limitations (MVP)
⚠ No authentication (demo with test data only)  
⚠ No rate limiting (monitor Gemini usage manually)  
⚠ Cold start on free tier (~30-60s after idle)  
⚠ Ephemeral disk on Render (data lost on redeploy)  

---

## 🌍 Cloud Deployment

**Budget: ₪0 (Free Tier)**

```powershell
# 1. Push to GitHub
git push origin main

# 2. Deploy to Render
# Follow DEPLOYMENT.md for detailed instructions
```

Services:
- Backend: `https://virology-lab-backend.onrender.com`
- Frontend: `https://virology-lab-frontend.onrender.com`

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment guide.

---

## 📝 Documentation

| File | Description |
|------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Local setup & running |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Cloud deployment (Render) |
| [INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md) | Technical integration report |
| [STATUS.md](STATUS.md) | Project metrics & roadmap |
| [PLAN.md](PLAN.md) | Development plan & decisions |
| `.kiro/specs/tasks.md` | Task breakdown |

---

## 🧪 Testing

```powershell
# Run all tests
cd backend
pytest tests/ -v

# Expected: 84 passed

# Build frontend
cd frontend
npm run build

# Expected: Success, no errors
```

---

## 🔒 Security Notes

⚠ **Demo MVP - Use Test Data Only**

This system is:
- ✅ Suitable for hackathon demo
- ✅ Good for proof-of-concept
- ❌ **NOT** HIPAA compliant
- ❌ **NOT** for real patient data
- ❌ **NO** encryption at rest
- ❌ **NO** audit logging

For production with real data, see "Production Upgrade Path" in STATUS.md.

---

## 💰 Cost Breakdown

| Service | Usage | Cost |
|---------|-------|------|
| Development | Local | ₪0 |
| Gemini API | Free tier (15 RPM) | ₪0 |
| Render Backend | Free (750h/mo) | ₪0 |
| Render Frontend | Free (unlimited) | ₪0 |
| **Total** | | **₪0** |

---

## 📈 Next Steps

### For Demo
1. Deploy to Render (DEPLOYMENT.md)
2. Share frontend URL
3. Demo with test forms
4. Gather feedback

### For Production
1. Add PostgreSQL database
2. Implement authentication
3. Add rate limiting & monitoring
4. HIPAA compliance measures
5. Audit logging
6. Backup strategy

---

## 🤝 Contributing

This is a hackathon MVP. For production deployment:
1. Review DECISIONS.md for design choices
2. Check STATUS.md for known issues
3. See tasks.md for pending work
4. Follow secure coding practices

---

## 📄 License

Hackathon project - Ministry of Health, Israel

---

## 🙏 Acknowledgments

- **Gemini API**: Free tier for AI extraction
- **Render**: Free hosting platform
- **FastAPI + React**: Modern, fast web frameworks
- **Python 3.13 + TypeScript**: Type-safe development

---

**Made with ❤ for improving healthcare data processing**  
**Hackathon 2026 | Budget: ₪0 | Status: ✅ Complete**
