import tempfile
from typing import List
from PIL import Image
from pdf2image import convert_from_path
from fastapi import UploadFile
from config.settings import settings

class PDFProcessor:
    def __init__(self):
        # Disable PIL image size limit
        Image.MAX_IMAGE_PIXELS = None
        print("[DEBUG] PDFProcessor initialized (image size limit disabled).")

    async def process_upload(self, file: UploadFile, dpi: int = None) -> str:
        """
        Save uploaded PDF to temporary file and return path.
        """
        if dpi is None:
            dpi = settings.default_dpi
        print(f"[DEBUG] Using DPI={dpi} for uploaded PDF processing.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        print(f"[INFO] Uploaded PDF saved to temporary file: {tmp_path}")
        return tmp_path

    def pdf_to_images(self, pdf_path: str, dpi: int = None) -> List[Image.Image]:
        """
        Convert PDF to a list of PIL Images.
        """
        if dpi is None:
            dpi = settings.default_dpi
        print(f"[DEBUG] Converting PDF at {pdf_path} to images with DPI={dpi}.")

        try:
            images = convert_from_path(pdf_path, dpi=dpi)
            print(f"[INFO] Converted PDF {pdf_path} into {len(images)} images.")
            return images
        except Exception as e:
            print(f"[ERROR] Failed to convert PDF {pdf_path} to images: {e}")
            raise

    def get_processing_dpi(self, high_res: bool = True) -> int:
        """
        Get DPI based on quality setting.
        """
        dpi = settings.high_res_dpi if high_res else settings.normal_dpi
        print(f"[DEBUG] Selected DPI={dpi} (high_res={high_res}).")
        return dpi
