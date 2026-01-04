// Global variables
let currentReportType = null;
let currentImageFile = null;

// DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// Initialize the application
function initializeApp() {
    setupNavigation();
    setupReportCards();
    setupForms();
    setupImagePreview();
    setupModal();
    setupSearch();
    setupScrollTop();
    setupScrollAnimations();
    loadHeroStats();
    // Statistics are loaded on demand when needed
}

// Setup Navigation
function setupNavigation() {
    const navLinks = document.querySelectorAll('.nav-link');
    const navToggle = document.querySelector('.navbar-toggle');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            if (link.getAttribute('href').startsWith('#')) {
                e.preventDefault();
                const targetId = link.getAttribute('href').substring(1);
                const targetSection = document.getElementById(targetId);
                
                if (targetSection) {
                    targetSection.scrollIntoView({ behavior: 'smooth' });
                    
                    // Update active state
                    navLinks.forEach(l => l.classList.remove('active'));
                    link.classList.add('active');
                }
            }
        });
    });
    
    // Mobile menu toggle
    if (navToggle) {
        navToggle.addEventListener('click', () => {
            const navbarMenu = document.querySelector('.navbar-menu');
            navbarMenu.classList.toggle('active');
        });
    }
    
    // Smooth scrolling for all anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Setup Report Cards
function setupReportCards() {
    const reportCards = document.querySelectorAll('.report-type-card');
    
    reportCards.forEach(card => {
        card.addEventListener('click', () => {
            currentReportType = card.getAttribute('data-type');
            
            // Update active state
            reportCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            
            showReportForm();
        });
    });
}

// Show Report Form
function showReportForm() {
    const formContainer = document.getElementById('report-form');
    const formTitle = document.getElementById('form-title');
    const formSubtitle = document.getElementById('form-subtitle');
    
    if (formContainer) {
        formContainer.style.display = 'block';
        formContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Update form title based on report type
        if (formTitle && formSubtitle) {
            if (currentReportType === 'lost') {
                formTitle.textContent = 'Report Lost Item';
                formSubtitle.textContent = 'Please provide detailed information about the item you lost';
            } else if (currentReportType === 'found') {
                formTitle.textContent = 'Report Found Item';
                formSubtitle.textContent = 'Please provide detailed information about the item you found';
            }
        }
    }
}

// Hide Report Form
function hideReportForm() {
    const formContainer = document.getElementById('report-form');
    const resultsContainer = document.getElementById('report-results');
    
    if (formContainer) {
        formContainer.style.display = 'none';
    }
    if (resultsContainer) {
        resultsContainer.style.display = 'none';
    }
    
    // Reset form
    const itemForm = document.getElementById('item-form');
    const imagePreview = document.getElementById('image-preview');
    
    if (itemForm) {
        itemForm.reset();
    }
    if (imagePreview) {
        imagePreview.innerHTML = '';
    }
    
    currentImageFile = null;
    currentReportType = null;
    
    // Remove active state from report cards
    document.querySelectorAll('.report-type-card').forEach(card => card.classList.remove('active'));
}

// Load Hero Statistics
async function loadHeroStats() {
    try {
        const response = await fetch('/api/stats');
        const result = await response.json();
        
        if (result.success) {
            const stats = result.stats;
            const resolutionRate = stats.total_reports > 0 ? ((stats.resolved_count / stats.total_reports) * 100).toFixed(0) : 0;
            
            // Update pie chart numbers with real data
            animateNumber('total-reports', stats.total_reports);
            animateNumber('lost-items', stats.lost_count);
            animateNumber('found-items', stats.found_count);
            animateNumber('resolved-reports', stats.resolved_count);
            animateNumber('matched-reports', stats.matched_count);
            animateNumber('resolution-rate', resolutionRate + '%');
            
            // Update pie chart visual percentages
            updatePieCharts(stats);
        }
    } catch (error) {
        console.error('Error loading hero stats:', error);
    }
}

// Animate number counting
function animateNumber(elementId, targetValue) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const isPercentage = targetValue.toString().includes('%');
    const numericValue = parseInt(targetValue.toString().replace('%', ''));
    
    let currentValue = 0;
    const increment = numericValue / 50; // 50 steps
    const timer = setInterval(() => {
        currentValue += increment;
        if (currentValue >= numericValue) {
            currentValue = numericValue;
            clearInterval(timer);
        }
        element.textContent = Math.floor(currentValue) + (isPercentage ? '%' : '');
    }, 30);
}

// Update pie charts with real data percentages
function updatePieCharts(stats) {
    const total = stats.total_reports;
    
    if (total === 0) {
        // If no data, show empty charts
        updatePieChart('total-reports-chart', 0);
        updatePieChart('lost-items-chart', 0);
        updatePieChart('found-items-chart', 0);
        updatePieChart('resolved-chart', 0);
        updatePieChart('matched-chart', 0);
        updatePieChart('resolution-rate-chart', 0);
        return;
    }
    
    // Calculate percentages
    const lostPercentage = (stats.lost_count / total) * 100;
    const foundPercentage = (stats.found_count / total) * 100;
    const resolvedPercentage = (stats.resolved_count / total) * 100;
    const matchedPercentage = (stats.matched_count / total) * 100;
    const resolutionRatePercentage = (stats.resolved_count / total) * 100;
    
    // Update each pie chart
    updatePieChart('total-reports-chart', 100); // Always 100% for total
    updatePieChart('lost-items-chart', lostPercentage);
    updatePieChart('found-items-chart', foundPercentage);
    updatePieChart('resolved-chart', resolvedPercentage);
    updatePieChart('matched-chart', matchedPercentage);
    updatePieChart('resolution-rate-chart', resolutionRatePercentage);
}

// Update individual pie chart
function updatePieChart(chartId, percentage) {
    const chart = document.getElementById(chartId);
    if (!chart) return;
    
    // Create conic gradient based on percentage
    const degree = (percentage / 100) * 360;
    const color = getChartColor(chartId);
    
    chart.style.background = `conic-gradient(${color} 0deg ${degree}deg, #e5e7eb ${degree}deg 360deg)`;
}

// Get color for each chart
function getChartColor(chartId) {
    const colors = {
        'total-reports-chart': '#2563eb',
        'lost-items-chart': '#3b82f6',
        'found-items-chart': '#059669',
        'resolved-chart': '#7c3aed',
        'matched-chart': '#10b981',
        'resolution-rate-chart': '#0891b2'
    };
    return colors[chartId] || '#2563eb';
}

// Forms Setup
function setupForms() {
    // Item Report Form
    const itemForm = document.getElementById('item-form');
    if (itemForm) {
        itemForm.addEventListener('submit', handleItemSubmit);
    }
    
    // Chat Form
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }
    
    // Admin Login Form
    const adminLoginForm = document.getElementById('admin-login-form');
    if (adminLoginForm) {
        adminLoginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            adminLogin();
        });
    }
}

// Handle Item Form Submission
async function handleItemSubmit(e) {
    e.preventDefault();
    
    if (!currentReportType) {
        showToast('warning', 'Please select Lost or Found first');
        return;
    }
    
    const formData = new FormData(e.target);
    const data = {
        name: formData.get('name'),
        contact: formData.get('contact'),
        description: formData.get('description'),
        status: currentReportType.charAt(0).toUpperCase() + currentReportType.slice(1),
        secret: formData.get('secret') || ''
    };
    
    // Handle image
    if (currentImageFile) {
        const reader = new FileReader();
        reader.onload = async function(e) {
            data.image = e.target.result;
            await submitReport(data);
        };
        reader.readAsDataURL(currentImageFile);
    } else {
        await submitReport(data);
    }
}

// Submit Report
async function submitReport(data) {
    showLoading(true);
    
    try {
        const response = await fetch('/api/report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('success', result.message);
            displayReportResults(result);
            document.getElementById('item-form').reset();
            document.getElementById('image-preview').innerHTML = '';
            currentImageFile = null;
            loadStatistics(); // Refresh stats
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to submit report. Please try again.');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Display Report Results
function displayReportResults(result) {
    const resultsContainer = document.getElementById('report-results');
    let html = `
        <div class="match-card">
            <h4><i class="fas fa-check-circle"></i> Report Submitted Successfully!</h4>
            <p><strong>Category:</strong> ${result.category}</p>
            <p><strong>Status:</strong> ${result.status}</p>
    `;
    
    if (result.matches > 0) {
        html += `
            <div style="margin-top: 25px;">
                <h5 style="color: #10b981; font-size: 1.2em; margin-bottom: 15px;">
                    <i class="fas fa-link"></i> Found ${result.matches} Match(es)!
                </h5>
        `;
        
        result.match_details.forEach((match, index) => {
            html += `
                <div style="background: #f8fafc; padding: 20px; border-radius: 12px; margin: 15px 0; border-left: 4px solid #10b981;">
                    <p><strong>Match ${index + 1}:</strong></p>
                    <p><strong>Description:</strong> ${match.description}</p>
                    <p><strong>Contact:</strong> ${match.contact}</p>
                    <p><strong>Reporter:</strong> ${match.name}</p>
                </div>
            `;
        });
        
        html += `
                <p style="color: #10b981; font-weight: 600; margin-top: 20px;">
                    <i class="fas fa-envelope"></i> 
                    ${result.email_sent ? 'Email notifications have been sent to all parties!' : 'Notifications will be sent if email is configured.'}
                </p>
            </div>
        `;
    } else {
        html += `
            <p style="color: #64748b; margin-top: 20px;">
                <i class="fas fa-info-circle"></i> 
                No matches found at this time. Your report has been saved and we'll notify you if a match is found.
            </p>
        `;
    }
    
    html += '</div>';
    resultsContainer.innerHTML = html;
    resultsContainer.style.display = 'block';
    resultsContainer.scrollIntoView({ behavior: 'smooth' });
}

// Handle Chat Form Submission
async function handleChatSubmit(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = {
        sender_name: formData.get('sender-name'),
        sender_email: formData.get('sender-email'),
        receiver_email: formData.get('receiver-email'),
        message: formData.get('message')
    };
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('success', result.message);
            e.target.reset();
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to send message. Please try again.');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Setup Search
function setupSearch() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('search-input');
    
    if (searchBtn) {
        searchBtn.addEventListener('click', performSearch);
    }
    
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }
    
    // Setup category search buttons
    const categoryCards = document.querySelectorAll('.category-card');
    categoryCards.forEach(card => {
        card.addEventListener('click', () => {
            const category = card.getAttribute('data-category');
            if (searchInput) {
                searchInput.value = category;
                performSearch();
            }
        });
    });
}

// Perform Search
async function performSearch() {
    const searchInput = document.getElementById('search-input');
    const query = searchInput.value.trim();
    
    if (!query) {
        showToast('warning', 'Please enter a search term');
        return;
    }
    
    showLoading(true);
    
    try {
        // Add cache-busting timestamp to ensure fresh results
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/search?t=${timestamp}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            },
            body: JSON.stringify({ query })
        });
        
        const result = await response.json();
        
        if (result.success) {
            displaySearchResults(result.results);
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Search failed. Please try again.');
        console.error('Error:', error);
    } finally {
        showLoading(false);
    }
}

// Force refresh search results
async function refreshSearchResults() {
    try {
        const response = await fetch('/api/search/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        });
        
        const result = await response.json();
        if (result.success) {
            // Search results refreshed
        }
    } catch (error) {
        // Error refreshing search
    }
}

// Display Search Results
function displaySearchResults(results) {
    const resultsContainer = document.getElementById('search-results');
    
    if (results.length === 0) {
        resultsContainer.innerHTML = '<p style="text-align: center; color: #64748b; padding: 40px;">No matches found. Try different search terms.</p>';
        return;
    }
    
    let html = `<h3 style="color: #1e40af; margin-bottom: 30px; font-size: 1.5em;">Found ${results.length} match(es):</h3>`;
    
    results.forEach(result => {
        const statusClass = result.status.toLowerCase();
        const statusEmoji = result.status === 'Lost' ? '🔴' : '🟢';
        
        const resolvedBadge = result.resolved ? '<span class="resolved-badge">✅ Resolved by Admin</span>' : '';
        
        html += `
            <div class="result-card ${result.resolved ? 'resolved-card' : ''}">
                <div class="result-header">
                    <span class="result-status status-${statusClass}">${statusEmoji} ${result.status}</span>
                    <span class="result-score">${result.score.toFixed(1)}% match</span>
                    ${resolvedBadge}
                </div>
                <div class="result-content">
                    <p><strong>Description:</strong> ${result.description}</p>
                    <p><strong>Contact:</strong> ${result.contact}</p>
                    <p><strong>Reporter:</strong> ${result.name}</p>
                    <p><strong>Reported:</strong> ${result.timestamp}</p>
                    ${result.category ? `<p><strong>Category:</strong> ${result.category}</p>` : ''}
                    ${result.secret ? `<p><strong>Secret Detail:</strong> ${result.secret}</p>` : ''}
                </div>
                ${result.image ? `
                    <div class="result-image">
                        <img src="data:image/jpeg;base64,${result.image}" alt="Item Image">
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

// Load Statistics
async function loadStatistics() {
    try {
        // Use public stats endpoint for homepage, admin stats for admin panel
        const endpoint = window.location.pathname.includes('/admin') ? '/api/admin/stats' : '/api/stats';
        const response = await fetch(endpoint);
        const result = await response.json();
        
        if (result.success) {
            if (window.location.pathname.includes('/admin')) {
                displayAdminStatistics(result.stats);
            }
            // Also update hero pie charts
            updatePieCharts(result.stats);
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to load statistics.');
        console.error('Error:', error);
    }
}

function displayAdminStatistics(stats) {
    const content = document.getElementById('admin-content');
    
    const resolutionRate = stats.total_reports > 0 ? ((stats.resolved_count / stats.total_reports) * 100).toFixed(1) : 0;
    const matchRate = stats.total_reports > 0 ? ((stats.matched_count / stats.total_reports) * 100).toFixed(1) : 0;
    
    let html = `
        <h3><i class="fas fa-chart-bar"></i> System Statistics</h3>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-list"></i>
                </div>
                <div class="stat-info">
                    <h3>${stats.total_reports}</h3>
                    <p>Total Reports</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="stat-info">
                    <h3>${stats.lost_count}</h3>
                    <p>Lost Items</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="stat-info">
                    <h3>${stats.found_count}</h3>
                    <p>Found Items</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-check"></i>
                </div>
                <div class="stat-info">
                    <h3>${stats.resolved_count}</h3>
                    <p>Resolved Reports</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-link"></i>
                </div>
                <div class="stat-info">
                    <h3>${stats.matched_count}</h3>
                    <p>Matched Reports</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">
                    <i class="fas fa-percentage"></i>
                </div>
                <div class="stat-info">
                    <h3>${resolutionRate}%</h3>
                    <p>Resolution Rate</p>
                </div>
            </div>
        </div>
        
        <div class="stats-summary">
            <h4><i class="fas fa-info-circle"></i> Summary</h4>
            <div class="summary-cards">
                <div class="summary-card">
                    <h5>Active Reports</h5>
                    <p>${stats.total_reports - stats.resolved_count} reports pending resolution</p>
                </div>
                <div class="summary-card">
                    <h5>Match Rate</h5>
                    <p>${matchRate}% of reports have been matched</p>
                </div>
                <div class="summary-card">
                    <h5>System Health</h5>
                    <p>${resolutionRate >= 70 ? 'Excellent' : resolutionRate >= 50 ? 'Good' : 'Needs Improvement'}</p>
                </div>
            </div>
        </div>
    `;
    
    content.innerHTML = html;
}

// Image Preview Setup
function setupImagePreview() {
    const imageInput = document.getElementById('image');
    if (imageInput) {
        imageInput.addEventListener('change', handleImagePreview);
    }
}

// Handle Image Preview
function handleImagePreview(e) {
    const file = e.target.files[0];
    if (file) {
        currentImageFile = file;
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('image-preview');
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        };
        reader.readAsDataURL(file);
    }
}

// Image Modal Functions
function showImageModal(imageSrc) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    if (modal && modalImg) {
        modal.style.display = 'flex';
        modalImg.src = imageSrc;
    }
}

function hideImageModal() {
    const modal = document.getElementById('image-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Modal Setup
function setupModal() {
    const modal = document.getElementById('image-modal');
    const closeBtn = document.querySelector('.close');
    
    if (closeBtn) {
        closeBtn.addEventListener('click', hideImageModal);
    }
    
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                hideImageModal();
            }
        });
    }
}

// Setup Scroll to Top
function setupScrollTop() {
    const scrollTopBtn = document.getElementById('scroll-top');
    
    if (scrollTopBtn) {
        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                scrollTopBtn.classList.add('show');
            } else {
                scrollTopBtn.classList.remove('show');
            }
        });
        
        scrollTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// Setup Scroll Animations
function setupScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);
    
    // Add fade-in-section class to sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.add('fade-in-section');
        observer.observe(section);
    });
    
    // Add fade-in class to cards
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('fade-in-section');
        observer.observe(card);
    });
}

// Show Loading Spinner
function showLoading(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.style.display = show ? 'flex' : 'none';
    }
}

// Show Toast Notification
function showToast(type, message) {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.className = `toast ${type}`;
        // Ensure it's above scrollbars and visible within viewport
        toast.style.position = 'fixed';
        toast.style.top = '20px';
        toast.style.right = '24px';
        toast.style.left = 'auto';
        toast.style.zIndex = '4000';
        toast.style.maxWidth = '80vw';
        toast.style.pointerEvents = 'none';
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
}

// Load statistics for footer and hero section

// Admin Functions

async function adminLogout() {
    try {
        // Show confirmation
        if (!confirm('Are you sure you want to logout from admin dashboard?')) {
            return;
        }
        
        const response = await fetch('/api/admin/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('success', 'Logged out successfully!');
            // Redirect to home page or login page after logout
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else {
            showToast('error', result.message || 'Logout failed');
        }
    } catch (error) {
        showToast('error', 'Logout failed. Please try again.');
        console.error('Error:', error);
    }
}

async function loadAllReports() {
    try {
        const response = await fetch('/api/admin/reports');
        const result = await response.json();
        
        if (result.success) {
            displayAdminReports(result.reports, 'All Reports');
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to load reports.');
        console.error('Error:', error);
    }
}

async function loadMatchedReports() {
    try {
        const response = await fetch('/api/admin/reports');
        const result = await response.json();
        
        if (result.success) {
            const matchedReports = result.reports.filter(report => report.matched === 1);
            displayMatchedReports(matchedReports);
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to load matched reports.');
        console.error('Error:', error);
    }
}

async function loadResolvedReports() {
    try {
        const response = await fetch('/api/admin/reports');
        const result = await response.json();
        
        if (result.success) {
            const resolvedReports = result.reports.filter(report => report.resolved === 1);
            displayResolvedReports(resolvedReports);
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to load resolved reports.');
        console.error('Error:', error);
    }
}

function displayMatchedReports(reports) {
    const content = document.getElementById('admin-content');
    
    if (reports.length === 0) {
        content.innerHTML = '<p>No matched reports found.</p>';
        return;
    }
    
    let html = `
        <h3><i class="fas fa-link"></i> Matched Reports (${reports.length})</h3>
        <div class="reports-grid">
    `;
    
    reports.forEach(report => {
        const statusEmoji = report.status === 'Lost' ? '🔴' : '🟢';
        
        html += `
            <div class="report-card matched">
                <div class="report-header">
                    <span class="status-badge ${report.status.toLowerCase()}">${statusEmoji} ${report.status}</span>
                    <span class="report-id">ID: ${report.id}</span>
                    <span class="matched-badge">Matched</span>
                </div>
                <div class="report-content">
                    <p><strong>Reporter:</strong> ${report.name}</p>
                    <p><strong>Contact:</strong> ${report.contact}</p>
                    <p><strong>Description:</strong> ${report.description}</p>
                    <p><strong>Category:</strong> ${report.category || 'Not categorized'}</p>
                    <p><strong>Reported:</strong> ${report.timestamp}</p>
                    ${report.secret ? `<p><strong>Secret Detail:</strong> ${report.secret}</p>` : ''}
                </div>
                <div class="report-actions">
                    <button data-report-id="${report.id}" data-report-description="${report.description.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" class="action-btn resolve-btn">
                        <i class="fas fa-check"></i> Resolve
                    </button>
                    <button data-report-id="${report.id}" data-report-description="${report.description.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" class="action-btn delete-btn">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                    <button onclick="sendNotification('${report.contact}', '${report.name}')" class="action-btn notify-btn">
                        <i class="fas fa-bell"></i> Notify
                    </button>
                </div>
                ${report.image && report.image.trim() !== '' ? `
                    <div class="report-image">
                        <img src="data:image/jpeg;base64,${report.image}" 
                             alt="Item Image">
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    content.innerHTML = html;
}

function displayResolvedReports(reports) {
    const content = document.getElementById('admin-content');
    
    if (reports.length === 0) {
        content.innerHTML = '<p>No resolved reports found.</p>';
        return;
    }
    
    let html = `
        <h3><i class="fas fa-check-circle"></i> Resolved Reports (${reports.length})</h3>
        <div class="reports-grid">
    `;
    
    reports.forEach(report => {
        const statusEmoji = report.status === 'Lost' ? '🔴' : '🟢';
        const resolvedText = report.resolved ? '<span style="color: #10b981;">✅ Resolved</span>' : '<span style="color: #ef4444;">❌ Unresolved</span>';
        const matchedText = report.matched ? '<span style="color: #3b82f6;">🔗 Matched</span>' : '<span style="color: #6b7280;">🔗 Not Matched</span>';
        
        html += `
            <div class="report-card resolved">
                <div class="report-header">
                    <span class="status-badge ${report.status.toLowerCase()}">${statusEmoji} ${report.status}</span>
                    <span class="report-id">ID: ${report.id}</span>
                    <span class="resolved-badge">Resolved</span>
                </div>
                <div class="report-content">
                    <p><strong>Reporter:</strong> ${report.name}</p>
                    <p><strong>Contact:</strong> ${report.contact}</p>
                    <p><strong>Description:</strong> ${report.description}</p>
                    <p><strong>Category:</strong> ${report.category || 'Not categorized'}</p>
                    <p><strong>Reported:</strong> ${report.timestamp}</p>
                    <p><strong>Status:</strong> ${resolvedText} | ${matchedText}</p>
                    ${report.secret ? `<p><strong>Secret Detail:</strong> ${report.secret}</p>` : ''}
                </div>
                <div class="report-actions">
                    <button data-report-id="${report.id}" data-report-description="${report.description.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" class="action-btn delete-btn">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                    <button onclick="sendNotification('${report.contact}', '${report.name}')" class="action-btn notify-btn">
                        <i class="fas fa-bell"></i> Notify
                    </button>
                </div>
                ${report.image && report.image.trim() !== '' ? `
                    <div class="report-image">
                        <img src="data:image/jpeg;base64,${report.image}" 
                             alt="Item Image">
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    content.innerHTML = html;
}

function displayAdminReports(reports, title) {
    const content = document.getElementById('admin-content');
    
    if (reports.length === 0) {
        content.innerHTML = '<p>No reports found.</p>';
        return;
    }
    
    let html = `
        <h3><i class="fas fa-list"></i> ${title} (${reports.length})</h3>
        <div class="reports-grid">
    `;
    
    reports.forEach(report => {
        const statusEmoji = report.status === 'Lost' ? '🔴' : '🟢';
        const resolvedText = report.resolved ? 'Resolved' : 'Pending';
        const matchedText = report.matched ? 'Matched' : 'Not Matched';
        
        html += `
            <div class="report-card">
                <div class="report-header">
                    <span class="status-badge ${report.status.toLowerCase()}">${statusEmoji} ${report.status}</span>
                    <span class="report-id">ID: ${report.id}</span>
                </div>
                <div class="report-content">
                    <p><strong>Reporter:</strong> ${report.name}</p>
                    <p><strong>Contact:</strong> ${report.contact}</p>
                    <p><strong>Description:</strong> ${report.description}</p>
                    <p><strong>Category:</strong> ${report.category || 'Not categorized'}</p>
                    <p><strong>Reported:</strong> ${report.timestamp}</p>
                    <p><strong>Status:</strong> ${resolvedText} | ${matchedText}</p>
                    ${report.secret ? `<p><strong>Secret Detail:</strong> ${report.secret}</p>` : ''}
                </div>
                <div class="report-actions">
                    ${!report.resolved ? `<button data-report-id="${report.id}" data-report-description="${report.description.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" class="action-btn resolve-btn">
                        <i class="fas fa-check"></i> Resolve
                    </button>` : ''}
                    <button data-report-id="${report.id}" data-report-description="${report.description.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" class="action-btn delete-btn">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                    <button onclick="sendNotification('${report.contact}', '${report.name}')" class="action-btn notify-btn">
                        <i class="fas fa-bell"></i> Notify
                    </button>
                </div>
                ${report.image && report.image.trim() !== '' ? `
                    <div class="report-image">
                        <img src="data:image/jpeg;base64,${report.image}" 
                             alt="Item Image">
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    content.innerHTML = html;
}

// Show delete confirmation modal
function showDeleteConfirmation(reportId, reportDescription) {
    // Check if the modal exists (it's defined in admin.html)
    const modal = document.getElementById('delete-confirmation-modal');
    
    if (!modal) {
        // Fallback to browser confirm if modal doesn't exist
        if (confirm(`Are you sure you want to delete report ${reportId}?\n\nDescription: ${reportDescription}\n\nThis action cannot be undone.`)) {
            deleteReport(reportId);
        }
        return;
    }
    
    // Use the custom modal
    document.getElementById('delete-report-id').textContent = reportId;
    document.getElementById('delete-report-description').textContent = reportDescription.substring(0, 100) + (reportDescription.length > 100 ? '...' : '');
    modal.style.display = 'flex';
    
    // Store report ID for deletion
    window.pendingDeleteReportId = reportId;
}

// Close delete confirmation modal
function closeDeleteConfirmation() {
    const modal = document.getElementById('delete-confirmation-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    window.pendingDeleteReportId = null;
}

// Confirm delete report
function confirmDeleteReport() {
    const reportId = window.pendingDeleteReportId;
    
    if (reportId) {
        closeDeleteConfirmation();
        deleteReport(reportId);
    } else {
        showToast('error', 'No report selected for deletion');
    }
}

// Show resolve confirmation modal
function showResolveConfirmation(reportId, reportDescription) {
    const modal = document.getElementById('resolve-confirmation-modal');
    
    if (!modal) {
        if (confirm(`Are you sure you want to resolve report ${reportId}?\n\nDescription: ${reportDescription}\n\nThis will mark the report as resolved.`)) {
            resolveReport(reportId);
        }
        return;
    }
    
    document.getElementById('resolve-report-id').textContent = reportId;
    document.getElementById('resolve-report-description').textContent = reportDescription.substring(0, 100) + (reportDescription.length > 100 ? '...' : '');
    modal.style.display = 'flex';
    
    window.pendingResolveReportId = reportId;
}

// Close resolve confirmation modal
function closeResolveConfirmation() {
    const modal = document.getElementById('resolve-confirmation-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    window.pendingResolveReportId = null;
}

// Confirm resolve report
function confirmResolveReport() {
    const reportId = window.pendingResolveReportId;
    
    if (reportId) {
        closeResolveConfirmation();
        resolveReport(reportId);
    } else {
        showToast('error', 'No report selected for resolution');
    }
}

async function deleteReport(reportId) {
    try {
        const response = await fetch(`/api/admin/delete/${reportId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('success', result.message);
            loadAllReports(); // Refresh the list
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to delete report.');
    }
}

async function resolveReport(reportId) {
    try {
        const response = await fetch(`/api/admin/resolve/${reportId}`, {
            method: 'PUT'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('success', result.message);
            loadAllReports(); // Refresh the list
        } else {
            showToast('error', result.message);
        }
    } catch (error) {
        showToast('error', 'Failed to resolve report.');
        console.error('Error:', error);
    }
}

// Global variables for chat modal
let currentChatContact = '';
let currentChatName = '';

async function sendNotification(contact, name) {
    // Open the chat modal
    currentChatContact = contact;
    currentChatName = name;
    
    // Update the modal with user info
    document.getElementById('chat-user-name').textContent = name;
    document.getElementById('chat-user-contact').textContent = contact;
    
    // Clear the message input
    document.getElementById('chat-message-input').value = '';
    
    // Show the modal
    document.getElementById('chat-modal').style.display = 'flex';
}

function closeChatModal() {
    document.getElementById('chat-modal').style.display = 'none';
    currentChatContact = '';
    currentChatName = '';
}

function sendChatMessage() {
    const message = document.getElementById('chat-message-input').value.trim();
    
    if (!message) {
        showToast('error', 'Please enter a message');
        return;
    }
    
    if (!currentChatContact) {
        showToast('error', 'Invalid contact information');
        return;
    }
    
    showLoading(true);
    
    fetch('/api/admin/notify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ contact: currentChatContact, message })
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showToast('success', 'Message sent successfully!');
            closeChatModal();
        } else {
            showToast('error', result.message);
        }
    })
    .catch(error => {
        showToast('error', 'Failed to send message');
        console.error('Error:', error);
    })
    .finally(() => {
        showLoading(false);
    });
}
