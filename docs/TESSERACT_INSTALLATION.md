# Tesseract OCR Installation Guide for Windows

**Required for:** Hybrid Extraction Engine OCR layer  
**Status:** Optional - MockOCR fallback available  
**Languages Needed:** Hebrew (heb) + English (eng)

---

## Quick Status Check

Before installing, check if Tesseract is already installed:

```powershell
tesseract --version
```

If this shows version info, Tesseract is already installed. Skip to **Verify Language Data** section.

---

## Installation Options

### Option 1: Official Windows Installer (Recommended)

**Source:** [UB-Mannheim/tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki)

1. **Download Installer:**
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download: `tesseract-ocr-w64-setup-5.5.1.20250113.exe` (or latest version)
   - File size: ~55 MB

2. **Run Installer as Administrator:**
   - Right-click installer → "Run as administrator"
   - Accept license

3. **⚠️ CRITICAL: Select Language Data**
   - In "Additional Language Data" screen:
   - ☑️ **Check "Hebrew"** (`heb.traineddata`)
   - ☑️ **Check "English"** (`eng.traineddata`)
   - Note: Default installation may NOT include Hebrew!

4. **Installation Path:**
   - Default: `C:\Program Files\Tesseract-OCR`
   - Custom path is fine, just remember it for step 5

5. **Add to PATH (Recommended):**
   
   Open PowerShell as Administrator:
   ```powershell
   # Add to User PATH (doesn't require admin after first time)
   [Environment]::SetEnvironmentVariable(
       "Path",
       $env:Path + ";C:\Program Files\Tesseract-OCR",
       "User"
   )
   ```
   
   **Or** add manually:
   - Windows Search → "Environment Variables"
   - Edit "Path" under User variables
   - Add new entry: `C:\Program Files\Tesseract-OCR`

6. **Restart Terminal:**
   - Close and reopen PowerShell/Command Prompt
   - Close and reopen VS Code (if using integrated terminal)

7. **Verify Installation:**
   ```powershell
   tesseract --version
   ```
   
   Expected output:
   ```
   tesseract 5.5.1
   leptonica-1.85.0
   ...
   ```

8. **Verify Language Data:**
   ```powershell
   tesseract --list-langs
   ```
   
   Expected output should include:
   ```
   List of available languages (2):
   eng
   heb
   ```
   
   **If Hebrew is missing:** Reinstall and ensure Hebrew is selected in language data step.

---

### Option 2: Chocolatey Package Manager

**Prerequisites:** Chocolatey must be installed  
**Installation:** [chocolatey.org/install](https://chocolatey.org/install)

```powershell
# Install Tesseract
choco install tesseract

# Install language packs
choco install tesseract-languages
```

**Verify:**
```powershell
tesseract --list-langs
```

---

### Option 3: Winget (Windows 11)

```powershell
winget install UB-Mannheim.TesseractOCR
```

**Note:** May not include Hebrew language data by default. Check with `tesseract --list-langs`.

---

## Manual Language Data Installation

If Hebrew is missing after installation:

1. **Download Hebrew traineddata:**
   - Visit: https://github.com/tesseract-ocr/tessdata/raw/main/heb.traineddata
   - Or: https://github.com/tesseract-ocr/tessdata_best/raw/main/heb.traineddata (higher accuracy)

2. **Copy to tessdata directory:**
   ```powershell
   # Find tessdata directory
   $tessdata = "C:\Program Files\Tesseract-OCR\tessdata"
   
   # Copy downloaded file
   Copy-Item "~\Downloads\heb.traineddata" -Destination $tessdata
   ```

3. **Verify:**
   ```powershell
   tesseract --list-langs
   # Should now show "heb"
   ```

---

## Configuration for Python (pytesseract)

**Python wrapper is already installed:**
```bash
pip list | findstr pytesseract
# pytesseract                0.3.13
```

### If Tesseract Not in PATH

Tell pytesseract where to find the executable:

**Option A:** Environment variable (recommended)
```powershell
# Add to .env file:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

**Option B:** In code (app/services/ocr/tesseract_extractor.py)
```python
import pytesseract

# Set path explicitly
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

---

## Testing the Installation

### Quick Test (PowerShell)

Create a test image with Hebrew text:

```powershell
# Test with a simple image
tesseract test_image.png stdout -l heb
```

### Python Test

```python
import pytesseract
from PIL import Image

# Test Hebrew OCR
text = pytesseract.image_to_string(
    Image.open("test_image.png"),
    lang="heb+eng"
)
print(text)
```

### Test with Project Code

```powershell
python -m pytest backend/tests/test_hybrid_ocr_mock.py -v
```

This will use MockOCR. To test real Tesseract, create a test with actual OCR calls.

---

## Troubleshooting

### Error: "tesseract is not recognized"

**Cause:** Tesseract not in PATH  
**Fix:**
1. Verify installation path exists: `Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe"`
2. Add to PATH (see Installation Option 1, step 5)
3. Restart terminal

### Error: "Failed loading language 'heb'"

**Cause:** Hebrew traineddata not installed  
**Fix:**
1. Check: `Get-ChildItem "C:\Program Files\Tesseract-OCR\tessdata" | Where-Object Name -like "*heb*"`
2. If empty: Reinstall with Hebrew selected, or download manually (see Manual Language Data section)

### Error: "TesseractNotFoundError"

**Cause:** pytesseract can't find tesseract.exe  
**Fix:**
1. Set `TESSERACT_CMD` in .env
2. Or set in code: `pytesseract.pytesseract.tesseract_cmd = r'C:\...\tesseract.exe'`

### Slow OCR Performance

**Cause:** Using `tessdata_best` (higher accuracy, slower)  
**Fix:**
- Standard `tessdata` is faster, sufficient accuracy for forms
- Location: Use default `tessdata` folder, not `tessdata_best`

---

## System Requirements

- **OS:** Windows 10/11 (64-bit)
- **Disk Space:** ~200 MB (Tesseract + language data)
- **RAM:** Minimal (OCR is fast)
- **Python:** pytesseract already installed via requirements.txt

---

## MockOCR Fallback

**If you skip Tesseract installation:**

The system will automatically use `MockOCRExtractor` when:
- `HYBRID_ENGINE_ENABLED=false` (baseline mode)
- `DEMO_MODE=true` (demo mode)
- Tesseract executable not found

**MockOCR provides:**
- Zero-cost testing
- Synthetic OCR results for development
- No actual text recognition

**MockOCR does NOT provide:**
- Real text extraction from images
- Cross-verification with Gemini results
- Production-ready OCR capability

---

## Uninstallation

### If installed via Installer:
- Windows Settings → Apps → Tesseract-OCR → Uninstall

### If installed via Chocolatey:
```powershell
choco uninstall tesseract tesseract-languages
```

### Manual cleanup:
```powershell
Remove-Item "C:\Program Files\Tesseract-OCR" -Recurse -Force
```

Remove from PATH:
- Windows Search → "Environment Variables"
- Edit Path → Remove Tesseract entry

---

## Next Steps

After successful installation:

1. **Verify in Project:**
   ```powershell
   python -c "from app.services.ocr.tesseract_extractor import TesseractExtractor; print('OK')"
   ```

2. **Enable Hybrid Engine:**
   - Set `HYBRID_ENGINE_ENABLED=true` in .env
   - Restart backend server

3. **Test with Real Documents:**
   - Upload commitment form
   - Check extraction results include `ocr_value` fields
   - Verify `verification_status` cross-checking

---

## Documentation References

- [Tesseract GitHub](https://github.com/tesseract-ocr/tesseract)
- [UB-Mannheim Windows Builds](https://github.com/UB-Mannheim/tesseract/wiki)
- [pytesseract Documentation](https://pypi.org/project/pytesseract/)
- [Traineddata Files](https://github.com/tesseract-ocr/tessdata)

---

**Installation Status:** Check with `tesseract --version && tesseract --list-langs`
