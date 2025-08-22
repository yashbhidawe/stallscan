from typing import List, Set
from models.schemas import ExtractionResult, BoothData

class ResultMerger:
    @staticmethod
    def merge_extraction_results(results: List[ExtractionResult]) -> ExtractionResult:
        """
        Intelligently merge multiple extraction results with deduplication.
        """
        all_booths = []
        seen_combinations: Set[str] = set()
        
        for result in results:
            if not result or not hasattr(result, 'booths'):
                continue
                
            for booth in result.booths:
                if not booth:
                    continue
                
                # Safely get values and handle None cases
                company = (booth.company_name or "").strip()
                booth_num = (booth.booth or "").strip()
                size = (booth.size or "").strip()
                
                # Skip entries without company names (ONLY include booths with companies)
                if not company or company.lower().strip() in ['', 'none', 'null', 'n/a']:
                    continue
                
                # Create deduplication key - prioritize company name since it's required
                dedup_key = f"company:{company.lower()}"
                combo_key = f"{company.lower()}:{booth_num.lower()}"
                
                if dedup_key not in seen_combinations and combo_key not in seen_combinations:
                    all_booths.append(BoothData(
                        company_name=company,
                        booth=booth_num,
                        size=size
                    ))
                    seen_combinations.add(dedup_key)
                    seen_combinations.add(combo_key)
        
        # Sort results by booth number first, then company name
        sorted_booths = sorted(
            all_booths, 
            key=lambda x: (x.booth or "", x.company_name or "")
        )
        
        return ExtractionResult(
            total_booths=len(sorted_booths),
            booths=sorted_booths
        )