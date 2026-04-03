# bill_reader.py
# Reads a HESCO bill image/PDF and extracts units + amount.
# Always returns a safe dict — never crashes the server.
# If OCR fails for any reason, returns ocr_success=False so the
# frontend shows the manual entry form instead.

import re
import os
import pytesseract
try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# Regex patterns to find units and amount in OCR text
UNITS_PATTERNS = [
    r'(?:units\s*consumed|consumption|kwh|units)[^\d]*(\d{2,5})',
    r'(?:current\s*reading\s*[-–]\s*prev(?:ious)?\s*reading)[^\d]*(\d{2,5})',
    r'(?:net\s*units)[^\d]*(\d{2,5})',
    r'(?:unidades|verbrauch)[^\d]*(\d{2,5})',   # fallback for other languages
]
AMOUNT_PATTERNS = [
    r'(?:amount\s*payable|total\s*payable|net\s*payable|bill\s*amount|total\s*amount)[^\d]*(\d{3,6})',
    r'(?:payable\s*before\s*due)[^\d]*(\d{3,6})',
    r'(?:grand\s*total|total\s*bill)[^\d]*(\d{3,6})',
    r'(?:rs\.?\s*|pkr\s*)(\d{3,6})',
]


def _safe_open_image(file_path: str):
    """
    Open image safely. Converts HEIC/WEBP/BMP to RGB first.
    Returns a PIL Image or raises an exception with a clear message.
    """
    # Try opening directly first
    try:
        img = Image.open(file_path)
        img.verify()                        # check file is not corrupt
        img = Image.open(file_path)         # reopen after verify (verify closes it)
        return img.convert('RGB')
    except Exception as e:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.heic', '.heif']:
            raise ValueError(
                'iPhone HEIC format is not supported. '
                'Please take a screenshot of the bill image and upload that instead.'
            )
        raise ValueError(f'Could not open image ({ext}): {str(e)}')


def _preprocess(img) -> object:
    """Convert to grayscale and sharpen for better OCR accuracy."""
    img = img.convert('L')                          # grayscale
    img = ImageEnhance.Contrast(img).enhance(2.0)  # boost contrast
    img = img.filter(ImageFilter.SHARPEN)
    return img


def _search(text: str, patterns: list):
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            val = int(match.group(1))
            if val > 0:
                return val
    return None


def extract_bill_data(file_path: str) -> dict:
    """
    Main function. Always returns:
    {
        units:       int or None,
        amount:      int or None,
        ocr_success: bool,
        error:       str or None   — user-friendly error message
    }
    Never raises an exception.
    """
    result = {
        'units':       None,
        'amount':      None,
        'ocr_success': False,
        'error':       None,
    }

    # OCR not installed — silent fallback, not an error
    if not OCR_AVAILABLE:
        result['error'] = (
            'Automatic bill reading is not set up on this device. '
            'Please enter your units and amount manually below.'
        )
        return result

    try:
        # Handle PDF
        if file_path.lower().endswith('.pdf'):
            if not PDF_AVAILABLE:
                result['error'] = (
                    'PDF reading requires pdf2image. '
                    'Please take a photo of your bill and upload that instead.'
                )
                return result
            pages    = convert_from_path(file_path, dpi=200, first_page=1, last_page=1)
            img      = pages[0].convert('RGB')
        else:
            img = _safe_open_image(file_path)

        # Pre-process and run OCR
        processed = _preprocess(img)
        raw_text  = pytesseract.image_to_string(processed, lang='eng')

        units  = _search(raw_text, UNITS_PATTERNS)
        amount = _search(raw_text, AMOUNT_PATTERNS)

        result['units']       = units
        result['amount']      = amount
        result['ocr_success'] = (units is not None or amount is not None)

        if not result['ocr_success']:
            result['error'] = (
                'Could not find units or amount in the bill image. '
                'The image may be blurry or the bill format is different. '
                'Please enter the values manually below.'
            )
        if not PIL_AVAILABLE:
            result['error'] = (
        'Image processing is not available on this device. '
        'Please enter your units and amount manually below.'
    )
        return result
    except ValueError as e:
        # Known, user-friendly errors (e.g. HEIC format)
        result['error'] = str(e)

    except Exception as e:
        # Unexpected errors — give a safe message, don't expose internal details
        result['error'] = (
            'An error occurred while reading the bill. '
            'Please enter your units and amount manually below.'
        )

    return result