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
    
    async def process_upload(self, file: UploadFile, dpi: int = None) -> str:
        """
        Save uploaded PDF to temporary file and return path.
        """
        if dpi is None:
            dpi = settings.default_dpi
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            return tmp.name
    
    def pdf_to_images(self, pdf_path: str, dpi: int = None) -> List[Image.Image]:
        """
        Convert PDF to a list of PIL Images.
        """
        if dpi is None:
            dpi = settings.default_dpi
            
        return convert_from_path(pdf_path, dpi=dpi)
    
    def get_processing_dpi(self, high_res: bool = True) -> int:
        """
        Get DPI based on quality setting.
        """
        return settings.high_res_dpi if high_res else settings.normal_dpi