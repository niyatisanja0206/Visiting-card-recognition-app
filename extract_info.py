import json
import sys
from info_utils import normalize_field, normalize_social_media

def extract_information(response_text):
    """
    Extract and normalize information from LLM response.
    
    Args:
        response_text: Raw response text from LLM
    
    Returns:
        Normalized extracted data dict
    
    Raises:
        json.JSONDecodeError: If response contains invalid JSON
    """
    # Clean the response to extract JSON
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    try:
        extracted_data = json.loads(response_text)
        
        # List fields to normalize to arrays
        list_fields = [
            'company_name', 'person_name', 'contact_numbers',
            'email_addresses', 'services', 'website', 'address'
        ]
        
        for field in list_fields:
            extracted_data[field] = normalize_field(
                extracted_data.get(field),
                return_type='list'
            )
        
        # Handle company_quote (always set to None as per spec)
        extracted_data['company_quote'] = None
        
        # Normalize category to single string
        extracted_data['category'] = normalize_field(
            extracted_data.get('category'),
            return_type='string'
        )
        
        # Normalize social media profiles
        social_media = extracted_data.get('social_media_profiles')
        extracted_data['social_media_profiles'] = normalize_social_media(social_media)
        
        return extracted_data
    
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON response: {e}", file=sys.stderr)
        print(f"Raw response: {response_text}", file=sys.stderr)
        raise
