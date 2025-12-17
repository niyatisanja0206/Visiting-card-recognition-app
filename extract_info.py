import json
import sys

def extract_information(response_text):
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

        # Normalize contact_numbers to always be an array
        contact_numbers = extracted_data.get('contact_numbers')
        contact_numbers_list = []
        
        if contact_numbers:
            # If contact_numbers is already an array
            if isinstance(contact_numbers, list):
                contact_numbers_list = [str(number).strip() for number in contact_numbers if number]
            # If contact_numbers is a string
            elif isinstance(contact_numbers, str):
                contact_numbers_list = [contact_numbers.strip()]
        
        # Set contact_numbers as array (empty array if null, or None if empty)
        if contact_numbers_list:
            extracted_data['contact_numbers'] = contact_numbers_list
        else:
            extracted_data['contact_numbers'] = None

        # Handle social media profiles - normalize each platform to array
        social_media_profiles_obj = {}
        platforms = ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']
        for platform in platforms:
            platform_value = extracted_data.get(platform)
            platform_list = []
            
            if platform_value:
                # If already an array
                if isinstance(platform_value, list):
                    platform_list = [str(profile).strip() for profile in platform_value if profile]
                # If a string
                elif isinstance(platform_value, str):
                    platform_list = [platform_value.strip()]
            
            # Set platform as array (None if empty)
            if platform_list:
                social_media_profiles_obj[platform] = platform_list
            else:
                social_media_profiles_obj[platform] = None
        
        # Handle 'other' social media profiles
        other_profiles = extracted_data.get('other')
        other_list = []
        
        if other_profiles:
            # If already an array
            if isinstance(other_profiles, list):
                other_list = [str(profile).strip() for profile in other_profiles if profile]
            # If a string
            elif isinstance(other_profiles, str):
                other_list = [other_profiles.strip()]
        
        # Set other as array (empty array if null, or None if empty)
        if other_list:
            social_media_profiles_obj['other'] = other_list
        else:
            social_media_profiles_obj['other'] = []
        
        extracted_data['social_media_profiles'] = social_media_profiles_obj

        # Normalize address to always be an array
        address = extracted_data.get('address')
        address_list = []
        
        if address:
            # If address is already an array
            if isinstance(address, list):
                address_list = [str(addr).strip() for addr in address if addr]
            # If address is a string
            elif isinstance(address, str):
                address_list = [address.strip()]
        
        # Set address as array (empty array if null, or None if empty)
        if address_list:
            extracted_data['address'] = address_list
        else:
            extracted_data['address'] = None

        # Normalize services to always be an array
        services = extracted_data.get('services')
        services_list = []
        
        if services:
            # If services is already an array
            if isinstance(services, list):
                services_list = [str(service).strip() for service in services if service]
            # If services is a string
            elif isinstance(services, str):
                services_list = [services.strip()]
        
        # Set services as array (empty array if null, or None if empty)
        if services_list:
            extracted_data['services'] = services_list
        else:
            extracted_data['services'] = None

        # Normalize website to always be an array
        website = extracted_data.get('website')
        website_list = []
        
        if website:
            # If website is already an array
            if isinstance(website, list):
                website_list = [str(url).strip() for url in website if url]
            # If website is a string
            elif isinstance(website, str):
                website_list = [website.strip()]
        
        # Set website as array (empty array if null, or None if empty)
        if website_list:
            extracted_data['website'] = website_list
        else:
            extracted_data['website'] = None

        # Normalize category to always be a single string (NOT an array)
        category = extracted_data.get('category')
        if category:
            # If category is an array, take the first non-empty value
            if isinstance(category, list):
                category_list = [str(c).strip() for c in category if c]
                extracted_data['category'] = category_list[0] if category_list else None
            # If category is a string, use it as is
            elif isinstance(category, str):
                extracted_data['category'] = category.strip() if category.strip() else None
            else:
                extracted_data['category'] = None
        else:
            extracted_data['category'] = None

        return extracted_data
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON response: {e}", file=sys.stderr)
        print(f"Raw response: {response_text}", file=sys.stderr)
        raise
