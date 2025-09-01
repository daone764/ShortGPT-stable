from shortGPT.api_utils.image_api import getBingImages
from tqdm import tqdm
import random
import math

def getImageUrlsTimed(imageTextPairs):
    results = []
    for pair in tqdm(imageTextPairs, desc='Search engine queries for images...'):
        timing, query = pair
        image_url = searchImageUrlsFromQuery(query)
        # Retry with alternative query if image_url is None
        if not image_url:
            alt_query = query.replace(' image', '').replace('person', 'object')
            image_url = searchImageUrlsFromQuery(alt_query)
        results.append((timing, image_url))
    return results



def searchImageUrlsFromQuery(query, top=3, expected_dim=[720,720], retries=5):
    """Search for image URLs based on a given query."""
    # Add car-specific handling
    if "genesis" in query.lower() and "hyundai" not in query.lower():
        query = f"Hyundai {query}"
    
    # Add more context for better image search
    if query.lower() in ["warranty", "years", "miles"]:
        query = f"Hyundai warranty badge"
    
    # For specific numeric values like "10 years"
    if any(str(num) in query for num in range(10, 101)) and len(query.split()) <= 2:
        query = f"Hyundai warranty {query}"
    
    print(f"[INFO] Searching for image: '{query}'")
    
    # Retry loop for better robustness
    for attempt in range(retries):
        try:
            from shortGPT.api_utils.image_api import getBingImages
            images = getBingImages(query, count=top)
            if images and len(images) > 0:
                # Sort by aspect ratio to find best match
                min_diff = float('inf')
                best_image = None
                
                for img in images:
                    width = img['width']
                    height = img['height']
                    if width == 0 or height == 0:
                        continue
                        
                    diff = abs(width/height - expected_dim[0]/expected_dim[1])
                    if diff < min_diff:
                        min_diff = diff
                        best_image = img
                
                if best_image:
                    print(f"[SUCCESS] Found image for '{query}'")
                    return best_image['url']
            
            # If we get here, we didn't find a good image
            if attempt < retries - 1:
                # Try with simpler query on next attempt
                if " " in query:
                    terms = query.split()
                    query = " ".join(terms[:2])  # Keep only first two terms
                    print(f"[INFO] Retrying with simplified query: '{query}'")
                    
        except Exception as e:
            print(f"[ERROR] Image search failed: {str(e)}")
            if attempt < retries - 1:
                print(f"[INFO] Retrying... (attempt {attempt+2}/{retries})")
    
    print(f"[WARNING] Could not find suitable image for '{query}' after {retries} attempts")
    return None