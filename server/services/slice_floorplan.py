import cv2
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from typing import List, Dict, Any

# --- Parameters for Tuning ---
NUM_CLUSTERS = 60
MIN_STALL_AREA = 1500
MAX_STALL_AREA = 500000
PADDING = 30


def detect_stalls(image: Image.Image,
                  num_clusters: int = NUM_CLUSTERS,
                  min_area: int = MIN_STALL_AREA,
                  max_area: int = MAX_STALL_AREA,
                  padding: int = PADDING,
                  debug: bool = False,
                  save_individual_detections: bool = False,
                  individual_output_dir: str = None) -> List[Dict[str, Any]]:
    """
    Detect rectangular stalls from a floorplan image using the WORKING method.

    Args:
        image: Input PIL image of the floorplan
        num_clusters: Number of groups for clustering stalls
        min_area: Minimum contour area to be considered a stall
        max_area: Maximum contour area filter
        padding: Padding around cropped stalls
        debug: If True, include a debug image in results
        save_individual_detections: If True, save each detected rectangle as separate image
        individual_output_dir: Directory to save individual detections (required if save_individual_detections=True)

    Returns:
        List of dicts containing cropped stall images and metadata
    """
    print("Starting precision stall detection...")
    
    # Convert PIL image to OpenCV format - EXACTLY like working version
    open_cv_image = np.array(image)
    open_cv_image = open_cv_image[:, :, ::-1].copy()

    # Preprocess image - EXACT working parameters
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Find contours - exact working method
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    all_boxes = []
    for cnt in contours:
        perimeter = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * perimeter, True)

        # Accept only quadrilaterals - EXACT working logic
        if len(approx) == 4:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                all_boxes.append(cv2.boundingRect(cnt))

    if not all_boxes:
        print("[WARN] No stalls detected")
        return []

    print(f"Detection complete. Found {len(all_boxes)} rectangular stalls.")

    # 🆕 SAVE INDIVIDUAL DETECTIONS FOR HUMAN INSPECTION
    if save_individual_detections:
        if individual_output_dir is None:
            raise ValueError("individual_output_dir must be provided when save_individual_detections=True")
        
        import os
        os.makedirs(individual_output_dir, exist_ok=True)
        print(f"💾 Saving {len(all_boxes)} individual detections to {individual_output_dir}")
        
        for idx, (x, y, w, h) in enumerate(all_boxes):
            # Crop individual detection with padding
            left = max(0, x - padding)
            upper = max(0, y - padding)
            right = min(image.size[0], x + w + padding)
            lower = min(image.size[1], y + h + padding)
            
            individual_crop = image.crop((left, upper, right, lower))
            
            # Save with detailed filename including area and dimensions
            area = w * h
            filename = f"detection_{idx+1:03d}_area{area}_size{w}x{h}.png"
            filepath = os.path.join(individual_output_dir, filename)
            individual_crop.save(filepath)
        
        print(f"✅ Saved {len(all_boxes)} individual detections for inspection")

    # Cluster by center points - exact working method
    stall_centers = np.array([(x + w / 2, y + h / 2) for x, y, w, h in all_boxes])
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(stall_centers)

    clusters = [[] for _ in range(num_clusters)]
    for i, box in enumerate(all_boxes):
        clusters[labels[i]].append(box)

    img_w, img_h = image.size
    results: List[Dict[str, Any]] = []

    for idx, cluster in enumerate(clusters):
        if not cluster:
            continue
            
        # Create bounding box - exact working method
        min_x = min(b[0] for b in cluster)
        min_y = min(b[1] for b in cluster)
        max_x = max(b[0] + b[2] for b in cluster)
        max_y = max(b[1] + b[3] for b in cluster)

        # Add padding - exact working method
        left = max(0, min_x - padding)
        upper = max(0, min_y - padding)
        right = min(img_w, max_x + padding)
        lower = min(img_h, max_y + padding)

        cropped = image.crop((left, upper, right, lower))

        results.append({
            "image": cropped,
            "cluster_index": idx,
            "coordinates": (left, upper, right, lower),
            "size": cropped.size
        })

        # At the end of detect_stalls, after you append each cluster result:
    if save_individual_detections and individual_output_dir:
        os.makedirs(individual_output_dir, exist_ok=True)
        for idx, res in enumerate(results):
            if "image" not in res:
                continue
            filename = f"cluster_{idx+1:03d}.png"
            filepath = os.path.join(individual_output_dir, filename)
            res["image"].save(filepath)


    # Debug visualization - exact working method
    if debug:
        dbg_img = open_cv_image.copy()
        for (x, y, w, h) in all_boxes:
            cv2.rectangle(dbg_img, (x, y), (x + w, y + h), (0, 255, 0), 3)
        dbg_pil = Image.fromarray(cv2.cvtColor(dbg_img, cv2.COLOR_BGR2RGB))
        results.append({"debug_image": dbg_pil})

    return results