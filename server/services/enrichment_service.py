import time
from typing import List, Optional, Dict
from models.schemas import ExtractionResult, EnrichedBoothData, PlacesData
from services.places_service import GooglePlacesService

class CompanyEnrichmentService:
    def __init__(self):
        self.places_service = GooglePlacesService()
    
    async def enrich_extraction_result(
        self, 
        extraction_result: ExtractionResult, 
        location: Optional[str] = None,
        enable_enrichment: bool = True
    ) -> tuple[List[EnrichedBoothData], float, int]:
        """
        Enrich booth data with Google Places information.
        
        Returns:
            - List of enriched booth data
            - Enrichment processing time
            - Number of API calls made
        """
        if not enable_enrichment or not extraction_result.booths:
            # Return non-enriched data
            enriched_booths = [
                EnrichedBoothData(
                    company_name=booth.company_name,
                    booth=booth.booth,
                    size=booth.size,
                    places_data=None
                )
                for booth in extraction_result.booths
            ]
            return enriched_booths, 0.0, 0
        
        start_time = time.time()
        
        try:
            async with self.places_service:
                # Extract unique company names
                company_names = list(set([
                    booth.company_name 
                    for booth in extraction_result.booths 
                    if booth.company_name and booth.company_name.strip()
                ]))
                
                print(f"🔍 Enriching {len(company_names)} unique companies...")
                
                # Enrich companies in batch
                enrichment_data = await self.places_service.enrich_companies_batch(
                    company_names, 
                    location=location,
                    max_concurrent=3  # Conservative rate limiting
                )
                
                # Create enriched booth data
                enriched_booths = []
                for booth in extraction_result.booths:
                    places_data = enrichment_data.get(booth.company_name)
                    
                    enriched_booth = EnrichedBoothData(
                        company_name=booth.company_name,
                        booth=booth.booth,
                        size=booth.size,
                        places_data=places_data
                    )
                    enriched_booths.append(enriched_booth)
                
                enrichment_time = time.time() - start_time
                successful_enrichments = sum(1 for data in enrichment_data.values() if data is not None)
                
                print(f"✅ Enrichment complete: {successful_enrichments}/{len(company_names)} companies found in {enrichment_time:.2f}s")
                
                return enriched_booths, enrichment_time, len(company_names)
                
        except Exception as e:
            print(f"❌ Enrichment error: {e}")
            # Return non-enriched data on error
            enriched_booths = [
                EnrichedBoothData(
                    company_name=booth.company_name,
                    booth=booth.booth,
                    size=booth.size,
                    places_data=None
                )
                for booth in extraction_result.booths
            ]
            return enriched_booths, time.time() - start_time, 0
    
    def filter_enriched_booths(
        self, 
        enriched_booths: List[EnrichedBoothData],
        has_website: Optional[bool] = None,
        has_phone: Optional[bool] = None,
    ) -> List[EnrichedBoothData]:
        """
        Filter enriched booths based on Places data criteria.
        """
        filtered_booths = []
        
        for booth in enriched_booths:
            # If no places data, include booth (original behavior)
            if not booth.places_data:
                filtered_booths.append(booth)
                continue
            
            places = booth.places_data
            
            # Apply filters
            if has_website is not None and bool(places.website) != has_website:
                continue
                
            if has_phone is not None and bool(places.phone) != has_phone:
                continue
            
            filtered_booths.append(booth)
        
        return filtered_booths
    
    def get_enrichment_stats(self, enriched_booths: List[EnrichedBoothData]) -> Dict[str, int]:
        """
        Get statistics about the enrichment process.
        """
        total = len(enriched_booths)
        enriched = sum(1 for booth in enriched_booths if booth.places_data is not None)
        with_website = sum(1 for booth in enriched_booths if booth.places_data and booth.places_data.website)
        with_phone = sum(1 for booth in enriched_booths if booth.places_data and booth.places_data.phone)
        with_address = sum(1 for booth in enriched_booths if booth.places_data and booth.places_data.address)
        
        return {
            "total_booths": total,
            "enriched_booths": enriched,
            "with_website": with_website,
            "with_phone": with_phone,
            "with_address": with_address,
            "enrichment_rate": round((enriched / total * 100) if total > 0 else 0, 1)
        }