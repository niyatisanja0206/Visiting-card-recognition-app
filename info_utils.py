"""Utility functions for data normalization and deduplication"""


def normalize_field(value, return_type='list'):
    """
    Normalize field values to consistent format.
    
    Args:
        value: The raw value (string, list, dict, None, etc.)
        return_type: 'list' (returns array), 'string' (returns single string), or 'dict' (returns dict as-is)
    
    Returns:
        Normalized value or None if empty
    """
    if return_type == 'list':
        if not value:
            return None
        
        if isinstance(value, list):
            normalized = [str(item).strip() for item in value if item]
            return normalized if normalized else None
        elif isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else None
        
        return None
    
    elif return_type == 'string':
        if not value:
            return None
        
        # If it's a list, take the first non-empty item
        if isinstance(value, list):
            for item in value:
                if item:
                    value = item
                    break
            else:
                return None
        
        # Convert to string and strip
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        
        return None
    
    elif return_type == 'dict':
        return value if value else None
    
    return None


def deduplicate_list(items):
    """
    Remove duplicates from a list while preserving order (case-insensitive comparison).
    
    Args:
        items: List of items to deduplicate
    
    Returns:
        Deduplicated list or None if empty
    """
    if not items:
        return None
    
    seen = set()
    result = []
    
    for item in items:
        if item:
            item_lower = str(item).lower().strip()
            if item_lower and item_lower not in seen:
                seen.add(item_lower)
                result.append(item)
    
    return result if result else None


def merge_lists(*lists, deduplicate=True):
    """
    Merge multiple lists and optionally deduplicate.
    
    Args:
        *lists: Variable number of lists or values to merge
        deduplicate: Whether to remove duplicates (default: True)
    
    Returns:
        Merged list or None if empty
    """
    combined = []
    
    for lst in lists:
        if lst:
            if isinstance(lst, list):
                combined.extend(lst)
            else:
                combined.append(lst)
    
    if not combined:
        return None
    
    if deduplicate:
        return deduplicate_list(combined)
    
    return combined if combined else None


def normalize_social_media(social_data):
    """
    Normalize social media profiles object.
    
    Args:
        social_data: Dict containing social media profiles
    
    Returns:
        Normalized social media dict
    """
    if not social_data:
        return {
            'facebook': None,
            'instagram': None,
            'linkedin': None,
            'twitter': None,
            'youtube': None,
            'other': None
        }
    
    platforms = ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']
    normalized = {}
    
    for platform in platforms:
        normalized[platform] = normalize_field(social_data.get(platform), return_type='list')
    
    # Handle 'other' field
    normalized['other'] = normalize_field(social_data.get('other'), return_type='list')
    
    return normalized


def merge_social_media(social1, social2):
    """
    Merge two social media profile objects.
    
    Args:
        social1: First social media dict
        social2: Second social media dict
    
    Returns:
        Merged social media dict
    """
    social1 = social1 or {}
    social2 = social2 or {}
    
    platforms = ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']
    merged = {}
    
    # Merge individual platforms (prefer non-null)
    for platform in platforms:
        merged[platform] = social1.get(platform) or social2.get(platform) or None
    
    # Merge 'other' arrays
    other1 = social1.get('other') or []
    other2 = social2.get('other') or []
    merged['other'] = merge_lists(other1, other2)
    
    return merged


def has_content(value):
    """
    Check if a value has meaningful content.
    
    Args:
        value: Any value to check
    
    Returns:
        True if value has content, False otherwise
    """
    if value is None:
        return False
    
    if isinstance(value, str):
        return bool(value.strip())
    
    if isinstance(value, list):
        return any(has_content(item) for item in value)
    
    if isinstance(value, dict):
        return any(has_content(v) for v in value.values())
    
    return bool(value)
