"""Flask app for visiting card OCR and data extraction"""

from flask import Flask, request, jsonify

import boto3
import PIL
import os
from io import BytesIO
import json
from datetime import datetime
from urllib.parse import urlparse, unquote_plus
#import pillow_heif
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from extract_info import extract_information
from merge_info import merge_extracted_data
from llm_utils import get_model
from prompt import get_prompt
from info_utils import has_content

# pillow_heif.register_heif_opener()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('SECRET_ACCESS_KEY')
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


# S3 Operations
def download_image_from_s3(s3_url):
    """
    Download image from S3 URL and return PIL Image object.
    
    Args:
        s3_url: S3 URL (Path style or Virtual-hosted style)
    
    Returns:
        Tuple of (PIL Image object, bucket name, object key)
    
    Raises:
        ValueError: If URL is invalid or download fails
    """
    try:
        logger.info(f"Starting image download from S3 URL: {s3_url}")
        
        parsed = urlparse(s3_url)
        
        # Validations
        if not parsed.scheme.startswith('http'):
             raise ValueError("URL must start with http or https")
             
        if "amazonaws.com" not in parsed.netloc:
             # Relax this if needed, but original code had it.
             raise ValueError(f"Invalid S3 URL (must contain amazonaws.com): {s3_url}")

        bucket = None
        key = None

        # Determine URL style
        # Path style: https://s3.us-east-1.amazonaws.com/bucket/key
        # Virtual hosted: https://bucket.s3.us-east-1.amazonaws.com/key
        
        if parsed.netloc.startswith('s3.') or parsed.netloc.startswith('s3-'):
            # Path style
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) < 2:
                raise ValueError(f"Invalid S3 path-style URL (cannot extract bucket/key): {s3_url}")
            bucket = path_parts[0]
            key = path_parts[1]
        else:
            # Assume Virtual-hosted style
            # Bucket is in the hostname before .s3
            s3_index = parsed.netloc.find('.s3')
            if s3_index != -1:
                bucket = parsed.netloc[:s3_index]
                key = parsed.path.lstrip('/')
            else:
                # Fallback: maybe just bucket.s3.amazonaws.com without region in hostname?
                # or just bucket.s3-region... 
                # If we cannot find '.s3', try splitting by first dot if it looks like a bucket
                # But safer to throw error if pattern isn't recognized
                raise ValueError(f"Could not parse bucket from S3 URL: {s3_url}")

        logger.info(f"Parsed - Bucket: {bucket}, Key: {key}")

        if not bucket or not key:
            raise ValueError(f"Failed to identify bucket or key from URL: {s3_url}")

        # Get image from S3
        response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        image = PIL.Image.open(BytesIO(image_data))
        
        logger.info(f"Successfully downloaded image from bucket: {bucket}, key: {key}")
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
        logger.info(f"Uploading extracted data to S3. Bucket: {bucket}, Prefix: {key_prefix}")
        # Generate S3 key for the data file
        # We use a static filename to ensure only one result file exists per entity
        data_key = f"{key_prefix}/{data_type}.json"
        
        # Convert data to JSON
        json_data = json.dumps(data, indent=2)
        
        # Upload to S3
        S3_CLIENT.put_object(
            Bucket=bucket,
            Key=data_key,
            Body=json_data.encode('utf-8'),
            ContentType='application/json'
        )
        
        logger.info(f"Successfully uploaded data to S3: {data_key}")
        return data_key
    
    except Exception as e:
        raise ValueError(f"Failed to upload data to S3: {str(e)}")


# LLM OPERATIONS

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


# DATA VALIDATION

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


# IMAGE PROCESSING

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


# API ENDPOINTS
def process_extraction_request(data):
    """
    Process extraction request data independently of Flask context.
    
    Args:
        data: Dictionary containing request data
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    try:
        if not data:
            return {'error': 'Request body must be JSON/dict'}, 400
        
        image_urls = data.get('image_urls')
        upload_results = data.get('upload_results', True)

        logger.info(f"Received info extraction request for images: {image_urls}")
        
        # Validate image URLs
        if not image_urls:
            return {'error': 'image_urls field is required'}, 400
        
        if not isinstance(image_urls, list):
            return {'error': 'image_urls must be an array'}, 400
        
        if len(image_urls) > 2:
            return {'error': 'Maximum 2 images are supported'}, 400
        
        if len(image_urls) == 0:
            return {'error': 'At least 1 image URL is required'}, 400
        
        # Process images
        extracted_data, bucket, key = process_images(image_urls)

        # Extract event_id and info_id from the key if possible and add to extracted data
        # Expected key format: eventid/infoid/filename.ext or similar structure where IDs are in the path
        if key:
            parts = key.split('/')
            # Assuming structure is .../event_id/info_id/filename
            if len(parts) >= 2:
                extracted_data['info_id'] = parts[-2]
            if len(parts) >= 3:
                extracted_data['event_id'] = parts[-3]
        
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
            logger.warning(warning_message)
        
        logger.info("Sending extraction response")
        return response, 200
    
    except ValueError as e:
        return {'error': str(e)}, 400
    except Exception as e:
        return {'error': f'Internal server error: {str(e)}'}, 500


@app.route('/info', methods=['POST'])
def extract_info():
    """
    Extract information from visiting card images.
    
    Request body:
    {
        "image_urls": ["https://s3.amazonaws.com/bucket/eventid/infoid/image.jpg"],
        "upload_results": true  # Optional: whether to upload results to S3
    }
    """
    data = request.get_json()
    response, status_code = process_extraction_request(data)
    return jsonify(response), status_code

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



def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    """
    logger.info(f"Lambda Handler invoked with event: {json.dumps(event)}")
    
    data = {}
    
    # Handle S3 Event Notification (S3 Trigger)
    if 'Records' in event and isinstance(event['Records'], list):
        try:
            logger.info("Processing S3 Event")
            
            # We will process based on the first record's location
            # If multiple records come in one event, we assume they are related or we pick common prefix
            # For simplicity, we handle the first one and look for siblings
            
            record = event['Records'][0]
            if 's3' in record:
                s3_info = record['s3']
                bucket_name = s3_info['bucket']['name']
                # S3 keys are URL-encoded in events, needs unquoting
                trigger_key = unquote_plus(s3_info['object']['key'])
                region = record.get('awsRegion', 'us-east-1') 
                
                # Identify the parent folder (prefix)
                # Key format: path/to/file.ext -> Prefix: path/to/
                if '/' in trigger_key:
                    prefix = trigger_key.rsplit('/', 1)[0] + '/'
                else:
                    prefix = ''
                
                logger.info(f"Checking for sibling images in bucket: {bucket_name}, prefix: {prefix}")
                
                # List objects in the same directory (prefix)
                try:
                    list_response = S3_CLIENT.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
                    
                    found_images = []
                    
                    if 'Contents' in list_response:
                        for obj in list_response['Contents']:
                            obj_key = obj['Key']
                            # Filter for valid image extensions
                            lower_key = obj_key.lower()
                            if lower_key.endswith(('.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif')):
                                # Construct S3 URL
                                img_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{obj_key}"
                                found_images.append(img_url)
                    
                    logger.info(f"Found {len(found_images)} images in prefix: {found_images}")
                    
                    if not found_images:
                        # Fallback if listing failed to find anything (unlikely if trigger fired)
                         s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{trigger_key}"
                         found_images = [s3_url]
                         
                    data = {
                        'image_urls': found_images,
                        'upload_results': True
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to list sibling files: {e}")
                    # Fallback to just processing the triggering file
                    s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{trigger_key}"
                    data = {
                        'image_urls': [s3_url],
                        'upload_results': True
                    }

        except Exception as e:
            logger.error(f"Failed to parse S3 event record: {e}")
            return {'statusCode': 400, 'body': json.dumps({'error': f"Invalid S3 event: {str(e)}"}) }

    # Handle API Gateway (Proxy or Direct)
    elif 'body' in event:
        try:
             # If body is string (API Gateway), parse it
            if isinstance(event['body'], str):
                data = json.loads(event['body'])
            else:
                data = event['body']
        except Exception as e:
            logger.warning(f"Failed to parse event body: {e}")
            return {'statusCode': 400, 'body': json.dumps({'error': "Invalid JSON body"})}
    
    # Handle direct invocation with data payload
    else:
        data = event
            
    response, status_code = process_extraction_request(data)
    
    return response

# Main function alias as requested
main = lambda_handler
