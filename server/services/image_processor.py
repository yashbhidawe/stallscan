from typing import List, Dict, Any, Optional, Tuple, Union
from PIL import Image, ImageEnhance, ImageFilter
import os
from pdf2image import convert_from_path
from .slice_floorplan import detect_stalls


class ImageProcessor:
    
    def __init__(self, contrast_factor: float = 2.5, sharpness_factor: float = 3.0):
        """
        Initialize ImageProcessor with configurable enhancement parameters.
        """
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor
    
    def convert_pdf_to_image(self, pdf_path: str, dpi: int = 300, page: int = 0) -> Image.Image:
        """
        Convert PDF to PIL Image - supports any PDF file path.
        
        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for conversion (300 is good for detection)
            page: Page number to convert (0-indexed)
            
        Returns:
            PIL Image of the specified PDF page
        """
        try:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
                
            print(f"Converting '{pdf_path}' to a high-resolution image...")
            images = convert_from_path(pdf_path, dpi=dpi)
            
            if page >= len(images):
                raise IndexError(f"Page {page} not found. PDF has {len(images)} pages.")
                
            return images[page]
            
        except Exception as e:
            print(f"Error converting PDF. Is Poppler installed and in your PATH? Details: {e}")
            raise
    
    def enhance_image_for_ocr(
        self, 
        image: Image.Image, 
        custom_contrast: Optional[float] = None,
        custom_sharpness: Optional[float] = None
    ) -> Image.Image:
        """Enhance image for better OCR results."""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Reduce noise slightly before enhancing
            image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
            
            # Contrast
            contrast_factor = custom_contrast or self.contrast_factor
            image = ImageEnhance.Contrast(image).enhance(contrast_factor)
            
            # Sharpness
            sharpness_factor = custom_sharpness or self.sharpness_factor
            image = ImageEnhance.Sharpness(image).enhance(sharpness_factor)
            
            # Brightness boost
            image = ImageEnhance.Brightness(image).enhance(1.1)
            
            return image
        except Exception as e:
            print(f"[ERROR] Error enhancing image for OCR: {e}")
            return image
    
    def prepare_full_image(
        self, 
        image: Image.Image, 
        max_dimension: Optional[int] = None
    ) -> Image.Image:
        """Resize + enhance large images for processing."""
        try:
            enhanced = self.enhance_image_for_ocr(image)
            max_dim = max_dimension or 2048
            
            if max(enhanced.size) > max_dim:
                ratio = max_dim / max(enhanced.size)
                new_size = tuple(int(dim * ratio) for dim in enhanced.size)
                print(f"Resizing image from {enhanced.size} to {new_size}")
                enhanced = enhanced.resize(new_size, Image.Resampling.LANCZOS)
                enhanced = self.enhance_image_for_ocr(enhanced, custom_contrast=2.0, custom_sharpness=2.5)
            
            return enhanced
        except Exception as e:
            print(f"[ERROR] Error preparing full image: {e}")
            return image
    
    def validate_image(self, image: Image.Image) -> bool:
        """Check image validity before processing."""
        try:
            if not image or not hasattr(image, 'size'):
                return False
            w, h = image.size
            if w < 10 or h < 10:
                print(f"[WARNING] Image too small: {w}x{h}")
                return False
            if w > 50000 or h > 50000:
                print(f"[WARNING] Image too large: {w}x{h}")
                return False
            return True
        except Exception as e:
            print(f"[ERROR] Error validating image: {e}")
            return False
    
    def detect_booths(self, 
                     input_source: Union[str, Image.Image], 
                     output_dir: str,
                     page: int = 0,
                     dpi: int = 300,
                     save_individual_detections: bool = True) -> List[str]:
        """
        Detect booths from PDF or Image input and save cropped booth images.
        
        Args:
            input_source: Either a PDF file path (str) or PIL Image
            output_dir: Directory to save booth images
            page: Page number if input is PDF (0-indexed)
            dpi: Resolution for PDF conversion
            save_individual_detections: If True, saves each OpenCV detection for human inspection
            
        Returns:
            List of saved file paths
        """
        # Handle input - PDF or Image
        if isinstance(input_source, str):
            # It's a file path
            if input_source.lower().endswith('.pdf'):
                print(f"[INFO] Processing PDF: {input_source}")
                image = self.convert_pdf_to_image(input_source, dpi=dpi, page=page)
            else:
                # Assume it's an image file
                print(f"[INFO] Processing image file: {input_source}")
                image = Image.open(input_source)
        elif isinstance(input_source, Image.Image):
            # It's already a PIL Image
            print("[INFO] Processing PIL Image")
            image = input_source
        else:
            raise ValueError("input_source must be either a file path (str) or PIL Image")
        
        if not self.validate_image(image):
            raise ValueError("Invalid image provided")
        
        print("[INFO] Detecting booths using working slice_floorplan method...")
        
        # Set up individual detections directory
        individual_dir = None
        if save_individual_detections:
            individual_dir = os.path.join(output_dir, "individual_detections")
        
        results = detect_stalls(
            image, 
            debug=True, 
            save_individual_detections=save_individual_detections,
            individual_output_dir=individual_dir
        )
        
        if not results:
            print("[WARN] No booths detected")
            return []
        
        # Save results
        os.makedirs(output_dir, exist_ok=True)
        saved_files = []
        
        count = 0
        for res in results:
            if "image" not in res:
                continue
            
            booth_img = res["image"]
            count += 1
            filename = os.path.join(output_dir, f"booth_{count}.png")
            booth_img.save(filename)
            saved_files.append(filename)

        # Save debug visualization
        for res in results:
            if "debug_image" in res:
                dbg_path = os.path.join(output_dir, "debug_detected.png")
                res["debug_image"].save(dbg_path)
                print(f"[DEBUG] Saved visualization: {dbg_path}")

        print(f"\n✅ Success! Saved {count} booth images to '{output_dir}' folder.")
        return saved_files
    
    def get_processing_strategy(self, image: Image.Image) -> Dict[str, Any]:
        """Return recommended processing strategy."""
        if not self.validate_image(image):
            raise ValueError("Invalid image provided")
        
        w, h = image.size
        total_pixels = w * h
        aspect_ratio = w / h
        
        strategy = {
            'use_tiling': False,  # Added back for compatibility
            'suggested_grid': (1, 1),  # Added back for compatibility
            'enhancement_level': 'high' if total_pixels < 1_000_000 else 'medium',
            'resize_needed': max(w, h) > 2048,
            'aspect_ratio': aspect_ratio,
            'complexity_score': min(100, total_pixels / 100_000),
            'recommended_dpi': 300 if total_pixels < 5_000_000 else 200
        }
        return strategy


# Example usage showing flexible input handling
if __name__ == "__main__":
    processor = ImageProcessor()
    
    # Example 1: Process a specific PDF
    pdf_path = input("Enter PDF file path: ").strip()
    output_dir = input("Enter output directory (or press Enter for 'booth_output'): ").strip()
    if not output_dir:
        output_dir = "booth_output"
    
    try:
        if os.path.exists(pdf_path):
            saved_files = processor.detect_booths(pdf_path, output_dir)
            print(f"\nProcessed and saved {len(saved_files)} booth images.")
        else:
            print(f"Error: File '{pdf_path}' not found.")
    except Exception as e:
        print(f"Error processing file: {e}")
    
    