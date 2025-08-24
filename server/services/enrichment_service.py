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
        enable_enrichment: bool = True,
        include_email: bool = True
    ) -> tuple[List[EnrichedBoothData], float, int]:
        """
        Enrich booth data with Google Places information including emails.
        
        Args:
            extraction_result: The extraction result containing booth data
            location: Optional location to help with Places API search
            enable_enrichment: Whether to perform enrichment at all
            include_email: Whether to include email finding (adds processing time)
        
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
                
                email_status = "with emails" if include_email else "without emails"
                print(f"🔍 Enriching {len(company_names)} unique companies ({email_status})...")
                
                # Enrich companies in batch
                enrichment_data = await self.places_service.enrich_companies_batch(
                    company_names, 
                    location=location,
                    max_concurrent=3,  # Conservative rate limiting
                    include_email=include_email
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
                emails_found = sum(1 for data in enrichment_data.values() if data and data.email)
                
                print(f"✅ Enrichment complete: {successful_enrichments}/{len(company_names)} companies found")
                if include_email:
                    print(f"📧 Emails found: {emails_found}/{successful_enrichments} companies")
                print(f"⏱️ Processing time: {enrichment_time:.2f}s")
                
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
        has_email: Optional[bool] = None,
        has_address: Optional[bool] = None,
        min_data_points: Optional[int] = None
    ) -> List[EnrichedBoothData]:
        """
        Filter enriched booths based on Places data criteria.
        
        Args:
            enriched_booths: List of enriched booth data
            has_website: Filter by presence of website
            has_phone: Filter by presence of phone
            has_email: Filter by presence of email
            has_address: Filter by presence of address
            min_data_points: Minimum number of data points (website, phone, email, address)
        
        Returns:
            Filtered list of enriched booth data
        """
        filtered_booths = []
        
        for booth in enriched_booths:
            # If no places data, include booth (original behavior)
            if not booth.places_data:
                # Only include if we're not filtering for specific data
                if (has_website is None and has_phone is None and 
                    has_email is None and has_address is None and 
                    min_data_points is None):
                    filtered_booths.append(booth)
                continue
            
            places = booth.places_data
            
            # Apply individual filters
            if has_website is not None and bool(places.website) != has_website:
                continue
                
            if has_phone is not None and bool(places.phone) != has_phone:
                continue
                
            if has_email is not None and bool(places.email) != has_email:
                continue
                
            if has_address is not None and bool(places.address) != has_address:
                continue
            
            # Apply minimum data points filter
            if min_data_points is not None:
                data_points = sum([
                    bool(places.website),
                    bool(places.phone),
                    bool(places.email),
                    bool(places.address)
                ])
                if data_points < min_data_points:
                    continue
            
            filtered_booths.append(booth)
        
        return filtered_booths
    
    def get_enrichment_stats(self, enriched_booths: List[EnrichedBoothData]) -> Dict[str, int]:
        """
        Get comprehensive statistics about the enrichment process.
        """
        total = len(enriched_booths)
        enriched = sum(1 for booth in enriched_booths if booth.places_data is not None)
        
        with_website = sum(1 for booth in enriched_booths 
                          if booth.places_data and booth.places_data.website)
        with_phone = sum(1 for booth in enriched_booths 
                        if booth.places_data and booth.places_data.phone)
        with_email = sum(1 for booth in enriched_booths 
                        if booth.places_data and booth.places_data.email)
        with_address = sum(1 for booth in enriched_booths 
                          if booth.places_data and booth.places_data.address)
        
        # Calculate booths with multiple data points
        with_2_or_more = sum(1 for booth in enriched_booths 
                           if booth.places_data and sum([
                               bool(booth.places_data.website),
                               bool(booth.places_data.phone),
                               bool(booth.places_data.email),
                               bool(booth.places_data.address)
                           ]) >= 2)
        
        with_3_or_more = sum(1 for booth in enriched_booths 
                           if booth.places_data and sum([
                               bool(booth.places_data.website),
                               bool(booth.places_data.phone),
                               bool(booth.places_data.email),
                               bool(booth.places_data.address)
                           ]) >= 3)
        
        complete_profiles = sum(1 for booth in enriched_booths 
                              if booth.places_data and all([
                                  booth.places_data.website,
                                  booth.places_data.phone,
                                  booth.places_data.email,
                                  booth.places_data.address
                              ]))
        
        return {
            "total_booths": total,
            "enriched_booths": enriched,
            "with_website": with_website,
            "with_phone": with_phone,
            "with_email": with_email,
            "with_address": with_address,
            "with_2_or_more_data_points": with_2_or_more,
            "with_3_or_more_data_points": with_3_or_more,
            "complete_profiles": complete_profiles,
            "enrichment_rate": round((enriched / total * 100) if total > 0 else 0, 1),
            "email_coverage_rate": round((with_email / enriched * 100) if enriched > 0 else 0, 1),
            "complete_profile_rate": round((complete_profiles / total * 100) if total > 0 else 0, 1)
        }
    
    def get_companies_with_emails(self, enriched_booths: List[EnrichedBoothData]) -> List[Dict[str, str]]:
        """
        Extract companies that have email addresses for further processing.
        
        Returns:
            List of dictionaries with company contact information
        """
        companies_with_emails = []
        
        for booth in enriched_booths:
            if booth.places_data and booth.places_data.email:
                company_info = {
                    "company_name": booth.company_name,
                    "booth": booth.booth,
                    "email": booth.places_data.email,
                    "website": booth.places_data.website or "",
                    "phone": booth.places_data.phone or "",
                    "address": booth.places_data.address or ""
                }
                companies_with_emails.append(company_info)
        
        return companies_with_emails
    
    def print_enrichment_summary(self, enriched_booths: List[EnrichedBoothData]) -> None:
        """
        Print a detailed summary of the enrichment results.
        """
        stats = self.get_enrichment_stats(enriched_booths)
        
        print("\n" + "="*50)
        print("📊 ENRICHMENT SUMMARY")
        print("="*50)
        print(f"Total Booths: {stats['total_booths']}")
        print(f"Enriched: {stats['enriched_booths']} ({stats['enrichment_rate']}%)")
        print(f"With Website: {stats['with_website']}")
        print(f"With Phone: {stats['with_phone']}")
        print(f"With Email: {stats['with_email']} ({stats['email_coverage_rate']}% of enriched)")
        print(f"With Address: {stats['with_address']}")
        print(f"With 2+ Data Points: {stats['with_2_or_more_data_points']}")
        print(f"With 3+ Data Points: {stats['with_3_or_more_data_points']}")
        print(f"Complete Profiles: {stats['complete_profiles']} ({stats['complete_profile_rate']}%)")
        print("="*50)
    
    async def enrich_emails_only(
        self, 
        companies_with_websites: List[Dict[str, str]], 
        max_concurrent: int = 3
    ) -> Dict[str, Optional[str]]:
        """
        Find emails for companies that already have website information.
        Useful for post-processing or targeted email finding.
        
        Args:
            companies_with_websites: List of dicts with 'name' and 'website' keys
            max_concurrent: Maximum concurrent requests
        
        Returns:
            Dictionary mapping company names to found emails
        """
        try:
            async with self.places_service:
                return await self.places_service.find_emails_only(
                    companies_with_websites, max_concurrent
                )
        except Exception as e:
            print(f"❌ Email-only enrichment error: {e}")
            return {}