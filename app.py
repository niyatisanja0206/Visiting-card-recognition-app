from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from pathlib import Path
from PIL import Image
import json
import sys
from llm_utils import get_model
import pillow_heif

pillow_heif.register_heif_opener()


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'upload_image'

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def merge_extracted_data(image1, image2):
    """
    Merge extracted data from two images, combining arrays and keeping non-null values.
    
    Args:
        image1: First extracted data dict
        image2: Second extracted data dict
    
    Returns:
        dict: Merged extracted data
    """
    merged = {}
    
    # Handle company names - normalize to arrays and merge them
    company1 = image1.get('company_name')
    company2 = image2.get('company_name')
    quote1 = image1.get('company_quote')
    quote2 = image2.get('company_quote')
    
    # Normalize company names to lists
    companies1 = []
    companies2 = []
    
    if company1:
        if isinstance(company1, list):
            companies1 = [str(c).strip() for c in company1 if c]
        elif isinstance(company1, str):
            companies1 = [company1.strip()]
    
    if company2:
        if isinstance(company2, list):
            companies2 = [str(c).strip() for c in company2 if c]
        elif isinstance(company2, str):
            companies2 = [company2.strip()]
    
    # Handle separate quotes (for backward compatibility)
    if quote1 and companies1:
        # Check if quote is already in the first company name
        if quote1 not in companies1[0]:
            companies1[0] = f"{companies1[0]}\n{quote1}".strip()
    elif quote1 and not companies1:
        companies1 = [quote1.strip()]
    
    if quote2 and companies2:
        # Check if quote is already in the first company name
        if quote2 not in companies2[0]:
            companies2[0] = f"{companies2[0]}\n{quote2}".strip()
    elif quote2 and not companies2:
        companies2 = [quote2.strip()]
    
    # Combine both lists and remove duplicates
    all_companies = companies1 + companies2
    seen = set()
    merged_companies = []
    for company in all_companies:
        # Use a normalized version (lowercase, stripped) for comparison
        company_normalized = company.lower().strip()
        if company_normalized and company_normalized not in seen:
            seen.add(company_normalized)
            merged_companies.append(company)
    
    merged['company_name'] = merged_companies if merged_companies else None
    merged['company_quote'] = None  # Always set to None since it's merged into company_name
    
    # Handle person names - normalize to arrays and merge them
    person1 = image1.get('person_name')
    person2 = image2.get('person_name')
    
    # Normalize person names to lists
    persons1 = []
    persons2 = []
    
    if person1:
        if isinstance(person1, list):
            persons1 = [str(p).strip() for p in person1 if p]
        elif isinstance(person1, str):
            persons1 = [person1.strip()]
    
    if person2:
        if isinstance(person2, list):
            persons2 = [str(p).strip() for p in person2 if p]
        elif isinstance(person2, str):
            persons2 = [person2.strip()]
    
    # Combine both lists and remove duplicates
    all_persons = persons1 + persons2
    seen = set()
    merged_persons = []
    for person in all_persons:
        # Use a normalized version (lowercase, stripped) for comparison
        person_normalized = person.lower().strip()
        if person_normalized and person_normalized not in seen:
            seen.add(person_normalized)
            merged_persons.append(person)
    
    merged['person_name'] = merged_persons if merged_persons else None
    
    # Simple fields - prefer non-null, or image1 if both are non-null
    simple_fields = ['address', 'website', 'category']
    for field in simple_fields:
        merged[field] = image1.get(field) or image2.get(field) or None
    
    # Array fields - combine and remove duplicates
    array_fields = ['contact_numbers', 'email_addresses', 'services']
    for field in array_fields:
        combined = []
        if image1.get(field):
            combined.extend(image1[field])
        if image2.get(field):
            combined.extend(image2[field])
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in combined:
            if item and item.lower() not in seen:
                seen.add(item.lower())
                unique.append(item)
        merged[field] = unique if unique else None
    
    # Social media profiles - merge objects
    social1 = image1.get('social_media_profiles', {}) or {}
    social2 = image2.get('social_media_profiles', {}) or {}
    merged_social = {}
    
    # Merge individual platforms
    platforms = ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']
    for platform in platforms:
        merged_social[platform] = social1.get(platform) or social2.get(platform) or None
    
    # Merge 'other' arrays
    other_list = []
    if social1.get('other'):
        other_list.extend(social1['other'])
    if social2.get('other'):
        other_list.extend(social2['other'])
    # Remove duplicates
    seen_other = set()
    unique_other = []
    for item in other_list:
        if item and item.lower() not in seen_other:
            seen_other.add(item.lower())
            unique_other.append(item)
    merged_social['other'] = unique_other if unique_other else []
    
    merged['social_media_profiles'] = merged_social
    
    return merged

def extract_information(image_paths):
    """
    Extract information from visiting card image(s).
    
    Args:
        image_paths: List of image file paths (1 or 2 images)
    
    Returns:
        dict: Extracted information as JSON
    """
    # Validate image paths
    images = []
    for img_path in image_paths:
        path = Path(img_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {img_path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {img_path}")
        images.append(Image.open(path))
    
    model = get_model()
    
    # Create extraction prompt
    extraction_prompt = """Extract all the following information from this visiting card image(s). Return ONLY a valid JSON object with the following structure. Do not include any additional text, explanations, or markdown formatting - ONLY the JSON object.

{
  "company_name": ["company name 1 with its quote/subtitle", "company name 2 with its quote/subtitle"] or "single company name with quote/subtitle" or null,
  "company_quote": null,
  "person_name": ["person name 1", "person name 2"] or "single person name" or null,
  "contact_numbers": ["phone number 1", "phone number 2"],
  "social_media_profiles": {
    "facebook": "URL or null",
    "instagram": "URL or null",
    "linkedin": "URL or null",
    "twitter": "URL or null",
    "youtube": "URL or null",
    "other": ["any other social media URLs"]
  },
  "address": "full address or null",
  "services": ["service 1", "service 2"],
  "website": "website URL or null",
  "email_addresses": ["email1@example.com", "email2@example.com"],
  "category": "business category (e.g., Healthcare, Technology, Education, etc.) or null"
}

Important:
- If information is not available, use null (not empty string)
- Extract ALL phone numbers, emails, and social media links you can find - there is NO LIMIT on the number of items
- For company_name: A visiting card can have ONE OR MORE (any number of) company names. Extract ALL company names found on the card. Return an array where each element is a string containing "Company Name\\nQuote/Subtitle" (combine the company name with its associated quote, tagline, subtitle, or slogan on the same line, separated by \\n). If there is only one company name, you can return either a string or an array with one element. ALWAYS include any quote, tagline, subtitle, or slogan that appears with each company name - combine them together in the format "Company Name\\nQuote". Extract EVERY company name you see, no matter how many there are.
- For company_quote: Always set this to null (quotes are now included in company_name)
- For person_name: A visiting card can have ONE OR MORE (any number of) person names. Extract ALL person names found on the card. Return an array where each element is a string containing the person's name. If there is only one person name, you can return either a string or an array with one element. Extract EVERY person name you see, no matter how many there are.
- For social_media_profiles.other: Extract ALL social media URLs that don't fit into the standard platforms (facebook, instagram, linkedin, twitter, youtube). There can be N number of other social media profiles. Return an array with ALL other social media URLs found on the card.
- For category, determine the business type based on the services/company name. 
- No need to give to much specific category you can give general category like Healthcare, Technology, Education, Mechine-tools industries or others.
- Return ONLY the JSON object, nothing else"""

    # Prepare content for model
    content = [extraction_prompt] + images
    
    # Generate response
    response = model.generate_content(content)
    response_text = response.text.strip()
    
    # Clean the response to extract JSON
    # Remove markdown code blocks if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    # Parse JSON
    try:
        extracted_data = json.loads(response_text)
        
        # Normalize company_name to always be an array
        company_name = extracted_data.get('company_name')
        company_quote = extracted_data.get('company_quote')
        
        company_names_list = []
        
        if company_name:
            # If company_name is already an array
            if isinstance(company_name, list):
                company_names_list = [str(name).strip() for name in company_name if name]
            # If company_name is a string
            elif isinstance(company_name, str):
                company_names_list = [company_name.strip()]
            
            # If there's a separate company_quote, combine it with the first company name
            if company_quote and company_names_list:
                # Check if quote is already in the company name
                first_company = company_names_list[0]
                if company_quote not in first_company:
                    company_names_list[0] = f"{first_company}\n{company_quote}".strip()
        elif company_quote:
            # If only quote exists, use it as company name
            company_names_list = [company_quote.strip()]
        
        # Set company_name as array (empty array if null, or None if empty)
        if company_names_list:
            extracted_data['company_name'] = company_names_list
        else:
            extracted_data['company_name'] = None
        
        # Always set company_quote to None since it's merged into company_name
        extracted_data['company_quote'] = None
        
        # Normalize person_name to always be an array
        person_name = extracted_data.get('person_name')
        person_names_list = []
        
        if person_name:
            # If person_name is already an array
            if isinstance(person_name, list):
                person_names_list = [str(name).strip() for name in person_name if name]
            # If person_name is a string
            elif isinstance(person_name, str):
                person_names_list = [person_name.strip()]
        
        # Set person_name as array (empty array if null, or None if empty)
        if person_names_list:
            extracted_data['person_name'] = person_names_list
        else:
            extracted_data['person_name'] = None
        
        return extracted_data
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON response: {e}", file=sys.stderr)
        print(f"Raw response: {response_text}", file=sys.stderr)
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        # Check if files were uploaded
        if 'images' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400
        
        files = request.files.getlist('images')
        
        # Filter out empty files
        files = [f for f in files if f.filename != '']
        
        if not files:
            return jsonify({'error': 'No files selected'}), 400
        
        # Validate number of files
        if len(files) > 2:
            return jsonify({'error': 'Maximum 2 images are supported'}), 400
        
        # Validate and save files
        image_paths = []
        for file in files:
            if not allowed_file(file.filename):
                return jsonify({'error': f'Invalid file type: {file.filename}. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_paths.append(filepath)
        
        # Extract information
        warning_message = None
        
        # If two images, extract separately and compare company names
        if len(image_paths) == 2:
            image1 = extract_information([image_paths[0]])
            image2 = extract_information([image_paths[1]])
            
            # Compare company names
            company1 = image1.get('company_name')
            company2 = image2.get('company_name')
            
            # Normalize to lists for comparison
            companies1_list = []
            companies2_list = []
            
            if company1:
                if isinstance(company1, list):
                    companies1_list = [str(c).lower().strip() for c in company1 if c]
                elif isinstance(company1, str):
                    companies1_list = [company1.lower().strip()]
            
            if company2:
                if isinstance(company2, list):
                    companies2_list = [str(c).lower().strip() for c in company2 if c]
                elif isinstance(company2, str):
                    companies2_list = [company2.lower().strip()]
            
            # Check if there are any common company names
            if companies1_list and companies2_list:
                common_companies = set(companies1_list) & set(companies2_list)
                if not common_companies:
                    # No common company names found
                    companies1_str = ', '.join([c.split('\n')[0] for c in companies1_list])  # Get just the name part
                    companies2_str = ', '.join([c.split('\n')[0] for c in companies2_list])
                    warning_message = f"Warning: Different company names were detected (Image 1: '{companies1_str}' and Image 2: '{companies2_str}'). It's possible you have uploaded cards for two different companies, not the front and back side of the same card. So you may have to extract the information from both the cards combined and the information given is not correct."
            
            # Merge data from both images
            extracted_data = merge_extracted_data(image1, image2)
        else:
            extracted_data = extract_information(image_paths)
        
        # Clean up uploaded files
        for filepath in image_paths:
            try:
                os.remove(filepath)
            except:
                pass
        
        response = {
            'success': True,
            'data': extracted_data
        }
        
        if warning_message:
            response['warning'] = warning_message
        
        return jsonify(response)
    
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Failed to parse response: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
