import json
import requests
import re
import urllib.parse

from urllib3 import Retry

def _extractBingImages(html):
    pattern = r'mediaurl=(.*?)&amp;.*?expw=(\d+).*?exph=(\d+)'
    matches = re.findall(pattern, html)
    result = []

    for match in matches:
        url, width, height = match
        if url.endswith('.jpg') or url.endswith('.png') or url.endswith('.jpeg'):
            result.append({'url': urllib.parse.unquote(url), 'width': int(width), 'height': int(height)})

    return result


def _extractGoogleImages(html):
  images = []
  regex = re.compile(r"AF_initDataCallback\({key: 'ds:1', hash: '2', data:(.*?), sideChannel: {}}\);")
  match = regex.search(html)
  if match:
      dz = json.loads(match.group(1))         
      for c in dz[56][1][0][0][1][0]:
          try:
              thing = list(c[0][0].values())[0]
              images.append(thing[1][3])
          except:
              pass
  return images

import urllib.parse
from requests.adapters import HTTPAdapter

def getBingImages(query, retries=5):
    query = query.replace(" ", "+")
    images = []
    tries = 0
    
    # Create a session with custom retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    
    while(len(images) == 0 and tries < retries):
        try:
            # Use verify=False to bypass SSL verification (use with caution)
            response = session.get(
                f"https://www.bing.com/images/search?q={query}&first=1",
                verify=False,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            if(response.status_code == 200):
                images = _extractBingImages(response.text)
            else:
                print("Error While making bing image searches", response.text)
                raise Exception("Error While making bing image searches")
        except requests.exceptions.SSLError as e:
            print(f"SSL Error occurred (attempt {tries + 1}/{retries}): {str(e)}")
            tries += 1
            if tries >= retries:
                raise Exception("Max retries reached - SSL Error while making Bing image searches")
            continue
        
    if(images):
        return images
    raise Exception("Error While making bing image searches")

def getBingImages(search_term, count=10, filter='', subscription_key=None):
    """Get images from Bing Image Search API."""
    if not subscription_key:
        subscription_key = ApiKeyManager.get_api_key("BING_API_KEY")
    
    # For car models, ensure proper formatting and add keywords
    lower_term = search_term.lower()
    if "genesis" in lower_term and "hyundai" not in lower_term:
        search_term = f"Hyundai {search_term}"
    
    if any(car_term in lower_term for car_term in ["car", "genesis", "hyundai", "bmw", "ferrari"]):
        search_term = f"{search_term} car photo"
    
    # Don't search for just numbers
    if search_term.strip().isdigit() or (search_term.strip().replace(',', '').isdigit()):
        search_term = "Hyundai Genesis car"
    
    # Remove the word "image" if it exists (since we're already searching for images)
    search_term = search_term.replace(" image", "").strip()
    
    print(f"[INFO] Searching Bing Images for: '{search_term}'")
    
    # Make API request