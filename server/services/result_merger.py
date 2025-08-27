from typing import List, Set, Dict, Any
from difflib import SequenceMatcher
from models.schemas import ExtractionResult, BoothData

class ResultMerger:
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize ResultMerger with similarity threshold for duplicate detection.
        
        Args:
            similarity_threshold: Threshold for considering two company names similar (0.85 = 85%)
        """
        self.similarity_threshold = similarity_threshold
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for comparison."""
        if not name:
            return ""
        
        # Clean up malformed names first
        name = name.strip()
        
        # Remove leading/trailing asterisks and other formatting artifacts
        name = name.strip('*').strip('-').strip('&').strip()
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common suffixes and prefixes
        suffixes = [' inc', ' inc.', ' ltd', ' ltd.', ' llc', ' corp', ' corp.', 
                   ' company', ' co', ' co.', ' group', ' international', ' intl']
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # Remove special characters and extra spaces
        normalized = ''.join(c if c.isalnum() else ' ' for c in normalized)
        normalized = ' '.join(normalized.split())  # Remove extra spaces
        
        return normalized
    
    def _normalize_booth_number(self, booth: str) -> str:
        """Normalize booth number for comparison."""
        if not booth:
            return ""
        
        # Convert to uppercase and remove extra spaces
        normalized = booth.upper().strip()
        
        # Remove common separators and normalize format
        normalized = normalized.replace(' ', '').replace('-', '').replace('_', '')
        
        return normalized
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings."""
        if not str1 or not str2:
            return 0.0
        
        # Use SequenceMatcher for similarity calculation
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _are_companies_similar(self, name1: str, name2: str) -> bool:
        """Check if two company names are similar enough to be considered duplicates."""
        norm1 = self._normalize_company_name(name1)
        norm2 = self._normalize_company_name(name2)
        
        if not norm1 or not norm2:
            return False
        
        # Exact match after normalization
        if norm1 == norm2:
            return True
        
        # Similarity-based matching
        similarity = self._calculate_similarity(norm1, norm2)
        return similarity >= self.similarity_threshold
    
    def _are_booths_similar(self, booth1: str, booth2: str) -> bool:
        """Check if two booth numbers refer to the same booth."""
        norm1 = self._normalize_booth_number(booth1)
        norm2 = self._normalize_booth_number(booth2)
        
        if not norm1 or not norm2:
            return False
        
        return norm1 == norm2
    
    def _merge_booth_data(self, booths: List[BoothData]) -> BoothData:
        """Merge multiple BoothData objects into one, preferring more complete information."""
        if not booths:
            return None
        
        if len(booths) == 1:
            return booths[0]
        
        # Find the booth with the most complete information
        best_booth = booths[0]
        best_score = 0
        
        for booth in booths:
            score = 0
            if booth.company_name and len(booth.company_name.strip()) > 0:
                score += len(booth.company_name.strip())
            if booth.booth and len(booth.booth.strip()) > 0:
                score += len(booth.booth.strip()) * 2  # Weight booth numbers higher
            if booth.size and len(booth.size.strip()) > 0:
                score += 10  # Size information is valuable
            
            if score > best_score:
                best_score = score
                best_booth = booth
        
        # Use the best booth as base and fill in missing info from others
        merged = BoothData(
            company_name=best_booth.company_name,
            booth=best_booth.booth,
            size=best_booth.size
        )
        
        # Fill in missing information from other booths
        for booth in booths:
            if not merged.company_name and booth.company_name:
                merged.company_name = booth.company_name
            if not merged.booth and booth.booth:
                merged.booth = booth.booth
            if not merged.size and booth.size:
                merged.size = booth.size
        
        return merged
    
    def merge_extraction_results(self, results: List[ExtractionResult]) -> ExtractionResult:
        """
        Merge multiple extraction results with improved duplicate detection.
        
        Args:
            results: List of ExtractionResult objects
            
        Returns:
            Merged ExtractionResult with duplicates removed
        """
        if not results:
            return ExtractionResult(total_booths=0, booths=[])
        
        all_booths = []
        for result in results:
            all_booths.extend(result.booths)
        
        if not all_booths:
            return ExtractionResult(total_booths=0, booths=[])
        
        print(f"Merging {len(all_booths)} booths from {len(results)} results")
        
        # Group similar booths together
        booth_groups = []
        processed_indices = set()
        
        for i, booth1 in enumerate(all_booths):
            if i in processed_indices:
                continue
            
            # Start a new group with this booth
            current_group = [booth1]
            processed_indices.add(i)
            
            # Find similar booths
            for j, booth2 in enumerate(all_booths[i+1:], i+1):
                if j in processed_indices:
                    continue
                
                # Check if booths are duplicates
                company_match = self._are_companies_similar(booth1.company_name, booth2.company_name)
                booth_match = self._are_booths_similar(booth1.booth, booth2.booth)
                
                # Enhanced duplicate detection for fragmented names
                is_fragment = self._is_fragment_of(booth2.company_name, booth1.company_name)
                
                # Consider as duplicate if:
                # 1. Same company and same booth number
                # 2. Same company and one booth number is empty
                # 3. Very similar company names (likely same company)
                # 4. One name is a fragment of another (e.g., "ENVO" vs "ENVO I")
                if (company_match and booth_match) or \
                   (company_match and (not booth1.booth or not booth2.booth)) or \
                   (company_match and self._calculate_similarity(booth1.company_name, booth2.company_name) > 0.9) or \
                   is_fragment:
                    
                    current_group.append(booth2)
                    processed_indices.add(j)
            
            booth_groups.append(current_group)
        
        # Merge each group into a single booth
        merged_booths = []
        for group in booth_groups:
            merged_booth = self._merge_booth_data(group)
            if merged_booth and merged_booth.company_name:  # Only include booths with company names
                merged_booths.append(merged_booth)
        
        print(f"Merged to {len(merged_booths)} unique booths (removed {len(all_booths) - len(merged_booths)} duplicates)")
        
        return ExtractionResult(
            total_booths=len(merged_booths),
            booths=merged_booths
        )
    
    def get_merge_statistics(self, original_results: List[ExtractionResult], 
                           merged_result: ExtractionResult) -> Dict[str, Any]:
        """Get statistics about the merge operation."""
        total_original = sum(result.total_booths for result in original_results)
        total_merged = merged_result.total_booths
        
        return {
            'original_total': total_original,
            'merged_total': total_merged,
            'duplicates_removed': total_original - total_merged,
            'duplicate_rate': (total_original - total_merged) / total_original if total_original > 0 else 0,
            'sources_merged': len(original_results)
        }
    
    def _is_fragment_of(self, short_name: str, long_name: str) -> bool:
        """Check if short_name is a fragment of long_name."""
        if not short_name or not long_name:
            return False
        
        short_norm = self._normalize_company_name(short_name)
        long_norm = self._normalize_company_name(long_name)
        
        if len(short_norm) < 3 or len(long_norm) < 3:
            return False
        
        # Check if short name is contained in long name or vice versa
        if short_norm in long_norm or long_norm in short_norm:
            return True
        
        # Check if they share a significant common prefix/suffix
        if len(short_norm) >= 4 and len(long_norm) >= 4:
            if (short_norm[:4] == long_norm[:4] or  # Same 4-char prefix
                short_norm[-4:] == long_norm[-4:]):  # Same 4-char suffix
                return True
        
        return False