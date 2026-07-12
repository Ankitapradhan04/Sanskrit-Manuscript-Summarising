"""
OCR utilities: image preprocessing + Tesseract text/confidence extraction
for Devanagari manuscript page images.
"""
import cv2
import numpy as np
import pytesseract
from PIL import Image

from config import TESSERACT_CMD, OCR_LANG, OCR_LANG_FALLBACK

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def preprocess_image(image_path):
    """
    Clean up a manuscript scan before OCR:
    grayscale -> denoise -> adaptive threshold -> deskew.
    Returns a PIL.Image ready for pytesseract.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=15)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 11,
    )
    deskewed = _deskew(thresh)
    return Image.fromarray(deskewed)


def _deskew(binary_img):
    """Estimate and correct small rotational skew using the minAreaRect of dark pixels."""
    coords = np.column_stack(np.where(binary_img < 255))
    if coords.shape[0] < 50:
        return binary_img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return binary_img
    (h, w) = binary_img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        binary_img, M, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )


def _run_tesseract(pil_img, lang):
    data = pytesseract.image_to_data(
        pil_img, lang=lang, output_type=pytesseract.Output.DICT
    )
    words, confs = [], []
    for text, conf in zip(data["text"], data["conf"]):
        text = text.strip()
        conf = float(conf)
        if text and conf >= 0:
            words.append(text)
            confs.append(conf)
    full_text = " ".join(words)
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return full_text, avg_conf


def extract_text(image_path):
    """
    OCR a manuscript page image. Tries the 'san' (Sanskrit) Tesseract
    language pack first and falls back to 'hin' (Hindi/Devanagari) if
    'san' isn't installed on this machine.
    Returns (text, avg_confidence).
    """
    pil_img = preprocess_image(image_path)
    try:
        return _run_tesseract(pil_img, OCR_LANG)
    except pytesseract.TesseractError:
        return _run_tesseract(pil_img, OCR_LANG_FALLBACK)
