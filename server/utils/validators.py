from fastapi import UploadFile, HTTPException
from config.settings import settings

class FileValidator:
    @staticmethod
    def validate_pdf_file(file: UploadFile) -> None:
        """
        Validate uploaded PDF file.
        """
        # Check file extension
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are supported"
            )
        
        # Check file size (this is approximate since we haven't read the file yet)
        if hasattr(file, 'size') and file.size:
            max_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
            if file.size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File size must be less than {settings.max_file_size_mb}MB"
                )
    
    @staticmethod
    def validate_processing_params(strategy: str, high_res: bool) -> None:
        """
        Validate processing parameters.
        """
        valid_strategies = ["adaptive", "grid", "full"]
        if strategy not in valid_strategies:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy. Must be one of: {valid_strategies}"
            )
        
        if not isinstance(high_res, bool):
            raise HTTPException(
                status_code=400,
                detail="high_res parameter must be a boolean"
            )