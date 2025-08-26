from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
from models.schemas import TileData
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class ImageProcessor:
    
    def __init__(self, contrast_factor: float = 1.5, sharpness_factor: float = 2.0):
        """
        Initialize ImageProcessor with configurable enhancement parameters.
        
        Args:
            contrast_factor: Contrast enhancement factor (default: 1.5)
            sharpness_factor: Sharpness enhancement factor (default: 2.0)
        """
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor
    
    def enhance_image_for_ocr(self, image: Image.Image, 
                            custom_contrast: Optional[float] = None,
                            custom_sharpness: Optional[float] = None) -> Image.Image:
        """
        Enhance image for better OCR results.
        
        Args:
            image: Input PIL Image
            custom_contrast: Override default contrast factor
            custom_sharpness: Override default sharpness factor
            
        Returns:
            Enhanced PIL Image
        """
        try:
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply slight gaussian blur to reduce noise before enhancement
            image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Enhance contrast
            contrast_factor = custom_contrast or self.contrast_factor
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(contrast_factor)
            
            # Enhance sharpness
            sharpness_factor = custom_sharpness or self.sharpness_factor
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(sharpness_factor)
            
            # Optional: Enhance brightness slightly for better OCR
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.1)
            
            return image
            
        except Exception as e:
            logger.error(f"Error enhancing image for OCR: {e}")
            return image  # Return original image if enhancement fails
    
    def calculate_optimal_grid(self, width: int, height: int, 
                             min_tile_size: int = 512) -> Tuple[int, int]:
        """
        Calculate optimal grid size based on image dimensions and minimum tile size.
        
        Args:
            width: Image width
            height: Image height  
            min_tile_size: Minimum tile dimension in pixels
            
        Returns:
            Tuple of (rows, cols)
        """
        total_pixels = width * height
        
        # Calculate based on total pixels and minimum tile size
        max_cols = max(1, width // min_tile_size)
        max_rows = max(1, height // min_tile_size)
        
        if total_pixels > 15_000_000:  # Extra large image
            print("Extra large image")
            rows, cols = min(16, max_rows), min(16, max_cols)
        elif total_pixels > 10_000_000:  # Very large image
            print("Very large image")
            rows, cols = min(8, max_rows), min(8, max_cols)
        elif total_pixels > 5_000_000:  # Large image
            print("Large image")
            rows, cols = min(5, max_rows), min(5, max_cols)
        else:  # Normal image
            print("Normal image")
            rows, cols = min(2, max_rows), min(2, max_cols)
        
        return rows, cols
    
    def adaptive_split_image(self, image: Image.Image, 
                           complexity_threshold: int = 500,
                           min_tile_size: int = 512) -> List[Dict[str, Any]]:
        """
        Adaptively split image based on complexity and size.
        
        Args:
            image: Input PIL Image
            complexity_threshold: Threshold for determining complexity (unused in current implementation)
            min_tile_size: Minimum tile size in pixels
            
        Returns:
            List of tiles with metadata
        """
        width, height = image.size
        tiles = []
        
        # Calculate optimal grid
        rows, cols = self.calculate_optimal_grid(width, height, min_tile_size)
        
        logger.info(f"Splitting {width}x{height} image into {rows}x{cols} grid")
        
        tile_width = width // cols
        tile_height = height // rows
        
        for r in range(rows):
            for c in range(cols):
                # Add overlap to avoid cutting through important elements
                overlap = getattr(settings, 'overlap_pixels', 50)  # Default fallback
                
                left = max(0, c * tile_width - overlap)
                upper = max(0, r * tile_height - overlap)
                right = min(width, (c + 1) * tile_width + overlap)
                lower = min(height, (r + 1) * tile_height + overlap)
                
                tile = image.crop((left, upper, right, lower))
                
                # Calculate tile metadata
                tile_info = {
                    'image': tile,
                    'position': f"row_{r}_col_{c}",
                    'grid_position': (r, c),
                    'coordinates': (left, upper, right, lower),
                    'size': tile.size,
                    'is_edge': r == 0 or r == rows-1 or c == 0 or c == cols-1,
                    'is_corner': (r == 0 or r == rows-1) and (c == 0 or c == cols-1),
                    'tile_index': r * cols + c,
                    'total_tiles': rows * cols
                }
                
                tiles.append(tile_info)
        
        return tiles
    
    def prepare_full_image(self, image: Image.Image, 
                          max_dimension: Optional[int] = None) -> Image.Image:
        """
        Prepare image for full-image processing (resize if too large).
        
        Args:
            image: Input PIL Image
            max_dimension: Override default max dimension
            
        Returns:
            Processed PIL Image
        """
        try:
            enhanced_image = self.enhance_image_for_ocr(image)
            
            # Use provided max_dimension or fall back to settings
            max_dim = max_dimension or getattr(settings, 'max_image_dimension', 2048)
            
            # Resize if too large for API
            if max(enhanced_image.size) > max_dim:
                ratio = max_dim / max(enhanced_image.size)
                new_size = tuple(int(dim * ratio) for dim in enhanced_image.size)
                
                logger.info(f"Resizing image from {enhanced_image.size} to {new_size}")
                enhanced_image = enhanced_image.resize(new_size, Image.Resampling.LANCZOS)
            
            return enhanced_image
            
        except Exception as e:
            logger.error(f"Error preparing full image: {e}")
            return image
    
    def validate_image(self, image: Image.Image) -> bool:
        """
        Validate image before processing.
        
        Args:
            image: PIL Image to validate
            
        Returns:
            True if image is valid for processing
        """
        try:
            # Check if image exists and has valid dimensions
            if not image or not hasattr(image, 'size'):
                return False
            
            width, height = image.size
            
            # Check minimum dimensions
            if width < 10 or height < 10:
                logger.warning(f"Image too small: {width}x{height}")
                return False
            
            # Check maximum dimensions (reasonable limits)
            if width > 50000 or height > 50000:
                logger.warning(f"Image too large: {width}x{height}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating image: {e}")
            return False
    
    def get_processing_strategy(self, image: Image.Image) -> Dict[str, Any]:
        """
        Determine the best processing strategy for an image.
        
        Args:
            image: Input PIL Image
            
        Returns:
            Dictionary with recommended processing parameters
        """
        if not self.validate_image(image):
            raise ValueError("Invalid image provided")
        
        width, height = image.size
        total_pixels = width * height
        aspect_ratio = width / height
        
        # Determine processing strategy
        strategy = {
            'use_tiling': total_pixels > 2_000_000,  # Use tiling for images > 2MP
            'suggested_grid': self.calculate_optimal_grid(width, height),
            'enhancement_level': 'high' if total_pixels < 1_000_000 else 'medium',
            'resize_needed': max(width, height) > getattr(settings, 'max_image_dimension', 2048),
            'aspect_ratio': aspect_ratio,
            'complexity_score': min(100, total_pixels / 100_000)  # Simple complexity metric
        }
        
        return strategy