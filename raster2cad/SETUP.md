# Raster2CAD Setup Guide

Complete setup instructions for Raster2CAD on Windows, macOS, and Linux.

## ⚡ Quick Start (5 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/cejezed/ScanCad.git
cd ScanCad/raster2cad
```

### 2. Create `.env` File

Copy the example file:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS/Linux
cp .env.example .env
```

### 3. Edit `.env` with Your API Key

Open `.env` in your editor and fill in your API key:

```bash
# Choose ONE: Claude OR OpenAI (or leave both empty for mock mode)

# Option A: Claude (Anthropic)
ANTHROPIC_API_KEY=sk_live_your_key_here

# Option B: OpenAI
OPENAI_API_KEY=sk-proj-your_key_here
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Start Server

```bash
python -m app.api
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 6. Open Browser

```
http://localhost:8000
```

**Done!** 🎉

---

## 📋 Getting API Keys

### Claude (Anthropic)

1. Go to: https://console.anthropic.com
2. Sign up (free, get $5 credits)
3. Create API key
4. Copy key to `.env`:
   ```
   ANTHROPIC_API_KEY=sk_live_xxx...
   ```

### OpenAI

1. Go to: https://platform.openai.com/api-keys
2. Sign up (free, get $5 credits)
3. Create API key
4. Copy key to `.env`:
   ```
   OPENAI_API_KEY=sk-proj-xxx...
   ```

---

## 🔐 Environment Variables (.env)

### Required

You need **at least ONE** of:

```bash
# Claude/Anthropic
ANTHROPIC_API_KEY=sk_live_...

# OR OpenAI
OPENAI_API_KEY=sk-proj-...
```

### Optional

```bash
# Resolution for vectorization (default: 300)
DPI=300

# Logging level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

---

## ⚠️ Security Notes

**IMPORTANT:**

1. ✅ `.env` file is **ignored by Git** (never committed)
2. ✅ `.env.example` is **in the repo** (template only)
3. ⚠️ **NEVER commit your actual `.env` file**
4. ⚠️ **NEVER share your API keys**

Check `.gitignore`:
```
.env          ← Your secret keys (NOT in repo)
.env.example  ← Template (in repo)
```

---

## 🎯 Usage Modes

### Mode 1: Mock (No API Key)

Works **offline**, no API key needed:

```bash
# Don't set ANTHROPIC_API_KEY or OPENAI_API_KEY
python -m app.api
```

App generates realistic test data. Good for:
- ✅ Testing UI
- ✅ Testing vectorization
- ✅ Demo purposes
- ❌ NOT for analyzing your actual drawings

### Mode 2: Claude Analysis

With Claude API key:

```bash
ANTHROPIC_API_KEY=sk_live_... python -m app.api
# or set in .env and: python -m app.api
```

Analyzes your actual drawings with Claude.

### Mode 3: OpenAI Analysis

With OpenAI API key:

```bash
OPENAI_API_KEY=sk-proj-... python -m app.api
# or set in .env and: python -m app.api
```

Analyzes your actual drawings with GPT-4 Vision.

---

## 🚀 Complete Setup Steps

### Step 1: Prerequisites

Ensure you have:
- Python 3.9+ installed
- Git installed
- Internet connection

Verify:
```bash
python --version  # Should show 3.9+
git --version     # Should show git version
```

### Step 2: Clone & Enter Directory

```bash
git clone https://github.com/cejezed/ScanCad.git
cd ScanCad/raster2cad
```

Verify you're in right place:
```bash
ls  # Should show: app/ web/ requirements.txt .env.example etc.
```

### Step 3: Create Environment File

```bash
# Copy template
cp .env.example .env  # macOS/Linux
# OR
Copy-Item .env.example .env  # Windows PowerShell
```

### Step 4: Get API Key (Optional)

If you want real analysis (not mock):

- **Claude**: https://console.anthropic.com (free $5)
- **OpenAI**: https://platform.openai.com (free $5)

Copy key to `.env`:

```bash
# Open .env in your editor and fill in one:
ANTHROPIC_API_KEY=sk_live_abc123...
# OR
OPENAI_API_KEY=sk-proj-xyz789...
```

### Step 5: Install Python Packages

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (web server)
- OpenCV (computer vision)
- ezdxf (CAD generation)
- requests (HTTP)
- python-dotenv (environment loading)
- ... and more

### Step 6: Start Server

```bash
python -m app.api
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 7: Open Web UI

In your browser:
```
http://localhost:8000
```

You should see the Raster2CAD interface.

### Step 8: Test It!

1. Upload a drawing (JPG, PNG, or PDF)
2. Click "Analyze Drawing"
3. Click "Generate DXF"
4. Download the DXF file
5. Open in CAD software (AutoCAD, BricsCAD, etc.)

---

## 🐛 Troubleshooting

### "Can't find Python"

```bash
# Try python3 instead
python3 -m app.api
```

### "Module not found"

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### "API key invalid"

1. Check key is correct: `echo $ANTHROPIC_API_KEY` (or OPENAI_API_KEY)
2. Check .env file exists
3. Restart server after changing .env

### "Can't connect to http://localhost:8000"

1. Check server is running (see terminal)
2. Check firewall isn't blocking port 8000
3. Try: http://127.0.0.1:8000 instead

### "DXF won't open"

1. Try online viewer: https://www.autodesk.com/viewer
2. Check server logs for errors
3. Verify input image is valid

---

## 📁 File Structure

```
raster2cad/
├── .env              ← Your secrets (LOCAL, not in repo)
├── .env.example      ← Template (in repo)
├── app/
│   ├── api.py        ← Loads .env automatically
│   ├── llm_analyzer.py
│   ├── vectorize.py
│   └── ...
├── web/
│   └── index.html
├── requirements.txt
└── ...
```

---

## ✅ Verification Checklist

- [ ] Repository cloned
- [ ] `.env` file created from `.env.example`
- [ ] API key added to `.env` (or left empty for mock)
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Server starts: `python -m app.api`
- [ ] Web UI loads: http://localhost:8000
- [ ] Can upload image
- [ ] Can analyze drawing
- [ ] Can generate DXF
- [ ] DXF file downloads

---

## 🎓 Next Steps

1. **Read README.md** for API documentation
2. **Read WEB_UI_GUIDE.md** for UI instructions
3. **Try CLI**: `python -m cli.raster2cad --help`
4. **Run tests**: `pytest tests/ -v`

---

## 💬 Need Help?

1. Check `.env` file exists and is readable
2. Check API key is valid (copy-paste carefully!)
3. Check server logs (in terminal)
4. Check browser console (F12 → Console)
5. Check network tab (F12 → Network)

---

**Happy vectorizing!** 🚀
