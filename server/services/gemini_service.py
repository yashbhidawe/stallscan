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
        
        TASK: Extract booth information for EXHIBITORS/COMPANIES only.
        
        FLOOR PLAN CONTEXT:
        - This is a trade show/exhibition floor plan
        - Booths contain company/exhibitor names with booth numbers
        - Booth numbers follow patterns like: A1, B23, Hall-5-123, 5A, C-45, etc.
        - Companies may have multiple booth numbers (e.g., "Company ABC: A1-A3")
        - Ignore: restrooms, food courts, registration areas, entrances, aisles, emergency exits
        
        EXTRACTION RULES:
        1. MANDATORY: Only extract if you see BOTH company name AND booth number together
        2. Company names are usually in larger/bold text near booth numbers
        3. If booth number is unclear, still extract if company name is clear and near a number
        4. Handle booth ranges: "A1-A3" means booths A1, A2, A3 for same company
        5. Skip empty booths showing only numbers without company names
        6. For overlapping areas, include booths that are >70% visible in this section
        
        BOOTH NUMBER PATTERNS TO RECOGNIZE:
        - Single: A1, B23, 5A, Hall-A-123
        - Ranges: A1-A3, B10-B12, 5A-5C
        - Multiple: A1,A2 or A1 & A2
        
        Return ONLY valid JSON in this exact format:
        {{
          "total_booths": <number>,
          "booths": [
            {{"company_name": "Company Name", "booth": "A123", "size": "12 sq.m"}},
            {{"company_name": "Another Company", "booth": "B456-B458", "size": ""}}
          ]
        }}
        
        If no company booths found, return: {{"total_booths": 0, "booths": []}}
        """
    
    def _get_full_image_prompt(self) -> str:
        """Get prompt for full image extraction."""
        return """
        You are analyzing a complete trade show/exhibition floor plan.
        
        TASK: Extract ALL exhibitor booth information from this floor plan.
        
        FLOOR PLAN ANALYSIS:
        1. First, understand the overall layout and booth numbering system
        2. Identify different sections/halls if present
        3. Look for booth numbering patterns (A1-A50, B1-B30, etc.)
        4. Find company/exhibitor names associated with booth numbers
        
        EXTRACTION REQUIREMENTS:
        - ONLY extract booths with visible company/exhibitor names
        - Include booth number whenever visible (A1, B23, Hall-5-123, etc.)
        - Handle booth ranges (A1-A3 means multiple booths for same company)
        - Skip facility areas: restrooms, cafes, registration, aisles, entrances
        - Company names are priority - if unclear booth number but clear company, include it
        
        BOOTH FORMATS TO EXPECT:
        - Standard: "Company Name" at booth "A123"
        - Range: "Company ABC" at booths "A1-A3"  
        - Multiple: "Company XYZ" at "A1, A2, A5"
        
        Return comprehensive JSON with ALL exhibitors found:
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
        
        # Clean up booth data with better validation
        cleaned_booths = []
        for booth in booths:
            if isinstance(booth, dict):
                company_name = str(booth.get("company_name") or "").strip()
                booth_num = str(booth.get("booth") or "").strip()
                size = str(booth.get("size") or "").strip()
                
                # Enhanced validation for company names
                if self._is_valid_company_name(company_name):
                    # Don't expand booth ranges - keep original booth number
                    cleaned_booths.append(BoothData(
                        company_name=company_name,
                        booth=booth_num,
                        size=size
                    ))
        
        return ExtractionResult(
            total_booths=len(cleaned_booths),
            booths=cleaned_booths
        )
    
    def _is_valid_company_name(self, company_name: str) -> bool:
        """Check if company name is valid and not fragmented text."""
        if not company_name or len(company_name.strip()) < 3:
            return False
        
        name = company_name.strip()
        
        # Skip obvious invalid names
        invalid_names = ['none', 'null', 'n/a', 'tbd', 'tba', 'available']
        if name.lower() in invalid_names:
            return False
        
        # Skip fragmented text patterns
        if (name.endswith('**') or name.startswith('**') or
            name.count('*') > 2 or
            name.endswith('&') or name.startswith('&') or
            len(name) <= 3 and not name.replace('-', '').replace('&', '').isalnum()):
            return False
        
        # Skip names that are mostly numbers or special characters
        alpha_chars = sum(c.isalpha() for c in name)
        if alpha_chars < len(name) * 0.6:  # At least 60% alphabetic characters
            return False
        
        # Skip names that look like partial/fragmented text
        if (name.endswith('-') and len(name) < 10) or name.startswith('-'):
            return False
            
        return True
    
    def _expand_booth_ranges(self, booth_str: str) -> list:
        """Expand booth ranges like A1-A3 into [A1, A2, A3]."""
        if not booth_str or '-' not in booth_str:
            return [booth_str] if booth_str else ['']
        
        try:
            # Handle ranges like A1-A3, B10-B12
            if '-' in booth_str and booth_str.count('-') == 1:
                start, end = booth_str.split('-')
                start, end = start.strip(), end.strip()
                
                # Extract letter prefix and numbers
                start_letters = ''.join(c for c in start if c.isalpha())
                start_nums = ''.join(c for c in start if c.isdigit())
                end_letters = ''.join(c for c in end if c.isalpha())
                end_nums = ''.join(c for c in end if c.isdigit())
                
                # If same letter prefix, expand the range
                if start_letters == end_letters and start_nums and end_nums:
                    start_num = int(start_nums)
                    end_num = int(end_nums)
                    
                    if start_num <= end_num <= start_num + 10:  # Reasonable range limit
                        return [f"{start_letters}{i}" for i in range(start_num, end_num + 1)]
            
        except (ValueError, AttributeError):
            pass
        
        # If expansion fails, return original
        return [booth_str]
    
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