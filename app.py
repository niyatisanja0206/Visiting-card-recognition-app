from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from pathlib import Path
from PIL import Image
import json
import sys
from llm_utils import get_model

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def merge_extracted_data(data1, data2):
    """
    Merge extracted data from two images, combining arrays and keeping non-null values.
    
    Args:
        data1: First extracted data dict
        data2: Second extracted data dict
    
    Returns:
        dict: Merged extracted data
    """
    merged = {}
    
    # Simple fields - prefer non-null, or data1 if both are non-null
    simple_fields = ['company_name', 'person_name', 'address', 'website', 'category']
    for field in simple_fields:
        merged[field] = data1.get(field) or data2.get(field) or None
    
    # Array fields - combine and remove duplicates
    array_fields = ['contact_numbers', 'email_addresses', 'services']
    for field in array_fields:
        combined = []
        if data1.get(field):
            combined.extend(data1[field])
        if data2.get(field):
            combined.extend(data2[field])
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in combined:
            if item and item.lower() not in seen:
                seen.add(item.lower())
                unique.append(item)
        merged[field] = unique if unique else None
    
    # Social media profiles - merge objects
    social1 = data1.get('social_media_profiles', {}) or {}
    social2 = data2.get('social_media_profiles', {}) or {}
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
  "company_name": "extracted company name or null",
  "person_name": "extracted person name or null",
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
- Extract all phone numbers, emails, and social media links you can find
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
            data1 = extract_information([image_paths[0]])
            data2 = extract_information([image_paths[1]])
            
            # Compare company names
            company1 = data1.get('company_name')
            company2 = data2.get('company_name')
            
            if company1 and company2 and company1.lower().strip() != company2.lower().strip():
                warning_message = f"Warning: Two different company names were detected ('{company1}' and '{company2}'). It's possible you have uploaded cards for two different companies, not the front and back side of the same card. So you may have to extract the information from both the cards combined and the information given is not correct."
            
            # Merge data from both images
            extracted_data = merge_extracted_data(data1, data2)
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
