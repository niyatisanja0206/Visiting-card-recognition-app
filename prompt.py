prompt = """Extract all the following information from this visiting card image(s). Return ONLY a valid JSON object with the following structure. Do not include any additional text, explanations, or markdown formatting - ONLY the JSON object.

CRITICAL RULES - READ CAREFULLY:
1. ONLY extract information that is ACTUALLY VISIBLE and EXPLICITLY WRITTEN in the image. DO NOT make assumptions, inferences, or guesses.
2. DO NOT extract information based on logos, app icons, or images alone. Text must be explicitly present.
3. If the image is NOT a visiting card (e.g., it's just a logo, app icon, or random image), return null for ALL fields.
4. DO NOT create or invent services, contact information, or any other data. Only extract what is clearly written.
5. If you cannot clearly see and read the information, use null - DO NOT guess or make up information.
6. IMPORTANT: Scan and decode ANY QR codes present in the image. Extract website URLs and social media profile URLs from QR codes. QR codes may contain links to websites, social media profiles, or other online resources.

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
  "website": ["website URL 1", "website URL 2"] or "single website URL" or null,
  "email_addresses": ["email1@example.com", "email2@example.com"],
  "category": "single business category string (e.g., Healthcare, Technology, Education, etc.) or null - MUST be only ONE category, not an array"
}

Extraction Rules:
- If information is not available or not clearly visible, use null (not empty string)
- Extract phone numbers, emails, website links, and social media links that are EXPLICITLY WRITTEN in the image OR extracted from QR codes
- For company_name: Extract ONLY company names that are clearly written as text. If you only see a logo without text, use null. Return an array where each element is a string containing "Company Name\\nQuote/Subtitle" (combine the company name with its associated quote, tagline, subtitle, or slogan on the same line, separated by \\n). If there is only one company name, you can return either a string or an array with one element. Extract ONLY company names that are explicitly written as text.
- For company_quote: Always set this to null (quotes are now included in company_name)
- For person_name: Extract ONLY person names that are clearly written as text. If no person name is visible, use null.
- For services: Extract ONLY services that are EXPLICITLY LISTED or WRITTEN on the card. DO NOT infer services from logos, app icons, or company names. If services are not explicitly written, use null.
- For social_media_profiles: Extract URLs that are explicitly written on the card OR decoded from QR codes. Scan all QR codes in the image and extract social media profile URLs (Facebook, Instagram, LinkedIn, Twitter, YouTube, etc.) from them. DO NOT guess social media profiles, but DO extract them from QR codes if present.
- For website: Extract website URLs that are explicitly written on the card OR decoded from QR codes. Scan all QR codes in the image and extract website URLs from them. DO NOT create or guess website URLs, but DO extract them from QR codes if present.
- For email_addresses: Extract ONLY emails that are explicitly written. DO NOT create or guess them. (Note: QR codes typically contain URLs, not email addresses)
- For category: Return ONLY ONE category as a single string value (NOT an array). Only determine category if you can clearly see services or business information written on the card. If multiple categories seem applicable, choose the PRIMARY or MOST RELEVANT one. If not clear, use null. The category field MUST be a string or null, never an array.
- QR CODE EXTRACTION: If QR codes are present in the image, decode them and extract any URLs they contain. Categorize the URLs appropriately:
  * Website URLs → add to "website" field
  * Social media URLs (Facebook, Instagram, LinkedIn, Twitter, YouTube) → add to corresponding field in "social_media_profiles"
  * Other social media URLs → add to "social_media_profiles.other"
- If the image appears to be just a logo, app icon, or is not a visiting card, return null for ALL fields.
- Return ONLY the JSON object, nothing else"""

def get_prompt():
    return prompt