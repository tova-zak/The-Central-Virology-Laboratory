# Gemini API Setup Guide

**Last Updated:** December 2024  
**Version:** 1.0  
**Project:** Virology Lab Commitment Extraction System

---

## Overview

This document provides complete instructions for setting up and using Google's Gemini API for the **Virology Lab Commitment Extraction System**. The project uses the **FREE TIER** of Gemini API at **0 ₪ cost** with no billing required.

---

## ✅ Verified Free Tier Model

### Model Selection

**Primary Model:** `gemini-3.5-flash-lite`

**Alternative Models:**
- `gemini-flash-lite-latest` (alias, may point to newer version)
- `gemini-3.8-flash` (may experience high demand/503 errors)
- `gemini-pro-latest`

### Capabilities Confirmed ✅

| Feature | Status |
|---------|--------|
| **Vision (Image Input)** | ✅ Supported |
| **Structured Output (JSON)** | ✅ Supported |
| **Free Tier (0 ₪)** | ✅ Confirmed |
| **No Billing Required** | ✅ Confirmed |

**Content used for research was paraphrased for compliance with licensing restrictions**

---

## Rate Limits & Quotas

### Free Tier Limits (as of December 2024)

Based on official Google documentation and community reports:

| Metric | Limit |
|--------|-------|
| **Requests per Day (RPD)** | ~20 requests/day (gemini-3.8-flash) |
| **Requests per Day (RPD)** | ~500 requests/day (flash-lite models) |
| **Input Tokens** | Free of charge |
| **Output Tokens** | Free of charge |
| **Context Window** | 1M tokens |

**Note:** Rate limits are not published in official documentation and may vary by project. Check your actual limits in [Google AI Studio](https://aistudio.google.com/).

**Sources:**
- [Official Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing) (accessed Dec 2024)
- [Google AI Studio](https://aistudio.google.com/)

**Important:** Free tier data may be used by Google to improve their products. This is acceptable for our hackathon/MVP project.

---

## Cost Confirmation: 0 ₪ ✅

**Billing Status:** NO BILLING REQUIRED

The Gemini API free tier does NOT require:
- Credit card
- Billing account
- Any payment setup

You can create an API key and start making requests immediately at zero cost.

**Future Note:** If the project scales beyond free tier limits, paid tier pricing applies:
- `gemini-3.8-flash`: $0.75 per 1M input tokens, $3.75 per 1M output tokens (through Dec 31, 2026)

---

## How to Get Your Free API Key

### Step-by-Step Instructions

1. **Go to Google AI Studio**
   - Visit: https://aistudio.google.com/apikey
   - Sign in with your Google account

2. **Create API Key**
   - Click "Create API Key" button
   - Choose "Create API key in new project" (recommended for new users)
   - OR select an existing Google Cloud project

3. **Copy Your API Key**
   - Your API key will be displayed (looks like: `AIzaSy...`)
   - Copy it immediately - you may not see it again
   - Store it securely

4. **Important Security Notes:**
   - Never commit API keys to Git
   - Never share API keys publicly
   - Restrict API key usage to specific services if possible (in Google AI Studio settings)

---

## Configuration

### 1. Update `.env` File

Create or update the `.env` file in the project root:

```bash
# Gemini API Configuration
GEMINI_API_KEY=AIzaSy...your_actual_key_here...

# Recommended model for free tier
GEMINI_MODEL=gemini-3.8-flash
```

**Security:** The `.env` file is already listed in `.gitignore` and will NOT be committed to Git.

### 2. Verify `.env.example`

The `.env.example` file should contain (for reference only):

```bash
# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
```

---

## Python SDK Usage

### Installation

The required package is already in `backend/requirements.txt`:

```bash
pip install google-genai
```

### Basic Example: Text Generation

```python
from google import genai
import os

# Initialize client (reads GEMINI_API_KEY from environment)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Simple text request
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input="Explain how AI works in a few words"
)

print(interaction.output)
```

### Example: Vision (Image Analysis)

```python
from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Analyze an image
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input=[
        {"type": "text", "text": "What do you see in this image?"},
        {
            "type": "image",
            "uri": "path/to/image.jpg",  # or use base64 data
        }
    ]
)

print(interaction.output)
```

### Example: Structured JSON Output

```python
from google import genai
from pydantic import BaseModel
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Define schema
class Commitment(BaseModel):
    test_name: str
    commitment_id: str
    central_number: str

# Request structured output
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input="Extract commitment: Test XY1234, Commitment 5678, Central 9999",
    response_format={"type": "json_object", "schema": Commitment}
)

result = interaction.output  # Returns structured data
```

### Example: Vision + JSON (Our Use Case)

```python
from google import genai
from pydantic import BaseModel
from typing import Optional
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Define our extraction schema
class VirusTestCommitment(BaseModel):
    test_name: Optional[str]
    commitment_id: Optional[str]
    central_number: Optional[str]
    confidence: str  # "high", "medium", "low"

# Analyze scanned form
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input=[
        {
            "type": "text",
            "text": "Extract test name, commitment ID, and central number from this form."
        },
        {
            "type": "image",
            "uri": "data:image/jpeg;base64,/9j/4AAQ..."  # base64 image
        }
    ],
    response_format={"type": "json_object", "schema": VirusTestCommitment}
)

data = interaction.output
print(f"Test: {data.test_name}, Commitment: {data.commitment_id}")
```

---

## Verification Script

A verification script is provided at `tests/verify_gemini.py`. Run it to check your setup:

```bash
cd backend
python -m pytest tests/verify_gemini.py -v
```

This script will:
- ✅ Check if `google-genai` package is installed
- ✅ Verify API key is in `.env` file
- ✅ Test basic import functionality
- ⚠️ Not make actual API calls (save quota for development)

---

## Troubleshooting

### Error: "API key not valid"

**Solution:**
1. Check your API key in Google AI Studio: https://aistudio.google.com/apikey
2. Ensure it's correctly copied to `.env` file (no extra spaces)
3. Restart your application to reload environment variables

### Error: "Rate limit exceeded"

**Solution:**
1. You've hit the daily free tier limit (~20 requests/day for gemini-3.8-flash)
2. Wait 24 hours for quota reset
3. Consider using `gemini-3.5-flash-lite` (higher free quota: ~500 RPD)
4. Implement request caching to reduce API calls

### Error: "google.genai not found"

**Solution:**
```bash
pip install google-genai
```

### Low Quota for Development

**Solutions:**
1. Use mock responses during development (see `tests/`)
2. Cache API responses for repeated tests
3. Use `gemini-3.5-flash-lite` for higher free quota
4. Consider creating multiple test projects (each gets own quota)

### Image Not Recognized

**Common Issues:**
- Image format: Use JPEG, PNG, or WebP
- Image size: Keep under 10MB
- Image quality: Ensure text is legible (min 300 DPI for scanned forms)
- Encoding: Use base64 for inline images or File API for larger files

---

## Best Practices

### 1. Request Optimization
- **Cache responses** for identical requests
- **Batch similar requests** when possible
- **Use smaller models** (flash-lite) for simple tasks
- **Implement retry logic** with exponential backoff

### 2. Security
- Never commit `.env` file
- Use environment variables for API keys
- Rotate API keys periodically
- Restrict API key to specific IP ranges (if possible)

### 3. Rate Limit Management
```python
import time
from functools import wraps

def rate_limit(calls_per_day=20):
    """Simple rate limiter for free tier"""
    min_interval = 86400 / calls_per_day  # seconds
    last_call = [0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_call[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            last_call[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(calls_per_day=20)
def call_gemini(prompt):
    # Your Gemini API call here
    pass
```

### 4. Error Handling
```python
from google import genai
import os

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def safe_gemini_call(model, input_data, max_retries=3):
    """Call Gemini with error handling and retries"""
    for attempt in range(max_retries):
        try:
            interaction = client.interactions.create(
                model=model,
                input=input_data
            )
            return interaction.output
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                print(f"Rate limit hit. Wait and retry.")
                time.sleep(60)  # Wait 1 minute
            elif attempt == max_retries - 1:
                raise
            else:
                print(f"Retry {attempt + 1}/{max_retries}")
                time.sleep(2 ** attempt)  # Exponential backoff
    return None
```

---

## Additional Resources

- **Official Gemini API Docs:** https://ai.google.dev/gemini-api/docs
- **Python SDK (google-genai):** https://github.com/googleapis/python-genai
- **Google AI Studio:** https://aistudio.google.com/
- **API Pricing Page:** https://ai.google.dev/gemini-api/docs/pricing
- **Image Understanding Guide:** https://ai.google.dev/gemini-api/docs/image-understanding
- **Structured Output Guide:** https://firebase.google.com/docs/ai-logic/generate-structured-output

---

## Summary Checklist

Before starting development, ensure:

- [ ] API key obtained from Google AI Studio
- [ ] API key added to `.env` file
- [ ] `.env` file is in `.gitignore` (already done)
- [ ] `google-genai` in `requirements.txt` (already done)
- [ ] Verified free tier model: `gemini-3.8-flash`
- [ ] Confirmed 0 ₪ cost (no billing required)
- [ ] Understood rate limits (~20 RPD)
- [ ] Read best practices for rate limiting
- [ ] Ready to run verification script

---

**Status:** ✅ Ready for TASK-003 (Document Processing Setup)

**Next Steps:** Proceed with implementing the document processing pipeline using this verified Gemini API configuration.
