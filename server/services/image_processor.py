from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter
from models.schemas import TileData
from config.settings import settings
import os
import time

class ImageProcessor:
    
    def __init__(self, contrast_factor: float = 2.5, sharpness_factor: float = 3.0):
        """
        Initialize ImageProcessor with configurable enhancement parameters.
        
        Args:
            contrast_factor: Contrast enhancement factor (default: 2.5)
            sharpness_factor: Sharpness enhancement factor (default: 3.0)
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
            print(f"[ERROR] Error enhancing image for OCR: {e}")
            return image  # Return original image if enhancement fails
    
    def calculate_optimal_grid(self, width: int, height: int, 
                             min_tile_size: int = 800) -> Tuple[int, int]:  # Increased from 512
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
        print(f"Total pixels: {total_pixels}")
        
        # Calculate based on total pixels and minimum tile size
        max_cols = max(1, width // min_tile_size)
        max_rows = max(1, height // min_tile_size)
        
        # More conservative grid sizes for better text readability
        if total_pixels > 15_000_000:  # Extra large image
            print("Extra large image")
            rows, cols = min(12, max_rows), min(12, max_cols)  # Reduced from 16
        elif total_pixels > 10_000_000:  # Very large image
            print("Very large image")
            rows, cols = min(6, max_rows), min(6, max_cols)  # Reduced from 8
        elif total_pixels > 5_000_000:  # Large image
            print("Large image")
            rows, cols = min(4, max_rows), min(4, max_cols)  # Reduced from 5
        else:  # Normal image
            print("Normal image")
            rows, cols = min(2, max_rows), min(2, max_cols)
        
        return rows, cols
    
    def adaptive_split_image(self, image: Image.Image, 
                           complexity_threshold: int = 500,
                           min_tile_size: int = 800,
                           save_tiles: bool = True,  # Changed default to True for debugging
                           output_dir: str = "debug_tiles") -> List[Dict[str, Any]]:  # Increased from 512
        """
        Adaptively split image based on complexity and size.
        
        Args:
            image: Input PIL Image
            complexity_threshold: Threshold for determining complexity (unused in current implementation)
            min_tile_size: Minimum tile size in pixels
            save_tiles: Whether to save debug tiles to disk
            output_dir: Directory name for saving tiles
            
        Returns:
            List of tiles with metadata
        """
        width, height = image.size
        tiles = []
        
        # Calculate optimal grid
        rows, cols = self.calculate_optimal_grid(width, height, min_tile_size)
        
        print(f"Splitting {width}x{height} image into {rows}x{cols} grid")
        
        # Create output directory for saving tiles if requested
        output_path = None
        if save_tiles:
            timestamp = int(time.time())
            output_path = f"{output_dir}_{timestamp}"
            try:
                os.makedirs(output_path, exist_ok=True)
                print(f"💾 Saving tiles to: {os.path.abspath(output_path)}")
            except Exception as e:
                print(f"[ERROR] Failed to create output directory {output_path}: {e}")
                save_tiles = False  # Disable saving if directory creation fails
        
        tile_width = width // cols
        tile_height = height // rows
        
        # Calculate intelligent overlap - percentage based, minimum 100px
        overlap_percentage = 0.20  # 20% overlap for better booth capture
        overlap_x = max(100, int(tile_width * overlap_percentage))
        overlap_y = max(100, int(tile_height * overlap_percentage))
        
        print(f"Using overlap: {overlap_x}x{overlap_y} pixels ({overlap_percentage*100}%)")
        
        saved_count = 0
        for r in range(rows):
            for c in range(cols):
                # Calculate tile boundaries with intelligent overlap
                left = max(0, c * tile_width - overlap_x)
                upper = max(0, r * tile_height - overlap_y)
                right = min(width, (c + 1) * tile_width + overlap_x)
                lower = min(height, (r + 1) * tile_height + overlap_y)
                
                # Ensure minimum tile size for text readability
                actual_width = right - left
                actual_height = lower - upper
                
                if actual_width < min_tile_size * 0.7 or actual_height < min_tile_size * 0.7:
                    print(f"Skipping small tile at {r},{c}: {actual_width}x{actual_height}")
                    continue
                
                tile = image.crop((left, upper, right, lower))
                
                # Save tile if requested and directory was created successfully
                tile_path = None
                if save_tiles and output_path:
                    try:
                        tile_filename = f"tile_r{r}_c{c}_{actual_width}x{actual_height}.png"
                        tile_path = os.path.join(output_path, tile_filename)
                        tile.save(tile_path, "PNG", quality=95)
                        saved_count += 1
                        print(f"  💾 Saved: {tile_filename}")
                    except Exception as e:
                        print(f"[ERROR] Failed to save tile {r},{c}: {e}")
                
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
                    'total_tiles': rows * cols,
                    'overlap_info': {
                        'overlap_x': overlap_x,
                        'overlap_y': overlap_y,
                        'has_left_overlap': c > 0,
                        'has_right_overlap': c < cols - 1,
                        'has_top_overlap': r > 0,
                        'has_bottom_overlap': r < rows - 1
                    }
                }
                
                # Add save path to metadata if tile was saved
                if tile_path:
                    tile_info['saved_path'] = tile_path
                
                tiles.append(tile_info)
        
        if save_tiles:
            print(f"✅ Created {len(tiles)} tiles, saved {saved_count} to disk")
            if output_path:
                print(f"📁 Full path: {os.path.abspath(output_path)}")
        else:
            print(f"Created {len(tiles)} tiles with enhanced overlap")
            
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
            
            # More conservative resizing to preserve text clarity
            current_max = max(enhanced_image.size)
            if current_max > max_dim:
                # Use higher quality resampling and be more conservative with resizing
                ratio = max_dim / current_max
                new_size = tuple(int(dim * ratio) for dim in enhanced_image.size)
                
                print(f"Resizing image from {enhanced_image.size} to {new_size}")
                enhanced_image = enhanced_image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Re-enhance after resizing to sharpen text
                enhanced_image = self.enhance_image_for_ocr(enhanced_image, 
                                                          custom_contrast=2.0,
                                                          custom_sharpness=2.5)
            
            return enhanced_image
            
        except Exception as e:
            print(f"[ERROR] Error preparing full image: {e}")
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
                print(f"[WARNING] Image too small: {width}x{height}")
                return False
            
            # Check maximum dimensions (reasonable limits)
            if width > 50000 or height > 50000:
                print(f"[WARNING] Image too large: {width}x{height}")
                return False
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Error validating image: {e}")
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

    def debug_split_image(self, image: Image.Image, 
                         output_dir: str = "debug_tiles",
                         **kwargs) -> List[Dict[str, Any]]:
        """
        Convenience method to force saving of debug tiles.
        
        Args:
            image: Input PIL Image
            output_dir: Directory for saving debug tiles
            **kwargs: Additional arguments passed to adaptive_split_image
            
        Returns:
            List of tiles with metadata
        """
        return self.adaptive_split_image(image, save_tiles=True, output_dir=output_dir, **kwargs)