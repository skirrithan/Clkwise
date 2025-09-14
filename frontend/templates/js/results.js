/* filepath: c:\Users\Dell\Projects\Clkwise\frontend\js\results.js */
// Results page JavaScript

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize code highlighting
    hljs.configure({ languages: ['verilog', 'systemverilog'] });
    hljs.highlightAll();
    
    // Initialize the code comparison view
    initializeCodeComparison();
    
    // Load fixes if available
    loadFixes();
    
    // Add event listeners for violation items
    document.querySelectorAll('.violation-item').forEach(item => {
      item.addEventListener('click', function() {
        const id = this.getAttribute('data-id');
        showViolationDetails(id);
      });
    });
    
    // Set up tab switching in code comparison
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const view = this.getAttribute('data-view');
        switchCodeView(view);
      });
    });
    
    // Add chat message handler
    const chatInput = document.getElementById('chatInput');
    chatInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });
  
    // Add animation to metrics
    animateMetrics();
  });
  
  /**
   * Initialize the code comparison functionality
   */
  function initializeCodeComparison() {
    // Fetch original code
    fetch('/api/original/top.sv')
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          const originalCode = data.content;
          const originalCodeElem = document.getElementById('originalCode');
          originalCodeElem.textContent = originalCode;
          hljs.highlightElement(originalCodeElem);
          
          // Now fetch optimized code
          return fetch('/api/optimized/top.sv')
            .then(response => response.json())
            .then(data => {
              if (data.status === 'success') {
                const optimizedCode = data.content;
                const optimizedCodeElem = document.getElementById('optimizedCode');
                optimizedCodeElem.textContent = optimizedCode;
                hljs.highlightElement(optimizedCodeElem);
                
                // Generate diff
                generateDiff(originalCode, optimizedCode);
              } else {
                showError('Failed to load optimized code: ' + (data.error || 'Unknown error'));
              }
            });
        } else {
          showError('Failed to load original code: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(error => {
        showError('Error loading code: ' + error);
      });
  }
  
  /**
   * Generate diff between original and optimized code
   */
  function generateDiff(originalCode, optimizedCode) {
    try {
      // Create unified diff
      const diffJson = Diff2Html.getJsonFromDiff(
        `--- a/original.sv\n+++ b/optimized.sv\n${Diff.createTwoFilesPatch('original.sv', 'optimized.sv', originalCode, optimizedCode)}`,
        { outputFormat: 'side-by-side', drawFileList: false }
      );
      
      // Render the diff
      const diffOutput = Diff2Html.html(diffJson, {
        drawFileList: false,
        matching: 'lines',
        outputFormat: 'side-by-side',
        synchronisedScroll: true
      });
      
      document.getElementById('diffView').innerHTML = diffOutput;
    } catch (e) {
      showError('Error generating diff: ' + e.message);
    }
  }
  
  /**
   * Switch between code views (diff, original, optimized)
   */
  function switchCodeView(view) {
    // Update active tab
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-view') === view);
    });
    
    // Show selected view
    document.querySelectorAll('.code-view').forEach(v => {
      v.classList.toggle('hidden', v.id !== view + 'View');
    });
  }
  
  /**
   * Load fixes data from API
   */
  function loadFixes() {
    const fixesListElement = document.getElementById('fixesList');
    if (!fixesListElement) return;
    
    fetch('/api/analysis')
      .then(response => response.json())
      .then(data => {
        if (data.status === 'success') {
          const fixes = data.data.analysis?.fixes || [];
          
          if (fixes.length > 0) {
            fixesListElement.innerHTML = '';
            
            fixes.forEach((fix, index) => {
              const impactClass = getImpactClass(fix.impact || 'medium');
              
              const fixElement = document.createElement('div');
              fixElement.className = 'fix-item';
              fixElement.innerHTML = `
                <div class="fix-header">
                  <div class="fix-title">Fix ${index + 1}: ${fix.title || 'Untitled Fix'}</div>
                  <div class="fix-impact ${impactClass}">${fix.impact || 'Medium'} Impact</div>
                </div>
                <div class="fix-content">
                  <p>${fix.rationale || 'No rationale provided.'}</p>
                  ${fix.latency_impact_cycles ? `<p><strong>Latency Impact:</strong> ${fix.latency_impact_cycles} cycles</p>` : ''}
                </div>
              `;
              
              fixesListElement.appendChild(fixElement);
            });
          } else {
            fixesListElement.innerHTML = '<p>No fixes available for this analysis.</p>';
          }
        } else {
          showError('Failed to load fixes: ' + (data.error || 'Unknown error'));
        }
      })
      .catch(error => {
        showError('Error loading fixes: ' + error);
      });
  }
  
  /**
   * Get the appropriate CSS class for the fix impact
   */
  function getImpactClass(impact) {
    const normalized = impact.toLowerCase();
    if (normalized.includes('high')) return 'high';
    if (normalized.includes('low')) return 'low';
    return 'medium';
  }
  
  /**
   * Show violation details
   */
  function showViolationDetails(id) {
    // This would normally fetch detailed information about the violation
    // For now we just toggle the selection state
    document.querySelectorAll('.violation-item').forEach(item => {
      item.classList.toggle('selected', item.getAttribute('data-id') === id);
    });
  }
  
  /**
   * Send a chat message
   */
  function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addMessage(message, 'user');
    input.value = '';
    
    // Send to backend
    fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        context: 'results'
      })
    })
    .then(response => response.json())
    .then(data => {
      if (data.status === 'success') {
        addMessage(data.response, 'ai');
      } else {
        addMessage('Sorry, I encountered an error: ' + data.error, 'system');
      }
    })
    .catch(error => {
      addMessage('Sorry, I encountered an error communicating with the server.', 'system');
      console.error('Chat error:', error);
    });
  }
  
  /**
   * Add a message to the chat window
   */
  function addMessage(text, sender) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    if (sender === 'system') {
      messageDiv.innerHTML = `<strong>System:</strong> ${text}`;
    } else {
      messageDiv.innerHTML = `<strong>${sender === 'user' ? 'You' : 'AI Expert'}:</strong> ${text}`;
    }
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Add animation for new messages
    void messageDiv.offsetWidth; // Force reflow
    messageDiv.style.animation = 'fadeIn 0.3s ease-in-out';
  }
  
  /**
   * Animate the metrics on page load
   */
  function animateMetrics() {
    document.querySelectorAll('.metric').forEach((metric, index) => {
      setTimeout(() => {
        metric.style.animation = 'pulseMetric 0.5s ease-out';
      }, index * 200);
    });
  }
  
  /**
   * Show an error message
   */
  function showError(message) {
    console.error(message);
    // You could also display this visually in the UI
  }
  
  // Add keyframe animations
  const styleElement = document.createElement('style');
  styleElement.textContent = `
    @keyframes fadeIn {
      0% { opacity: 0; transform: translateY(10px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes pulseMetric {
      0% { transform: scale(1); }
      50% { transform: scale(1.05); }
      100% { transform: scale(1); }
    }
    
    .violation-item.selected {
      border-left-color: var(--accent-green);
      background-color: rgba(0, 170, 85, 0.05);
    }
  `;
  document.head.appendChild(styleElement);