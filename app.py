from flask import Flask
import os
import pillow_heif
from extract_info import extract_information
from merge_info import merge_extracted_data
from llm_utils import get_model
from prompt import get_prompt
from pathlib import Path
from PIL import Image
from flask import request, jsonify
from werkzeug.utils import secure_filename
from flask import render_template
from datetime import datetime

pillow_heif.register_heif_opener()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'upload_image'

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'heic'}

def allowed_file(filename):
    # Check if the file extension is allowed
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def take_image_input(image1, image2=None):
    # Take image input from the user
    image_paths = []
    if image1:
        image_paths.append(image1)
    if image2:
        image_paths.append(image2)
    return image_paths
    
def validate_image_paths(image_paths):
    # Validate the image paths
    for img_path in image_paths:
        path = Path(img_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {img_path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {img_path}")
    return image_paths

def load_llm_prompt():
    # Load the LLM model and prompt
    model = get_model()
    prompt = get_prompt()
    return model, prompt

def generate_response(image_paths):
    # Call LLM API with images and prompt to get response text
    # Validate image paths
    validate_image_paths(image_paths)
    
    # Load images
    images = []
    for img_path in image_paths:
        images.append(Image.open(img_path))
    
    # Get model and prompt
    model, prompt = load_llm_prompt()
    
    # Prepare content for model
    content = [prompt] + images
    
    # Call LLM API
    response = model.generate_content(content)
    response_text = response.text.strip()
    
    return response_text

def is_empty_extraction(extracted_data):
    # Check if extracted data contains no meaningful visiting card information
    # Key fields that indicate a visiting card
    key_fields = [
        'company_name',
        'person_name',
        'contact_numbers',
        'email_addresses',
        'address',
        'website',
        'services',
        'category'
    ]
    
    # Check if all key fields are None or empty
    for field in key_fields:
        value = extracted_data.get(field)
        if value is not None:
            # Check if it's a list/array with non-empty items
            if isinstance(value, list):
                if any(item for item in value if item):
                    return False
            # Check if it's a string with content
            elif isinstance(value, str) and value.strip():
                return False
            # Check if it's a dict (like social_media_profiles)
            elif isinstance(value, dict):
                if any(v for v in value.values() if v):
                    return False
    
    # Also check social_media_profiles separately
    social_media = extracted_data.get('social_media_profiles', {}) or {}
    if social_media:
        for platform, profiles in social_media.items():
            if profiles:
                if isinstance(profiles, list) and any(p for p in profiles if p):
                    return False
                elif isinstance(profiles, str) and profiles.strip():
                    return False
    
    # If all key fields are empty, it's likely not a visiting card
    return True

def process_images(image_paths):
    # Process one or two images to extract and merge information
    if len(image_paths) == 2:
        # Extract information from both images separately
        response_text1 = generate_response([image_paths[0]])
        response_text2 = generate_response([image_paths[1]])
        
        data_image1 = extract_information(response_text1)
        data_image2 = extract_information(response_text2)
        
        # Merge information from both images
        merged_data = merge_extracted_data(data_image1, data_image2)
        return merged_data
    elif len(image_paths) == 1:
        # Extract information from single image
        response_text = generate_response(image_paths)
        return extract_information(response_text)
    else:
        raise ValueError("Invalid number of images. Expected 1 or 2 images.")

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
            
            # Add timestamp to filename to prevent overwriting
            original_filename = secure_filename(file.filename)
            name, ext = os.path.splitext(original_filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"{name}_{timestamp}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            image_paths.append(filepath)
        
        # Process images - extract and merge information from both images if provided
        warning_message = None
        
        # If two images, extract separately first to compare company names
        if len(image_paths) == 2:
            from extract_info import extract_information
            from merge_info import merge_extracted_data
            
            # Extract information from both images separately
            response_text1 = generate_response([image_paths[0]])
            response_text2 = generate_response([image_paths[1]])
            
            image1 = extract_information(response_text1)
            image2 = extract_information(response_text2)
            
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
            # Process single image
            extracted_data = process_images(image_paths)
        
        # Check if no information was extracted (image might not be a visiting card)
        if is_empty_extraction(extracted_data):
            empty_warning = "Warning: No visiting card information was extracted from the image(s). The uploaded image(s) may not be a visiting card."
            if warning_message:
                warning_message = f"{warning_message} Additionally, {empty_warning}"
            else:
                warning_message = empty_warning
        
        # Images are stored in upload_image folder and not deleted
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

