/* filepath: c:\Users\Dell\Projects\Clkwise\frontend\js\upload.js */
document.addEventListener('DOMContentLoaded', function() {
    // File input change handlers
    document.getElementById('hdlFile').addEventListener('change', function(e) {
      updateFileLabel(this, 'hdlFile');
    });
    
    document.getElementById('timingFile').addEventListener('change', function(e) {
      updateFileLabel(this, 'timingFile');
    });
    
    // Form submission handlers
    document.getElementById('hdlUploadForm').addEventListener('submit', function(e) {
      e.preventDefault();
      uploadFile(this, 'hdl', 'hdlUploadStatus');
    });
    
    document.getElementById('timingUploadForm').addEventListener('submit', function(e) {
      e.preventDefault();
      uploadFile(this, 'timing', 'timingUploadStatus');
    });
    
    // Process button click handler
    document.getElementById('processButton').addEventListener('click', function() {
      processFiles();
    });
    
    // Check for existing uploads
    updateFileList();
  });
  
  /**
   * Update file label when a file is selected
   */
  function updateFileLabel(input, inputId) {
    const label = document.querySelector(`label[for="${inputId}"]`);
    const fileText = label.querySelector('.file-text');
    
    if (input.files && input.files[0]) {
      fileText.textContent = input.files[0].name;
      label.style.borderColor = 'var(--primary-blue)';
    } else {
      fileText.textContent = 'CHOOSE FILE';
      label.style.borderColor = 'var(--border-color)';
    }
  }
  
  /**
   * Upload a file to the server
   */
  function uploadFile(form, fileType, statusElementId) {
    const fileInput = form.querySelector('input[type="file"]');
    const statusElement = document.getElementById(statusElementId);
    
    if (!fileInput.files || fileInput.files.length === 0) {
      statusElement.textContent = 'Please select a file first';
      statusElement.className = 'upload-status error';
      return;
    }
    
    // Create FormData object
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    // Show uploading state
    statusElement.textContent = 'Uploading...';
    statusElement.className = 'upload-status';
    
    // Send the file to server
    fetch(`/api/upload/${fileType}`, {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        statusElement.textContent = `File uploaded successfully!`;
        statusElement.className = 'upload-status success';
        
        // Update file list and enable process button
        updateFileList();
      } else {
        statusElement.textContent = `Error: ${data.error}`;
        statusElement.className = 'upload-status error';
      }
    })
    .catch(error => {
      statusElement.textContent = `Upload failed: ${error.message}`;
      statusElement.className = 'upload-status error';
      console.error('Upload error:', error);
    });
  }
  
  /**
   * Update the list of uploaded files
   */
  function updateFileList() {
    const fileListElement = document.getElementById('uploadedFilesList');
    
    fetch('/api/uploads/list')
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          const hdlFiles = data.hdl_files || [];
          const timingFiles = data.timing_files || [];
          
          if (hdlFiles.length === 0 && timingFiles.length === 0) {
            fileListElement.innerHTML = '<p>No files uploaded yet</p>';
            document.getElementById('processButton').disabled = true;
            return;
          }
          
          let html = '';
          
          // Add HDL files
          if (hdlFiles.length > 0) {
            html += '<h4>HDL Files</h4>';
            hdlFiles.forEach(file => {
              html += `<div class="file-item">
                        <span>${file.name}</span>
                        <span>${formatFileSize(file.size)}</span>
                      </div>`;
            });
          }
          
          // Add timing files
          if (timingFiles.length > 0) {
            html += '<h4>Timing Reports</h4>';
            timingFiles.forEach(file => {
              html += `<div class="file-item">
                        <span>${file.name}</span>
                        <span>${formatFileSize(file.size)}</span>
                      </div>`;
            });
          }
          
          fileListElement.innerHTML = html;
          
          // Enable process button if we have both HDL and timing files
          document.getElementById('processButton').disabled = !(hdlFiles.length > 0 && timingFiles.length > 0);
        } else {
          fileListElement.innerHTML = `<p>Error: ${data.error || 'Failed to load file list'}</p>`;
        }
      })
      .catch(error => {
        fileListElement.innerHTML = `<p>Error: ${error.message}</p>`;
        console.error('Error fetching file list:', error);
      });
  }
  
  /**
   * Format file size in human-readable format
   */
  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }
  
  /**
   * Process the uploaded files
   */
  function processFiles() {
    const processButton = document.getElementById('processButton');
    const originalText = processButton.textContent;
    
    // Disable button and show loading state
    processButton.disabled = true;
    processButton.textContent = 'PROCESSING...';
    
    // Call processing endpoint
    fetch('/api/process/upload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        // Redirect to results page
        window.location.href = '/results';
      } else {
        alert('Error: ' + (data.error || 'Processing failed'));
        processButton.textContent = originalText;
        processButton.disabled = false;
      }
    })
    .catch(error => {
      alert('Processing failed: ' + error.message);
      console.error('Processing error:', error);
      processButton.textContent = originalText;
      processButton.disabled = false;
    });
  }
  
  // Add animation for upload forms
  document.querySelectorAll('.upload-form').forEach((form, index) => {
    setTimeout(() => {
      form.style.animation = 'fadeInUp 0.5s ease-out forwards';
      form.style.opacity = '1';
    }, index * 200);
  });
  
  // Add keyframe animations
  const styleElement = document.createElement('style');
  styleElement.textContent = `
    @keyframes fadeInUp {
      0% { opacity: 0; transform: translateY(20px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    
    .upload-form {
      opacity: 0;
    }
  `;
  document.head.appendChild(styleElement);