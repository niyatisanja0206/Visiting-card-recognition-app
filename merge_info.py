def merge_extracted_data(img_data_image1, img_data_image2):
    # Merge extracted information from two images
    merged = {}
    
    # Handle company names - normalize to arrays and merge them
    company1 = img_data_image1.get('company_name')
    company2 = img_data_image2.get('company_name')
    quote1 = img_data_image1.get('company_quote')
    quote2 = img_data_image2.get('company_quote')
    
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
    person1 = img_data_image1.get('person_name')
    person2 = img_data_image2.get('person_name')
    
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
    
    # Simple fields - prefer non-null, or data_image1 if both are non-null
    # Handle address (can be array)
    merged['address'] = img_data_image1.get('address') or img_data_image2.get('address') or None
    
    # Handle category - must be a single string, not an array
    category1 = img_data_image1.get('category')
    category2 = img_data_image2.get('category')
    
    # Normalize category to single string
    category = None
    if category1:
        if isinstance(category1, list):
            category = category1[0] if category1 else None
        elif isinstance(category1, str):
            category = category1.strip() if category1.strip() else None
    elif category2:
        if isinstance(category2, list):
            category = category2[0] if category2 else None
        elif isinstance(category2, str):
            category = category2.strip() if category2.strip() else None
    
    merged['category'] = category
    
    # Array fields - combine and remove duplicates
    array_fields = ['contact_numbers', 'email_addresses', 'services', 'website']
    for field in array_fields:
        combined = []
        if img_data_image1.get(field):
            if isinstance(img_data_image1[field], list):
                combined.extend(img_data_image1[field])
            else:
                combined.append(img_data_image1[field])
        if img_data_image2.get(field):
            if isinstance(img_data_image2[field], list):
                combined.extend(img_data_image2[field])
            else:
                combined.append(img_data_image2[field])
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in combined:
            if item and item.lower() not in seen:
                seen.add(item.lower())
                unique.append(item)
        merged[field] = unique if unique else None
    
    # Social media profiles - merge objects
    social1 = img_data_image1.get('social_media_profiles', {}) or {}
    social2 = img_data_image2.get('social_media_profiles', {}) or {}
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

