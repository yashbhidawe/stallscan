import io
import json
from typing import Dict, Any
from PIL import Image
import google.generativeai as genai
from config.settings import settings
from models.schemas import ExtractionResult, BoothData

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
    
    def _get_tile_prompt(self, position: str) -> str:
        """Get prompt for tile-based extraction."""
        return f"""
        You are analyzing a floor plan section (position: {position}).
        
        TASK: Extract booth information for EXHIBITORS/COMPANIES only:
        - company_name (company/exhibitor name) - REQUIRED
        - booth (booth number like A1, B23, Hall-5-123, etc.)
        - size (if visible, in sq.m or sq.ft)
        
        CRITICAL REQUIREMENTS:
        1. ONLY include booths that have a visible company/exhibitor name
        2. DO NOT include booths that only have numbers without company names
        3. DO NOT include empty stalls, corridors, or facility areas
        4. Look for company/brand names, not just booth numbers
        5. Skip duplicates from image overlap
        6. Focus on each individual company booth, not the entire section
        7. Assign the correct booth number to corrosponding company name
        
        Return ONLY valid JSON in this exact format:
        {{
          "total_booths": <number>,
          "booths": [
            {{"company_name": "Company Name", "booth": "A123", "size": "12 sq.m"}},
            {{"company_name": "Another Company", "booth": "B456", "size": ""}}
          ]
        }}
        
        If no company booths found, return: {{"total_booths": 0, "booths": []}}
        """
    
    def _get_full_image_prompt(self) -> str:
        """Get prompt for full image extraction."""
        return """
        You are analyzing a complete floor plan image.
        
        TASK: Extract booth information for EXHIBITORS/COMPANIES only.
        
        CRITICAL REQUIREMENTS:
        1. ONLY extract booths that have visible company/exhibitor names
        2. DO NOT include empty booths or booths with only numbers
        3. Focus on clearly readable company names and brand names
        4. Include booth numbers when available, but company name is MANDATORY
        5. Skip facility areas, corridors, registration desks, etc.
        
        Return valid JSON:
        {
          "total_booths": <number>,
          "booths": [
            {"company_name": "...", "booth": "...", "size": "..."}
          ]
        }
        """
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL image to bytes."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    
    def _validate_and_clean_result(self, result: Dict[str, Any]) -> ExtractionResult:
        """Validate and clean Gemini response."""
        if not isinstance(result, dict):
            return ExtractionResult(total_booths=0, booths=[])
        
        booths = result.get("booths", [])
        if not isinstance(booths, list):
            return ExtractionResult(total_booths=0, booths=[])
        
        # Clean up booth data
        cleaned_booths = []
        for booth in booths:
            if isinstance(booth, dict):
                company_name = str(booth.get("company_name") or "").strip()
                booth_num = str(booth.get("booth") or "").strip()
                size = str(booth.get("size") or "").strip()
                
                # Only include booths with company names
                if company_name and company_name.lower() not in ['none', 'null', 'n/a']:
                    cleaned_booths.append(BoothData(
                        company_name=company_name,
                        booth=booth_num,
                        size=size
                    ))
        
        return ExtractionResult(
            total_booths=len(cleaned_booths),
            booths=cleaned_booths
        )
    
    def extract_from_tile(self, tile_data: Dict[str, Any]) -> ExtractionResult:
        """Extract booth information from image tile."""
        image = tile_data['image']
        position = tile_data['position']
        
        try:
            img_bytes = self._image_to_bytes(image)
            prompt = self._get_tile_prompt(position)
            
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/png", "data": img_bytes}],
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": settings.gemini_temperature,
                }
            )
            
            result = json.loads(response.text)
            return self._validate_and_clean_result(result)
            
        except Exception as e:
            print(f"❌ Error processing tile {position}: {e}")
            return ExtractionResult(total_booths=0, booths=[])
    
    def extract_from_full_image(self, image: Image.Image) -> ExtractionResult:
        """Extract booth information from full image."""
        try:
            img_bytes = self._image_to_bytes(image)
            prompt = self._get_full_image_prompt()
            
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/png", "data": img_bytes}],
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": settings.gemini_temperature,
                }
            )
            
            result = json.loads(response.text)
            return self._validate_and_clean_result(result)
            
        except Exception as e:
            print(f"❌ Fallback processing error: {e}")
            return ExtractionResult(total_booths=0, booths=[])