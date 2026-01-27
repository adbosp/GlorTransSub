GEMINI_API_KEY = "AIzaSyD-6imSU3aJ6RyebzNScBCrQLxt2VkTX1w"
# Optional: path to tesseract executable. If tesseract is on PATH, set to None
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# Model to use (check your available models via genai.list_models())
GEMINI_MODEL = "models/gemini-flash-latest"


# Capture settings
CAPTURE_FPS = 3 # number of captures per second (real-time responsiveness)
OCR_LANG = "eng+vie" # pytesseract languages installed (e.g. 'eng+vie')