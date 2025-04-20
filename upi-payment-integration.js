/**
 * UPI Payment Integration for Skill Match Platform
 * This script handles integration with Indian UPI payment methods
 * including BHIM, Google Pay, PhonePe, etc.
 */

// UPI Payment Handler
const UPIPayment = {
  // List of supported UPI apps
  supportedApps: [
    {
      id: 'bhim',
      name: 'BHIM UPI',
      logo: '/static/img/bhim-logo.png',
      prefixes: ['bhim://upi']
    },
    {
      id: 'gpay',
      name: 'Google Pay',
      logo: '/static/img/gpay-logo.png',
      prefixes: ['gpay://upi', 'tez://upi']
    },
    {
      id: 'phonepe',
      name: 'PhonePe',
      logo: '/static/img/phonepe-logo.png',
      prefixes: ['phonepe://upi']
    },
    {
      id: 'paytm',
      name: 'Paytm',
      logo: '/static/img/paytm-logo.png',
      prefixes: ['paytm://upi']
    }
  ],

  // Check if UPI apps are installed (basic check)
  async detectInstalledApps() {
    // In a real-world scenario, this would use better detection
    // Here we're just returning all supported apps
    return this.supportedApps;
  },

  // Generate UPI payment link
  generateUPILink(upiId, amount, payeeName, transactionNote) {
    const upiParams = new URLSearchParams({
      pa: upiId,                   // UPI ID (Payee Address)
      pn: payeeName,               // Payee Name
      am: amount.toString(),       // Amount
      tn: transactionNote,         // Transaction Note
      cu: 'INR'                    // Currency (Indian Rupee)
    });
    
    return `upi://pay?${upiParams.toString()}`;
  },

  // Open payment in specific UPI app
  openUPIApp(appId, upiLink) {
    const app = this.supportedApps.find(a => a.id === appId);
    if (!app) return false;
    
    // Create modified link with app-specific prefix
    const appSpecificLink = upiLink.replace('upi://', app.prefixes[0]);
    
    // Open the link (in a real implementation, we'd handle this better)
    window.location.href = appSpecificLink;
    return true;
  },

  // Create a QR code for payment
  generateQRCode(upiLink, elementId) {
    // In a real implementation, we'd use a QR code library
    // For now, we'll just show a placeholder message
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = `
        <div class="qr-placeholder">
          <div class="qr-image">QR Code Placeholder</div>
          <div class="qr-text">Scan with any UPI app</div>
          <div class="upi-link"> ₹{upiLink}</div>
        </div>
      `;
    }
    return true;
  }
};

// UPI Withdrawal Handler
const UPIWithdrawal = {
  // Initialize withdrawal form
  init(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    // Add payment method selection
    this.populatePaymentMethods(form);
    
    // Handle form submission
    form.addEventListener('submit', (e) => this.handleWithdrawalSubmit(e));
  },

  // Populate payment method options
  populatePaymentMethods(form) {
    const paymentMethodSelect = form.querySelector('.payment-method-select');
    if (!paymentMethodSelect) return;
    
    // Add UPI option
    const upiOption = document.createElement('option');
    upiOption.value = 'upi';
    upiOption.textContent = 'UPI (BHIM, GPay, PhonePe)';
    paymentMethodSelect.appendChild(upiOption);
    
    // Listen for changes to show appropriate fields
    paymentMethodSelect.addEventListener('change', (e) => {
      this.togglePaymentFields(form, e.target.value);
    });
  },
  
  // Toggle payment detail fields based on method
  togglePaymentFields(form, method) {
    const upiFields = form.querySelector('.upi-fields');
    const bankFields = form.querySelector('.bank-fields');
    
    if (method === 'upi') {
      if (upiFields) upiFields.style.display = 'block';
      if (bankFields) bankFields.style.display = 'none';
    } else if (method === 'bank') {
      if (upiFields) upiFields.style.display = 'none';
      if (bankFields) bankFields.style.display = 'block';
    }
  },
  
  // Handle form submission
  async handleWithdrawalSubmit(e) {
    e.preventDefault();
    const form = e.target;
    
    const amount = parseFloat(form.querySelector('[name="amount"]').value);
    const paymentMethod = form.querySelector('[name="payment_method"]').value;
    let paymentDetails = {};
    
    // Get payment details based on method
    if (paymentMethod === 'upi') {
      paymentDetails = {
        upi_id: form.querySelector('[name="upi_id"]').value,
        upi_app: form.querySelector('[name="upi_app"]').value || 'any'
      };
    } else if (paymentMethod === 'bank') {
      paymentDetails = {
        account_number: form.querySelector('[name="account_number"]').value,
        ifsc_code: form.querySelector('[name="ifsc_code"]').value,
        account_name: form.querySelector('[name="account_name"]').value
      };
    }
    
    try {
      // Show loading spinner
      const spinner = form.querySelector('.loading-spinner');
      if (spinner) spinner.style.display = 'block';
      
      // Submit withdrawal request to server
      const result = await FreelancerManager.requestWithdrawal(
        amount,
        paymentMethod,
        paymentDetails
      );
      
      if (spinner) spinner.style.display = 'none';
      
      if (result.success) {
        this.showSuccessMessage(form, result.withdrawal_id);
        
        // If UPI selected, show QR code
        if (paymentMethod === 'upi') {
          this.showUPIOptions(paymentDetails.upi_id, amount);
        }
      } else {
        this.showErrorMessage(form, result.error);
      }
    } catch (error) {
      const spinner = form.querySelector('.loading-spinner');
      if (spinner) spinner.style.display = 'none';
      
      this.showErrorMessage(form, 'Network error. Please try again.');
    }
  },
  
  // Show UPI payment options
  showUPIOptions(upiId, amount) {
    const modal = document.getElementById('upi-payment-modal');
    if (!modal) return;
    
    // Generate UPI link
    const upiLink = UPIPayment.generateUPILink(
      upiId,
      amount,
      'Skill Match',
      'Withdrawal from Skill Match Platform'
    );
    
    // Generate QR code
    UPIPayment.generateQRCode(upiLink, 'upi-qr-code');
    
    // Populate UPI app options
    const appContainer = document.getElementById('upi-app-options');
    if (appContainer) {
      appContainer.innerHTML = '';
      
      UPIPayment.supportedApps.forEach(app => {
        const appButton = document.createElement('button');
        appButton.className = 'upi-app-button';
        appButton.setAttribute('data-app-id', app.id);
        appButton.innerHTML = `
          <div class="app-icon">${app.name[0]}</div>
          <div class="app-name">${app.name}</div>
        `;
        appButton.addEventListener('click', () => {
          UPIPayment.openUPIApp(app.id, upiLink);
        });
        
        appContainer.appendChild(appButton);
      });
    }
    
    // Show modal
    modal.style.display = 'block';
  },
  
  // Show success message
  showSuccessMessage(form, withdrawalId) {
    const messageContainer = form.querySelector('.message-container');
    if (!messageContainer) return;
    
    messageContainer.innerHTML = `
      <div class="success-message">
        <i class="fas fa-check-circle"></i>
        Withdrawal request submitted successfully!
        <div class="withdrawal-id">Reference ID: ${withdrawalId}</div>
      </div>
    `;
  },
  
  // Show error message
  showErrorMessage(form, error) {
    const messageContainer = form.querySelector('.message-container');
    if (!messageContainer) return;
    
    messageContainer.innerHTML = `
      <div class="error-message">
        <i class="fas fa-exclamation-circle"></i>
        ${error}
      </div>
    `;
  }
};

// Initialize when document is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Initialize withdrawal form if it exists
  const withdrawalForm = document.getElementById('withdrawal-form');
  if (withdrawalForm) {
    UPIWithdrawal.init('withdrawal-form');
  }
  
  console.log('UPI Payment integration initialized!');
});
