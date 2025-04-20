/**
 * Skill Match Platform API Demo
 * 
 * This file demonstrates how to interact with the Skill Match Platform API
 * endpoints defined in helper_for_savan.py using JavaScript.
 */

// Base URL for API requests
const API_BASE_URL = 'http://localhost:5000/api';

// Helper function for making API requests
async function fetchAPI(endpoint, method = 'GET', body = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include', // Important for cookies/session
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('API request failed:', error);
    return { success: false, error: 'Network error' };
  }
}

// User Authentication Functions
const UserAuth = {
  // Register a new user
  async register(username, password, userType, skills = [], hourlyRate = 0) {
    const payload = {
      username,
      password,
      user_type: userType
    };

    if (userType === 'freelancer') {
      payload.skills = skills;
      payload.hourly_rate = hourlyRate;
    }

    return await fetchAPI('/register', 'POST', payload);
  },
  
  // Login a user
  async login(username, password) {
    return await fetchAPI('/login', 'POST', { username, password });
  }
};

// Job Management Functions
const JobManager = {
  // Post a new job
  async postJob(title, description, skillsRequired, budget, deadline) {
    return await fetchAPI('/jobs', 'POST', {
      title,
      description,
      skills_required: skillsRequired,
      budget,
      deadline
    });
  },
  
  // Search for jobs
  async searchJobs(skills = [], minBudget = null, status = 'open') {
    let endpoint = '/jobs/search?';
    
    if (skills.length > 0) {
      endpoint += `skills=${skills.join(',')}&`;
    }
    
    if (minBudget) {
      endpoint += `min_budget=${minBudget}&`;
    }
    
    endpoint += `status=${status}`;
    
    return await fetchAPI(endpoint);
  },
  
  // Apply for a job
  async applyForJob(jobId, proposal, bidAmount) {
    return await fetchAPI(`/jobs/${jobId}/apply`, 'POST', {
      proposal,
      bid_amount: bidAmount
    });
  },
  
  // Award a job to a freelancer
  async awardJob(jobId, freelancerId) {
    return await fetchAPI(`/jobs/${jobId}/award`, 'POST', {
      freelancer_id: freelancerId
    });
  },
  
  // Complete a job and provide rating
  async completeJob(jobId, rating) {
    return await fetchAPI(`/jobs/${jobId}/complete`, 'POST', {
      rating
    });
  }
};

// Freelancer Functions
const FreelancerManager = {
  // Search for freelancers
  async searchFreelancers(skills = [], maxRate = null, minRating = null) {
    let endpoint = '/freelancers/search?';
    
    if (skills.length > 0) {
      endpoint += `skills=${skills.join(',')}&`;
    }
    
    if (maxRate) {
      endpoint += `max_rate=${maxRate}&`;
    }
    
    if (minRating) {
      endpoint += `min_rating=${minRating}`;
    }
    
    return await fetchAPI(endpoint);
  },
  
  // Get earnings data
  async getEarnings() {
    return await fetchAPI('/earnings');
  },
  
  // Request withdrawal
  async requestWithdrawal(amount, paymentMethod, paymentDetails) {
    return await fetchAPI('/withdraw', 'POST', {
      amount,
      payment_method: paymentMethod,
      payment_details: paymentDetails
    });
  }
};

// Admin Functions
const AdminManager = {
  // Process a withdrawal request
  async processWithdrawal(withdrawalId) {
    return await fetchAPI(`/admin/withdrawals/${withdrawalId}/process`, 'POST');
  }
};

// Usage Examples:

// Example 1: Register a new user
async function registerExample() {
  console.log('Registering a new freelancer...');
  const result = await UserAuth.register(
    'johndoe', 
    'password123', 
    'freelancer',
    ['JavaScript', 'React', 'Node.js'],
    25
  );
  console.log('Registration result:', result);
}

// Example 2: Login
async function loginExample() {
  console.log('Logging in...');
  const result = await UserAuth.login('johndoe', 'password123');
  console.log('Login result:', result);
}

// Example 3: Post a job
async function postJobExample() {
  console.log('Posting a new job...');
  const result = await JobManager.postJob(
    'Web Development Project',
    'Need a responsive website built with React',
    ['JavaScript', 'React', 'CSS'],
    1000,
    '2025-05-30'
  );
  console.log('Job posting result:', result);
}

// Example 4: Search for freelancers
async function searchFreelancersExample() {
  console.log('Searching for freelancers...');
  const result = await FreelancerManager.searchFreelancers(['JavaScript'], 30, 4);
  console.log('Found freelancers:', result);
}

// Example 5: Get earnings data and display chart
async function displayEarningsChart() {
  console.log('Getting earnings data...');
  const result = await FreelancerManager.getEarnings();
  
  if (result.success) {
    console.log('Earnings data:', result);
    
    // This would create a chart similar to what's in dashboard.html
    if (typeof Chart !== 'undefined') {
      const labels = Object.keys(result.earnings_by_month);
      const values = Object.values(result.earnings_by_month);
      
      new Chart(document.getElementById('earningsChart'), {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Earnings ($)',
            data: values,
            backgroundColor: '#3498db'
          }]
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true
            }
          }
        }
      });
    }
  }
}

// Run the examples
// Note: In a real application, these would be triggered by user actions
function runExamples() {
  // Uncomment these to test individual functions
  // registerExample();
  // loginExample();
  // postJobExample();
  // searchFreelancersExample();
  // displayEarningsChart();
  
  console.log("Skill Match Platform API Demo initialized!");
  console.log("Uncomment the example functions to test individual API calls.");
}

// Initialize when the document is loaded
document.addEventListener('DOMContentLoaded', runExamples);
