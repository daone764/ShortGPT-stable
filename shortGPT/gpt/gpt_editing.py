from shortGPT.gpt import gpt_utils
import json
import re

def extractJsonFromString(text):
    start = text.find('{') 
    end = text.rfind('}') + 1
    if start == -1 or end == 0:
        raise Exception("Error: No JSON object found in response")
    json_str = text[start:end]
    return json.loads(json_str)


def getImageQueryPairs(captions, n=15, maxTime=2):
    chat, _ = gpt_utils.load_local_yaml_prompt('prompt_templates/editing_generate_images.yaml')
    prompt = chat.replace('<<CAPTIONS TIMED>>', f"{captions}").replace("<<NUMBER>>", f"{n}")
    
    # Calculate end time from captions to include in prompt
    end_audio = captions[-1][0][1]
    prompt = prompt.replace("<<DURATION>>", f"{end_audio}")
    
    try:
        # Extract main subject from captions for validation
        all_text = " ".join([text for _, text in captions])
        main_subject = extract_main_subject(all_text)
        
        # Get response and parse JSON
        res = gpt_utils.llm_completion(chat_prompt=prompt)
        print(f"[DEBUG] Raw image query response: {res}")
        data = extractJsonFromString(res)
        
        # Validate and fix queries if needed
        validated_queries = []
        for item in data["image_queries"]:
            query = item["query"]
            timestamp = item["timestamp"]
            
            # Fix queries that don't include main subject
            if main_subject and main_subject not in query.lower() and is_generic_term(query):
                print(f"[WARNING] Generic query '{query}' detected, adding main subject '{main_subject}'")
                query = f"{main_subject} {query}"
                
            # Avoid numeric-only queries
            if is_mostly_numeric(query):
                print(f"[WARNING] Numeric query '{query}' detected, replacing with '{main_subject}'")
                query = main_subject
                
            validated_queries.append({"timestamp": timestamp, "query": query})
            
        data["image_queries"] = validated_queries
        
        # Convert to pairs with time ranges
        pairs = []
        
        for i, item in enumerate(data["image_queries"]):
            time = item["timestamp"]
            query = item["query"]
            
            # Skip invalid timestamps
            if time <= 0 or time >= end_audio:
                print(f"[WARNING] Invalid timestamp {time} for query '{query}', adjusting...")
                time = min(max(1.0, time), end_audio - 1)
                
            # Calculate end time for this image
            if i < len(data["image_queries"]) - 1:
                next_time = data["image_queries"][i + 1]["timestamp"]
                end = min(time + maxTime, next_time)
            else:
                end = min(time + maxTime, end_audio)
                
            print(f"[DEBUG] Adding image query: '{query}' at time {time}-{end}")
            pairs.append(((time, end), query + " image"))
            
        return pairs
        
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from LLM")
        return []
    except KeyError:
        print("Error: Malformed JSON structure")
        return []
    except Exception as e:
        print(f"Error processing image queries: {str(e)}")
        return []

def getVideoSearchQueriesTimed(captions_timed):
    """
    Generate timed video search queries based on caption timings.
    Returns list of [time_range, search_queries] pairs.
    """
    err = ""

    for _ in range(4):
        try:
            # Get total video duration from last caption
            end_time = captions_timed[-1][0][1]
            
            # Load and prepare prompt
            chat, system = gpt_utils.load_local_yaml_prompt('prompt_templates/editing_generate_videos.yaml')
            prompt = chat.replace("<<TIMED_CAPTIONS>>", f"{captions_timed}")
            
            # Get response and parse JSON
            res = gpt_utils.llm_completion(chat_prompt=prompt, system=system)
            data = extractJsonFromString(res)
            
            # Convert to expected format
            formatted_queries = []
            for segment in data["video_segments"]:
                time_range = segment["time_range"]
                queries = segment["queries"]
                
                # Validate time range
                if not (0 <= time_range[0] < time_range[1] <= end_time):
                    continue
                    
                # Ensure exactly 3 queries
                while len(queries) < 3:
                    queries.append(queries[-1])
                queries = queries[:3]
                
                formatted_queries.append([time_range, queries])
                
            # Verify coverage
            if not formatted_queries:
                raise ValueError("Generated segments don't cover full video duration")
                
            return formatted_queries
        except Exception as e:
            err = str(e)
            print(f"Error generating video search queries {err}")
    raise Exception(f"Failed to generate video search queries {err}")

def extract_main_subject(text):
    """Extract the main subject from the transcript text."""
    # Look for common patterns in fact videos
    patterns = [
        r"facts about the ([\w\s]+)!",
        r"about the ([\w\s]+)!",
        r"^--- ([\w\s]+)!",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
    
    # Fallback: look for repeated terms
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    word_counts = {}
    for word in words:
        if word.lower() not in ['the', 'and', 'that', 'this', 'with', 'from']:
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # Get most common proper noun
    if word_counts:
        most_common = max(word_counts.items(), key=lambda x: x[1])[0]
        return most_common.lower()
    
    return None

def is_generic_term(query):
    """Check if a query is too generic."""
    generic_terms = [
        'car', 'vehicle', 'automobile', 'sedan', 'luxury', 
        'warranty', 'audio', 'system', 'years', 'miles'
    ]
    
    query_terms = query.lower().split()
    for term in query_terms:
        if term in generic_terms:
            return True
    return False

def is_mostly_numeric(query):
    """Check if a query is mostly numbers."""
    numeric_chars = sum(c.isdigit() for c in query)
    return numeric_chars > (len(query) * 0.4)  # If >40% is digits