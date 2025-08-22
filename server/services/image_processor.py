from typing import List, Dict, Any
from PIL import Image, ImageEnhance
from models.schemas import TileData
from config.settings import settings

class ImageProcessor:
    
    def enhance_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Enhance image for better OCR results.
        """
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhance contrast and sharpness
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        return image
    
    def adaptive_split_image(self, image: Image.Image, complexity_threshold: int = 500) -> List[Dict[str, Any]]:
        """
        Adaptively split image based on complexity and size.
        Returns list of tiles with metadata.
        """
        width, height = image.size
        total_pixels = width * height
        
        tiles = []
        
        # Determine grid size based on image complexity
        if total_pixels > 10_000_000:  # Very large image
            rows, cols = 4, 4
        elif total_pixels > 5_000_000:  # Large image
            rows, cols = 3, 3
        else:  # Normal image
            rows, cols = 2, 2
        
        tile_width = width // cols
        tile_height = height // rows
        
        for r in range(rows):
            for c in range(cols):
                # Add overlap to avoid cutting through booths
                overlap = settings.overlap_pixels
                
                left = max(0, c * tile_width - overlap)
                upper = max(0, r * tile_height - overlap)
                right = min(width, (c + 1) * tile_width + overlap)
                lower = min(height, (r + 1) * tile_height + overlap)
                
                tile = image.crop((left, upper, right, lower))
                
                tiles.append({
                    'image': tile,
                    'position': f"row_{r}_col_{c}",
                    'coordinates': (left, upper, right, lower),
                    'is_edge': r == 0 or r == rows-1 or c == 0 or c == cols-1
                })
        
        return tiles
    
    def prepare_full_image(self, image: Image.Image) -> Image.Image:
        """
        Prepare image for full-image processing (resize if too large).
        """
        enhanced_image = self.enhance_image_for_ocr(image)
        
        # Resize if too large for API
        max_dimension = settings.max_image_dimension
        if max(enhanced_image.size) > max_dimension:
            ratio = max_dimension / max(enhanced_image.size)
            new_size = tuple(int(dim * ratio) for dim in enhanced_image.size)
            enhanced_image = enhanced_image.resize(new_size, Image.Resampling.LANCZOS)
        
        return enhanced_image