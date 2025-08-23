from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from enum import Enum

class ProcessingStrategy(str, Enum):
    ADAPTIVE = "adaptive"
    GRID = "grid" 
    FULL = "full"

class BoothData(BaseModel):
    company_name: str
    booth: str
    size: Optional[str] = ""

class TileData(BaseModel):
    position: str
    coordinates: tuple[int, int, int, int]
    is_edge: bool

class ExtractionResult(BaseModel):
    total_booths: int
    booths: List[BoothData]

class ProcessingResult(BaseModel):
    filename: str
    booths: List[BoothData]
    total_booths: int
    extraction_method: str
    processing_time: float

class APIResponse(BaseModel):
    message: str
    total_stalls_found: int
    results: List[ProcessingResult]

class UploadRequest(BaseModel):
    strategy: ProcessingStrategy = ProcessingStrategy.ADAPTIVE
    high_res: bool = True

# Google Places integration
class PlacesData(BaseModel):
    place_id: Optional[str] = None
    name: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
   

class EnrichedBoothData(BoothData):
    places_data: Optional[PlacesData] = None

class EnrichedProcessingResult(BaseModel):
    filename: str
    booths: List[EnrichedBoothData]
    total_booths: int
    extraction_method: str
    processing_time: float
    enrichment_time: Optional[float] = None
    places_api_calls: Optional[int] = None

class EnrichedAPIResponse(BaseModel):
    message: str
    total_stalls_found: int
    results: List[EnrichedProcessingResult]