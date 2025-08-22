#!/usr/bin/env python3
import os
import time
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Local imports
from config.settings import settings
from models.schemas import ProcessingStrategy, APIResponse, ProcessingResult
from services.pdf_processor import PDFProcessor
from services.image_processor import ImageProcessor
from services.gemini_service import GeminiService
from utils.validators import FileValidator
from utils.merger import ResultMerger

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
pdf_processor = PDFProcessor()
image_processor = ImageProcessor()
gemini_service = GeminiService()
result_merger = ResultMerger()
file_validator = FileValidator()

@app.post("/extract")
async def extract_booths(
    file: UploadFile = File(...),
    strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE,
    high_res: bool = True
) -> JSONResponse:
    """
    Extract booth information from PDF floor plan.
    
    - **file**: PDF file to process
    - **strategy**: Processing strategy (adaptive, grid, full)  
    - **high_res**: Use high resolution processing
    """
    # Validate inputs
    file_validator.validate_pdf_file(file)
    file_validator.validate_processing_params(strategy.value, high_res)
    
    start_time = time.time()
    
    try:
        # Step 1: Process PDF upload
        dpi = pdf_processor.get_processing_dpi(high_res)
        pdf_path = await pdf_processor.process_upload(file, dpi)
        
        # Step 2: Convert PDF to images
        page_images = pdf_processor.pdf_to_images(pdf_path, dpi)
        
        all_results = []
        
        # Step 3: Process each page
        for page_num, page_img in enumerate(page_images):
            print(f"📄 Processing page {page_num + 1}, size: {page_img.size}")
            
            if strategy == ProcessingStrategy.FULL:
                # Process entire image
                enhanced_image = image_processor.prepare_full_image(page_img)
                result = gemini_service.extract_from_full_image(enhanced_image)
                all_results.append(result)
                
            elif strategy == ProcessingStrategy.ADAPTIVE:
                # Adaptive processing with fallback
                tiles = image_processor.adaptive_split_image(page_img)
                
                # Process all tiles
                tile_results = []
                for tile_data in tiles:
                    enhanced_tile = {
                        **tile_data,
                        'image': image_processor.enhance_image_for_ocr(tile_data['image'])
                    }
                    result = gemini_service.extract_from_tile(enhanced_tile)
                    tile_results.append(result)
                
                # Check if tiling was successful
                total_found = sum(r.total_booths for r in tile_results)
                if total_found < settings.poor_results_threshold:
                    print(f"⚠️ Tiling found only {total_found} booths, trying full image...")
                    enhanced_image = image_processor.prepare_full_image(page_img)
                    fallback_result = gemini_service.extract_from_full_image(enhanced_image)
                    
                    if fallback_result.total_booths > total_found:
                        all_results.append(fallback_result)
                    else:
                        all_results.extend(tile_results)
                else:
                    all_results.extend(tile_results)
            
            else:  # GRID strategy
                tiles = image_processor.adaptive_split_image(page_img)
                for tile_data in tiles:
                    enhanced_tile = {
                        **tile_data,
                        'image': image_processor.enhance_image_for_ocr(tile_data['image'])
                    }
                    result = gemini_service.extract_from_tile(enhanced_tile)
                    all_results.append(result)

        # Step 4: Merge all results
        merged = result_merger.merge_extraction_results(all_results)
        processing_time = time.time() - start_time
        
        print(f"✅ Processing complete: {merged.total_booths} booths found in {processing_time:.2f}s")
        
        # Step 5: Format response
        response_data = APIResponse(
            message=f"Successfully processed {file.filename} using {strategy.value} strategy",
            total_stalls_found=merged.total_booths,
            results=[
                ProcessingResult(
                    filename=file.filename,
                    booths=merged.booths,
                    total_booths=merged.total_booths,
                    extraction_method=f"gemini-{strategy.value}",
                    processing_time=round(processing_time, 2)
                )
            ]
        )

        return JSONResponse(content=response_data.dict())
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Clean up temporary file
        if 'pdf_path' in locals():
            try:
                os.remove(pdf_path)
            except OSError:
                pass

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.app_name} v{settings.app_version}",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)