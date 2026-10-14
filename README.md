# Virology Lab Commitment Extraction System

**Status:** MVP Development (7-day hackathon)  
**Budget:** 0 ₪ (Gemini Free Tier only)

## Project Description

Automated extraction system for commitment forms from the Central Virology Laboratory. Processes PDF/image documents containing Hebrew and English text, handwriting, stamps, and stickers to extract structured data for regulatory reporting.

## Tech Stack

### Backend
- **Python 3.10+**
- **FastAPI** — API framework
- **Pydantic** — Data validation
- **Google Gemini Vision API** — AI extraction (Free Tier)
- **PyMuPDF** — PDF processing
- **openpyxl** — Excel export

### Frontend
- **React 18**
- **TypeScript**
- **Vite** — Build tool
- **TanStack Query** — Data fetching

### Architecture
- Monorepo structure: Python backend + React frontend
- Local development, single-user MVP
- No authentication (local prototype only)

## Project Structure

```
.
├── backend/           # Python FastAPI application
├── frontend/          # React TypeScript application
├── tests/             # Shared test utilities
├── docs/              # Documentation
├── PLAN.md            # Project plan v2.1 (approved)
├── DECISIONS.md       # Architecture decisions v2.0 (approved)
└── .kiro/specs/       # Kiro task specifications
```

## Setup Instructions

### System Requirements

**Backend:**
- Python 3.10 or higher
- pip (Python package manager)
- Windows: truststore package (for SSL certificate validation)

**Frontend:**
- Node.js 18 or higher
- npm (Node package manager)

**API Access:**
- Gemini API key (Free Tier) — obtain from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd The-Central-Virology-Laboratory
   ```

2. **Backend Setup**
   ```bash
   cd backend
   pip install -r requirements.txt
   # Configure .env file (see .env.example)
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

4. **Run Development Servers**
   ```bash
   # Terminal 1 - Backend
   cd backend
   uvicorn app.main:app --reload
   
   # Terminal 2 - Frontend
   cd frontend
   npm run dev
   ```

## Usage

> 📝 **Note:** Usage documentation will be added as features are implemented.

1. Upload PDF or image files
2. Process batch with AI extraction
3. Review and correct extracted fields
4. Export to Excel

## Important Notes

- **MVP Prototype:** This is a hackathon prototype, NOT production-ready
- **Budget:** 0 ₪ — uses only free-tier services
- **Gemini Free Tier:** Subject to rate limits and quotas
- **Local Only:** Single-user, localhost deployment
- **No Authentication:** Suitable only for development/testing
- **Data Privacy:** Do NOT use with real patient data without proper approvals

## Documentation

- [PLAN.md](./PLAN.md) — Project plan and timeline
- [DECISIONS.md](./DECISIONS.md) — Architecture and technical decisions
- [Tasks](./.kiro/specs/tasks.md) — Development tasks and status

## License

> 📝 License information to be added

## Contact

> 📝 Contact information to be added
