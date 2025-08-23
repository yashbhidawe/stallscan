#!/usr/bin/env python3
import os
import time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Local imports
from config.settings import settings
from models.schemas import ProcessingStrategy, EnrichedAPIResponse, EnrichedProcessingResult
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
    strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE,
    high_res: bool = True,
    enrich: bool = Query(default=True, description="Enable Google Places enrichment"),
    location: Optional[str] = Query(default=None, description="Search location for Places API (e.g., 'Las Vegas, NV')")
) -> JSONResponse:
    """
    Extract and enrich booth information from PDF floor plan.
    
    - **file**: PDF file to process
    - **strategy**: Processing strategy (adaptive, grid, full)  
    - **high_res**: Use high resolution processing
    - **enrich**: Enable Google Places API enrichment
    - **location**: Location context for Places search
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

        # Step 4: Merge extraction results
        merged = result_merger.merge_extraction_results(all_results)
        extraction_time = time.time() - start_time
        
        print(f"✅ Extraction complete: {merged.total_booths} booths found in {extraction_time:.2f}s")
        
        # Step 5: Enrich with Google Places data
        search_location = location or settings.default_search_location
        enriched_booths, enrichment_time, api_calls = await enrichment_service.enrich_extraction_result(
            merged, 
            location=search_location,
            enable_enrichment=enrich and settings.enable_places_enrichment
        )
        
        total_processing_time = time.time() - start_time
        
        # Step 6: Get enrichment stats
        stats = enrichment_service.get_enrichment_stats(enriched_booths)
        
        # Step 7: Format response
        enrichment_msg = f" (enriched {stats['enriched_booths']}/{stats['total_booths']} companies)" if enrich else ""
        
        response_data = EnrichedAPIResponse(
            message=f"Successfully processed {file.filename} using {strategy.value} strategy{enrichment_msg}",
            total_stalls_found=len(enriched_booths),
            results=[
                EnrichedProcessingResult(
                    filename=file.filename,
                    booths=enriched_booths,
                    total_booths=len(enriched_booths),
                    extraction_method=f"gemini-{strategy.value}",
                    processing_time=round(extraction_time, 2),
                    enrichment_time=round(enrichment_time, 2) if enrich else None,
                    places_api_calls=api_calls if enrich else None
                )
            ]
        )

        print(f"🎉 Complete! Total time: {total_processing_time:.2f}s | Enrichment: {stats['enrichment_rate']}%")
        
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
    places_available = bool(settings.google_places_api_key)
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "places_api": "available" if places_available else "not configured"
    }

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.app_name} v{settings.app_version}",
        "features": [
            "PDF floor plan extraction",
            "Google Places API enrichment",
            "Company details and contact info"
        ],
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)