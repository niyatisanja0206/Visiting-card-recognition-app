"""Flask app for visiting card OCR and data extraction"""

from flask import Flask, request, jsonify
import os
import boto3
from PIL import Image
from io import BytesIO
import json
from datetime import datetime
import pillow_heif

from extract_info import extract_information
from merge_info import merge_extracted_data
from llm_utils import get_model
from prompt import get_prompt
from utils import has_content

pillow_heif.register_heif_opener()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# ===== AWS S3 Configuration =====
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
S3_BUCKET = os.getenv('S3_BUCKET_NAME')

S3_CLIENT = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

if not S3_BUCKET:
    raise ValueError("S3_BUCKET_NAME environment variable is required")


# ===== S3 OPERATIONS =====

def download_image_from_s3(s3_url):
    """
    Download image from S3 URL and return PIL Image object.
    
    Args:
        s3_url: S3 URL (https://s3.amazonaws.com/bucket/key or https://bucket.s3.amazonaws.com/key)
    
    Returns:
        Tuple of (PIL Image object, bucket name, object key)
    
    Raises:
        ValueError: If URL is invalid or download fails
    """
    try:
        if "amazonaws.com" not in s3_url:
            raise ValueError(f"Invalid S3 URL: {s3_url}")
        
        # Extract bucket and key from URL
        if s3_url.startswith("https://s3"):
            # Format: https://s3.amazonaws.com/bucket-name/key
            parts = s3_url.replace("https://s3.amazonaws.com/", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]
        else:
            # Format: https://bucket-name.s3.amazonaws.com/key
            parts = s3_url.replace("https://", "").split(".s3.amazonaws.com/")
            bucket = parts[0]
            key = parts[1]
        
        # Get image from S3
        response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        image = Image.open(BytesIO(image_data))
        
        return image, bucket, key
    
    except Exception as e:
        raise ValueError(f"Failed to download image from S3: {str(e)}")


def upload_data_to_s3(data, bucket, key_prefix, data_type="extraction"):
    """
    Upload extracted data to S3 as JSON.
    
    Args:
        data: Data to upload (dict)
        bucket: S3 bucket name
        key_prefix: S3 key prefix (directory)
        data_type: Type of data being uploaded (for filename)
    
    Returns:
        S3 key where data was uploaded
    
    Raises:
        ValueError: If upload fails
    """
    try:
        # Generate S3 key for the data file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        data_key = f"{key_prefix}/{data_type}_{timestamp}.json"
        
        # Convert data to JSON
        json_data = json.dumps(data, indent=2)
        
        # Upload to S3
        S3_CLIENT.put_object(
            Bucket=bucket,
            Key=data_key,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        
        return data_key
    
    except Exception as e:
        raise ValueError(f"Failed to upload data to S3: {str(e)}")


# ===== LLM OPERATIONS =====

def load_llm_prompt():
    """Load the LLM model and prompt."""
    model = get_model()
    prompt = get_prompt()
    return model, prompt


def generate_response(images):
    """
    Call LLM API with images and prompt to get response text.
    
    Args:
        images: List of PIL Image objects
    
    Returns:
        Response text from LLM
    
    Raises:
        ValueError: If LLM call fails
    """
    try:
        # Get model and prompt
        model, prompt = load_llm_prompt()
        
        # Prepare content for model
        content = [prompt] + images
        
        # Call LLM API
        response = model.generate_content(content)
        response_text = response.text.strip()
        
        return response_text
    
    except Exception as e:
        raise ValueError(f"Failed to generate response from LLM: {str(e)}")


# ===== DATA VALIDATION =====

def is_empty_extraction(extracted_data):
    """
    Check if extracted data contains no meaningful visiting card information.
    
    Args:
        extracted_data: Extracted data dict
    
    Returns:
        True if no content found, False otherwise
    """
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
    
    # Check if any key field has content
    for field in key_fields:
        if has_content(extracted_data.get(field)):
            return False
    
    # Check social media profiles
    social_media = extracted_data.get('social_media_profiles', {})
    if has_content(social_media):
        return False
    
    # If all fields are empty, it's not a visiting card
    return True


# ===== IMAGE PROCESSING =====

def process_images(image_urls):
    """
    Process one or two images from S3 URLs to extract and merge information.
    
    Args:
        image_urls: List of 1-2 S3 URLs
    
    Returns:
        Tuple of (extracted data dict, S3 bucket, S3 key)
    
    Raises:
        ValueError: If processing fails
    """
    try:
        images = []
        s3_buckets = []
        s3_keys = []
        
        # Download images from S3
        for url in image_urls:
            image, bucket, key = download_image_from_s3(url)
            images.append(image)
            s3_buckets.append(bucket)
            s3_keys.append(key)
        
        if len(images) == 2:
            # Extract information from both images separately
            response_text1 = generate_response([images[0]])
            response_text2 = generate_response([images[1]])
            
            data_image1 = extract_information(response_text1)
            data_image2 = extract_information(response_text2)
            
            # Merge information from both images
            merged_data = merge_extracted_data(data_image1, data_image2)
            
            return merged_data, s3_buckets[0], s3_keys[0]
        
        elif len(images) == 1:
            # Extract information from single image
            response_text = generate_response(images)
            extracted_data = extract_information(response_text)
            
            return extracted_data, s3_buckets[0], s3_keys[0]
        
        else:
            raise ValueError("Invalid number of images. Expected 1 or 2 images.")
    
    except Exception as e:
        raise ValueError(f"Failed to process images: {str(e)}")


# ===== API ENDPOINTS =====

@app.route('/info', methods=['POST'])
def extract_info():
    """
    Extract information from visiting card images.
    
    Request body:
    {
        "image_urls": ["https://s3.amazonaws.com/bucket/image1.jpg"],
        "upload_results": true  # Optional: whether to upload results to S3
    }
    
    Response:
    {
        "success": true,
        "data": { ... },
        "s3_result_key": "...",
        "warning": "..." # Optional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        image_urls = data.get('image_urls')
        upload_results = data.get('upload_results', True)
        
        # Validate image URLs
        if not image_urls:
            return jsonify({'error': 'image_urls field is required'}), 400
        
        if not isinstance(image_urls, list):
            return jsonify({'error': 'image_urls must be an array'}), 400
        
        if len(image_urls) > 2:
            return jsonify({'error': 'Maximum 2 images are supported'}), 400
        
        if len(image_urls) == 0:
            return jsonify({'error': 'At least 1 image URL is required'}), 400
        
        # Process images
        extracted_data, bucket, key = process_images(image_urls)
        
        # Check if no information was extracted
        warning_message = None
        if is_empty_extraction(extracted_data):
            warning_message = "Warning: No visiting card information was extracted from the image(s). The uploaded image(s) may not be a visiting card."
        
        # Upload results to S3 if requested
        result_key = None
        if upload_results:
            try:
                # Get the directory from the image key
                key_prefix = '/'.join(key.split('/')[:-1]) if '/' in key else ''
                result_key = upload_data_to_s3(extracted_data, bucket, key_prefix, "extraction_result")
            except Exception as e:
                warning_message = f"{warning_message or 'Extraction successful.'} However, failed to upload results to S3: {str(e)}"
        
        response = {
            'success': True,
            'data': extracted_data,
            's3_result_key': result_key
        }
        
        if warning_message:
            response['warning'] = warning_message
        
        return jsonify(response), 200
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/info/<extraction_id>', methods=['GET'])
def get_info(extraction_id):
    """
    Retrieve previously extracted and stored information from S3.
    
    Args:
        extraction_id: The S3 key or identifier of the stored extraction result
    
    Query params:
        bucket: S3 bucket name (optional, defaults to configured bucket)
    
    Response:
    {
        "success": true,
        "data": { ... },
        "s3_key": "..."
    }
    """
    try:
        bucket = request.args.get('bucket', S3_BUCKET)
        
        if not bucket:
            return jsonify({'error': 'Bucket not specified and S3_BUCKET_NAME not configured'}), 400
        
        # Download the extraction result from S3
        try:
            response = S3_CLIENT.get_object(Bucket=bucket, Key=extraction_id)
            json_data = response['Body'].read().decode('utf-8')
            extracted_data = json.loads(json_data)
            
            return jsonify({
                'success': True,
                'data': extracted_data,
                's3_key': extraction_id
            }), 200
        
        except S3_CLIENT.exceptions.NoSuchKey:
            return jsonify({'error': f'Extraction result not found: {extraction_id}'}), 404
        except Exception as e:
            return jsonify({'error': f'Failed to retrieve extraction result: {str(e)}'}), 500
    
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify S3 connection."""
    try:
        # Verify S3 connection
        S3_CLIENT.head_bucket(Bucket=S3_BUCKET)
        return jsonify({'status': 'healthy', 'bucket': S3_BUCKET}), 200
    
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
