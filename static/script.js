const imageInput = document.getElementById('imageInput');
const uploadForm = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const previewContainer = document.getElementById('previewContainer');
const resultSection = document.getElementById('resultSection');
const resultContent = document.getElementById('resultContent');
const errorSection = document.getElementById('errorSection');
const errorText = document.getElementById('errorText');
const warningSection = document.getElementById('warningSection');
const warningText = document.getElementById('warningText');
const clearBtn = document.getElementById('clearBtn');
const downloadJsonBtn = document.getElementById('downloadJsonBtn');

let selectedFiles = [];
let currentExtractedData = null;

// Handle file selection
imageInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    
    // Limit to 2 files
    if (files.length > 2) {
        alert('Maximum 2 images are allowed');
        e.target.value = '';
        return;
    }
    
    selectedFiles = files;
    displayPreviews();
    updateSubmitButton();
});

// Display image previews
function displayPreviews() {
    previewContainer.innerHTML = '';
    
    selectedFiles.forEach((file, index) => {
        const fileExtension = file.name.split('.').pop().toLowerCase();
        const isHeic = fileExtension === 'heic' || fileExtension === 'heif';
        
        if (isHeic && typeof heic2any !== 'undefined') {
            // Convert HEIC to JPEG for preview
            heic2any({
                blob: file,
                toType: "image/jpeg",
                quality: 0.8
            }).then(conversionResult => {
                // heic2any returns an array, get the first blob
                const blob = Array.isArray(conversionResult) ? conversionResult[0] : conversionResult;
                const reader = new FileReader();
                reader.onload = (e) => {
                    const previewItem = document.createElement('div');
                    previewItem.className = 'preview-item';
                    previewItem.innerHTML = `
                        <img src="${e.target.result}" alt="Preview ${index + 1}">
                        <button type="button" class="remove-btn" onclick="removeFile(${index})">×</button>
                    `;
                    previewContainer.appendChild(previewItem);
                };
                reader.readAsDataURL(blob);
            }).catch(error => {
                console.error('Error converting HEIC image:', error);
                // Fallback: show placeholder or error message
                const previewItem = document.createElement('div');
                previewItem.className = 'preview-item';
                previewItem.innerHTML = `
                    <div style="padding: 20px; text-align: center; background: #f0f0f0;">
                        <p>HEIC Preview</p>
                        <p style="font-size: 12px; color: #666;">${file.name}</p>
                    </div>
                    <button type="button" class="remove-btn" onclick="removeFile(${index})">×</button>
                `;
                previewContainer.appendChild(previewItem);
            });
        } else {
            // Handle regular image formats
            const reader = new FileReader();
            reader.onload = (e) => {
                const previewItem = document.createElement('div');
                previewItem.className = 'preview-item';
                previewItem.innerHTML = `
                    <img src="${e.target.result}" alt="Preview ${index + 1}">
                    <button type="button" class="remove-btn" onclick="removeFile(${index})">×</button>
                `;
                previewContainer.appendChild(previewItem);
            };
            reader.readAsDataURL(file);
        }
    });
}

// Remove file from selection
function removeFile(index) {
    selectedFiles.splice(index, 1);
    
    // Update the file input
    const dataTransfer = new DataTransfer();
    selectedFiles.forEach(file => dataTransfer.items.add(file));
    imageInput.files = dataTransfer.files;
    
    displayPreviews();
    updateSubmitButton();
}

// Update submit button state
function updateSubmitButton() {
    submitBtn.disabled = selectedFiles.length === 0;
}

// Handle form submission
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    if (selectedFiles.length === 0) {
        showError('Please select at least one image');
        return;
    }
    
    // Hide previous results, errors, and warnings
    resultSection.style.display = 'none';
    errorSection.style.display = 'none';
    warningSection.style.display = 'none';
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.classList.add('loading');
    
    // Create FormData
    const formData = new FormData();
    selectedFiles.forEach(file => {
        formData.append('images', file);
    });
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            currentExtractedData = data.data;
            
            // Show warning if present
            if (data.warning) {
                showWarning(data.warning);
            }
            
            displayResults(data.data);
        } else {
            showError(data.error || 'An error occurred while processing the images');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.classList.remove('loading');
    }
});

// Display extracted results
function displayResults(data) {
    resultContent.innerHTML = '';
    
    // Helper function to create info group
    function createInfoGroup(label, value, icon = '') {
        if (!value || (Array.isArray(value) && value.length === 0) || 
            (typeof value === 'object' && Object.keys(value).length === 0)) {
            return '';
        }
        
        const group = document.createElement('div');
        group.className = 'info-group';
        
        const labelEl = document.createElement('div');
        labelEl.className = 'info-label';
        labelEl.innerHTML = icon ? `${icon} ${label}` : label;
        
        const valueEl = document.createElement('div');
        valueEl.className = 'info-value';
        
        if (Array.isArray(value)) {
            const ul = document.createElement('ul');
            value.forEach(item => {
                if (item) {
                    const li = document.createElement('li');
                    li.textContent = item;
                    ul.appendChild(li);
                }
            });
            valueEl.appendChild(ul);
        } else if (typeof value === 'object') {
            // Handle social media profiles
            const linksContainer = document.createElement('div');
            linksContainer.className = 'social-links';
            
            Object.entries(value).forEach(([platform, url]) => {
                if (platform !== 'other' && url) {
                    const link = document.createElement('a');
                    link.href = url;
                    link.target = '_blank';
                    link.className = 'social-link';
                    link.textContent = platform.charAt(0).toUpperCase() + platform.slice(1);
                    linksContainer.appendChild(link);
                }
            });
            
            if (value.other && Array.isArray(value.other)) {
                value.other.forEach(url => {
                    if (url) {
                        const link = document.createElement('a');
                        link.href = url;
                        link.target = '_blank';
                        link.className = 'social-link';
                        link.textContent = url;
                        linksContainer.appendChild(link);
                    }
                });
            }
            
            if (linksContainer.children.length > 0) {
                valueEl.appendChild(linksContainer);
            } else {
                return '';
            }
        } else {
            // Check if it's a URL
            if (value.startsWith('http://') || value.startsWith('https://')) {
                const link = document.createElement('a');
                link.href = value;
                link.target = '_blank';
                link.textContent = value;
                valueEl.appendChild(link);
            } else {
                valueEl.textContent = value;
            }
        }
        
        group.appendChild(labelEl);
        group.appendChild(valueEl);
        return group;
    }
    
    // Add each field
    if (data.company_name) {
        // Handle company_name as array or string (for backward compatibility)
        let companyNames = [];
        if (Array.isArray(data.company_name)) {
            companyNames = data.company_name;
        } else if (typeof data.company_name === 'string') {
            companyNames = [data.company_name];
        }
        
        if (companyNames.length > 0) {
            // If multiple company names, display as list, otherwise as single value
            if (companyNames.length === 1) {
                resultContent.appendChild(createInfoGroup('Company Name', companyNames[0]));
            } else {
                resultContent.appendChild(createInfoGroup('Company Names', companyNames));
            }
        }
    }
    
    if (data.person_name) {
        // Handle person_name as array or string (for backward compatibility)
        let personNames = [];
        if (Array.isArray(data.person_name)) {
            personNames = data.person_name;
        } else if (typeof data.person_name === 'string') {
            personNames = [data.person_name];
        }
        
        if (personNames.length > 0) {
            // If multiple person names, display as list, otherwise as single value
            if (personNames.length === 1) {
                resultContent.appendChild(createInfoGroup('Person Name', personNames[0]));
            } else {
                resultContent.appendChild(createInfoGroup('Person Names', personNames));
            }
        }
    }
    
    if (data.category) {
        resultContent.appendChild(createInfoGroup('Category', data.category));
    }
    
    if (data.contact_numbers && data.contact_numbers.length > 0) {
        resultContent.appendChild(createInfoGroup('Contact Numbers', data.contact_numbers));
    }
    
    if (data.email_addresses && data.email_addresses.length > 0) {
        resultContent.appendChild(createInfoGroup('Email Addresses', data.email_addresses));
    }
    
    if (data.website) {
        resultContent.appendChild(createInfoGroup('Website', data.website));
    }
    
    if (data.address) {
        resultContent.appendChild(createInfoGroup('Address', data.address));
    }
    
    if (data.services && data.services.length > 0) {
        resultContent.appendChild(createInfoGroup('Services', data.services));
    }
    
    if (data.social_media_profiles) {
        const socialGroup = createInfoGroup('Social Media Profiles', data.social_media_profiles);
        if (socialGroup) {
            resultContent.appendChild(socialGroup);
        }
    }
    
    // Show result section
    resultSection.style.display = 'block';
    
    // Scroll to results
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Show warning message
function showWarning(message) {
    warningText.textContent = message;
    warningSection.style.display = 'block';
    warningSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Show error message
function showError(message) {
    errorText.textContent = message;
    errorSection.style.display = 'block';
    errorSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Download JSON file
downloadJsonBtn.addEventListener('click', () => {
    if (!currentExtractedData) {
        showError('No data available to download');
        return;
    }
    
    // Create JSON string
    const jsonString = JSON.stringify(currentExtractedData, null, 2);
    
    // Create a blob with the JSON data
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    // Create a download link
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    // Generate filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    link.download = `extracted_data_${timestamp}.json`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Clean up the URL
    URL.revokeObjectURL(url);
});

// Clear results
clearBtn.addEventListener('click', () => {
    resultSection.style.display = 'none';
    resultContent.innerHTML = '';
    errorSection.style.display = 'none';
    warningSection.style.display = 'none';
    currentExtractedData = null;
    
    // Clear file selection
    selectedFiles = [];
    imageInput.value = '';
    previewContainer.innerHTML = '';
    updateSubmitButton();
});
