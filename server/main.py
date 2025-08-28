#!/usr/bin/env python3
import os
import time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Local imports
from config.settings import settings
from models.schemas import ProcessingStrategy, EnrichedAPIResponse, EnrichedProcessingResult, BoothData, ExtractionResult
from services.pdf_processor import PDFProcessor
from services.image_processor import ImageProcessor
from services.gemini_service import GeminiService
from services.enrichment_service import CompanyEnrichmentService
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
enrichment_service = CompanyEnrichmentService()
result_merger = ResultMerger()
file_validator = FileValidator()

@app.post("/extract")
async def extract_booths(
    file: UploadFile = File(...),
    strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE,  # Now unused but kept for compatibility
    high_res: bool = True,
    enrich: bool = Query(default=True, description="Enable Google Places enrichment"),
    location: Optional[str] = Query(default=None, description="Search location for Places API (e.g., 'Las Vegas, NV')"),
    debug_tiles: bool = Query(default=False, description="Save tile images for debugging"),
    save_booth_images: bool = Query(default=True, description="Save individual booth detection images")
) -> JSONResponse:
    """
    Extract and enrich booth information from PDF floor plan using OpenCV + Gemini OCR.
    
    - **file**: PDF file to process
    - **high_res**: Use high resolution processing
    - **enrich**: Enable Google Places API enrichment
    - **location**: Location context for Places search
    - **save_booth_images**: Save detected booth images for inspection
    - **strategy**: Kept for compatibility (OpenCV detection is always used)
    """
    # Validate inputs
    file_validator.validate_pdf_file(file)
    file_validator.validate_processing_params(strategy.value, high_res)
    
    # Check if Places API is available for enrichment
    if enrich and not settings.google_places_api_key:
        print("⚠️ Places enrichment requested but API key not available")
        enrich = False
    
    start_time = time.time()
    
    try:
        # Step 1: Process PDF upload
        dpi = pdf_processor.get_processing_dpi(high_res)
        pdf_path = await pdf_processor.process_upload(file, dpi)
        
        # Step 2: Convert PDF to images
        page_images = pdf_processor.pdf_to_images(pdf_path, dpi)
        
        all_booth_data = []
        total_pages = len(page_images)
        
        # Step 3: Process each page with OpenCV detection only
        for page_num, page_img in enumerate(page_images):
            print(f"📄 Processing page {page_num + 1}/{total_pages}, size: {page_img.size}")
            
            # Create output directory for this page
            page_output_dir = f"opencv_output/page_{page_num + 1}"
            
            # Step 3a: OpenCV booth detection
            print("🎯 Using OpenCV booth detection")
            saved_booth_files = image_processor.detect_booths(
                page_img, 
                output_dir=page_output_dir,
                save_individual_detections=save_booth_images
            )
            
            print(f"✅ OpenCV Detection: Found {len(saved_booth_files)} booth regions on page {page_num + 1}")
            
            if saved_booth_files:
                # Step 3b: OCR each detected booth with Gemini
                print(f"🤖 Running Gemini OCR on {len(saved_booth_files)} detected booths...")
                
                for i, booth_file in enumerate(saved_booth_files):
                    try:
                        # Load the detected booth image
                        from PIL import Image
                        booth_image = Image.open(booth_file)
                        
                        # Enhance the booth image for better OCR
                        enhanced_booth = image_processor.enhance_image_for_ocr(booth_image)
                        
                        # Create a tile structure for Gemini OCR
                        booth_tile = {
                            'image': enhanced_booth,
                            'position': f'page_{page_num + 1}_booth_{i+1}',
                            'grid_position': (page_num, i),
                            'coordinates': (0, 0, booth_image.size[0], booth_image.size[1]),
                            'source_file': booth_file
                        }
                        
                        # Run Gemini OCR on this booth
                        ocr_result = gemini_service.extract_from_tile(booth_tile)
                        
                        # Process OCR results
                        if hasattr(ocr_result, 'booths') and ocr_result.booths:
                            for booth_data in ocr_result.booths:
                                # Create new BoothData with all fields (Pydantic models are immutable)
                                enhanced_booth = BoothData(
                                    company_name=booth_data.company_name,
                                    booth=booth_data.booth,
                                    size=booth_data.size,
                                    booth_file=booth_file,
                                    detection_method="opencv+gemini_ocr",
                                    page_number=page_num + 1,
                                    detection_index=i + 1
                                )
                                all_booth_data.append(enhanced_booth)
                                
                            print(f"  🔍 Booth {i+1}: {len(ocr_result.booths)} companies found")
                        else:
                            # Create fallback booth data for failed OCR
                            fallback_booth = BoothData(
                                company_name=f"OCR_Failed_Page{page_num+1}_Booth{i+1}",
                                booth=f"P{page_num+1}B{i+1:03d}",
                                size="Unknown",
                                booth_file=booth_file,
                                detection_method="opencv_ocr_failed",
                                page_number=page_num + 1,
                                detection_index=i + 1
                            )
                            all_booth_data.append(fallback_booth)
                            print(f"  ⚠️ Booth {i+1}: OCR returned no results, using fallback")
                        
                    except Exception as ocr_error:
                        print(f"  ❌ OCR failed for booth {i+1}: {ocr_error}")
                        # Create error fallback booth data
                        error_booth = BoothData(
                            company_name=f"OCR_Error_Page{page_num+1}_Booth{i+1}",
                            booth=f"ERR_P{page_num+1}B{i+1:03d}",
                            size="Unknown",
                            booth_file=booth_file,
                            detection_method="opencv_ocr_error",
                            page_number=page_num + 1,
                            detection_index=i + 1,
                            error_message=str(ocr_error)
                        )
                        all_booth_data.append(error_booth)
                
                if save_booth_images:
                    print(f"📁 Booth images saved to: {page_output_dir}/individual_detections")
                
            else:
                print(f"⚠️ No booths detected on page {page_num + 1} with OpenCV")
        
        # Step 4: Create final extraction result
        total_booths = len(all_booth_data)
        
        final_result = ExtractionResult(
            total_booths=total_booths,
            booths=all_booth_data
        )
        
        extraction_time = time.time() - start_time
        print(f"🔍 OpenCV + Gemini OCR complete: {total_booths} total booth entries found across {total_pages} pages")
        
        # Step 5: Enrich with Google Places data
        if enrich and final_result.booths:
            search_location = location or settings.default_search_location
            enriched_booths, enrichment_time, api_calls = await enrichment_service.enrich_extraction_result(
                final_result, 
                location=search_location,
                enable_enrichment=enrich and settings.enable_places_enrichment
            )
            stats = enrichment_service.get_enrichment_stats(enriched_booths)
            print(f"🌟 Places enrichment: {stats['enriched_booths']}/{stats['total_booths']} companies enriched ({api_calls} API calls)")
        else:
            enriched_booths = final_result.booths
            enrichment_time = 0
            api_calls = 0
            stats = {'enriched_booths': 0, 'total_booths': total_booths, 'enrichment_rate': 0}
            if not final_result.booths:
                print("ℹ️ No booths to enrich")
            elif not enrich:
                print("ℹ️ Enrichment disabled by user")
        
        total_processing_time = time.time() - start_time
        
        # Step 6: Format response
        method_used = "opencv_detection + gemini_ocr"
        enrichment_msg = f" (enriched {stats['enriched_booths']}/{stats['total_booths']} companies)" if enrich else ""
        
        response_data = EnrichedAPIResponse(
            message=f"Successfully processed {file.filename} using {method_used}{enrichment_msg}",
            total_stalls_found=len(enriched_booths),
            results=[
                EnrichedProcessingResult(
                    filename=file.filename,
                    booths=enriched_booths,
                    total_booths=len(enriched_booths),
                    extraction_method=method_used,
                    processing_time=round(extraction_time, 2),
                    enrichment_time=round(enrichment_time, 2) if enrich else None,
                    places_api_calls=api_calls if enrich else None,
                    pages_processed=total_pages,
                    opencv_detections=sum(1 for b in enriched_booths if hasattr(b, 'detection_method') and b.detection_method and 'opencv' in b.detection_method)
                )
            ]
        )
      
        print(f"🎉 Complete! Total time: {total_processing_time:.2f}s | Method: {method_used}")
        
        # Print summary statistics
        detection_methods = {}
        for booth in enriched_booths:
            method = getattr(booth, 'detection_method', 'unknown') or 'unknown'
            detection_methods[method] = detection_methods.get(method, 0) + 1
        
        print(f"📊 Detection method breakdown: {detection_methods}")
        
        return JSONResponse(content=response_data.dict())
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Clean up temporary file
        if 'pdf_path' in locals():
            try:
                os.remove(pdf_path)
                print(f"🧹 Cleaned up temporary file: {pdf_path}")
            except OSError as e:
                print(f"⚠️ Could not remove temporary file: {e}")

@app.get("/health")
async def health():
    """Health check endpoint."""
    places_available = bool(settings.google_places_api_key)
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "detection_method": "opencv + gemini_ocr",
        "places_api": "available" if places_available else "not configured",
        "opencv_detection": "available"
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.app_name} v{settings.app_version}",
        "features": [
            "PDF floor plan extraction",
            "OpenCV booth detection (PRIMARY)",
            "Gemini OCR for detected booths",
            "Google Places API enrichment",
            "Company details and contact info"
        ],
        "detection_pipeline": [
            "1. OpenCV detects booth regions",
            "2. Gemini OCR extracts text from detected booths", 
            "3. Google Places API enriches company data"
        ],
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)