from info_utils import normalize_field, merge_lists, merge_social_media

def merge_extracted_data(img_data_image1, img_data_image2):
    """
    Merge extracted information from two images.
    
    Args:
        img_data_image1: Extracted data from first image
        img_data_image2: Extracted data from second image
    
    Returns:
        Merged extracted data dict
    """
    merged = {}
    
    # MERGE COMPANY NAMES
    company1 = normalize_field(img_data_image1.get('company_name'), return_type='list')
    company2 = normalize_field(img_data_image2.get('company_name'), return_type='list')
    merged['company_name'] = merge_lists(company1, company2)
    
    # MERGE PERSON NAMES
    person1 = normalize_field(img_data_image1.get('person_name'), return_type='list')
    person2 = normalize_field(img_data_image2.get('person_name'), return_type='list')
    merged['person_name'] = merge_lists(person1, person2)
    
    # SIMPLE FIELDS (prefer non-null)
    merged['address'] = (
        img_data_image1.get('address') or 
        img_data_image2.get('address') or 
        None
    )
    
    # CATEGORY (single string)
    merged['category'] = (
        normalize_field(img_data_image1.get('category'), return_type='string') or
        normalize_field(img_data_image2.get('category'), return_type='string') or
        None
    )
    
    # ARRAY FIELDS (merge and deduplicate)
    array_fields = ['contact_numbers', 'email_addresses', 'services', 'website']
    
    for field in array_fields:
        data1 = img_data_image1.get(field)
        data2 = img_data_image2.get(field)
        merged[field] = merge_lists(data1, data2)
    
    # SOCIAL MEDIA PROFILES
    social1 = img_data_image1.get('social_media_profiles', {}) or {}
    social2 = img_data_image2.get('social_media_profiles', {}) or {}
    merged['social_media_profiles'] = merge_social_media(social1, social2)
    
    return merged
