const API_BASE_URL = "https://gclearnbot.onrender.com"; 
const PROTECTED_ROUTES = ['/web/dashboard.html', '/web/journal.html', '/web/progress.html'];

// Initialize the app
async function initializeApp() {
    const token = getAuthToken();
    if (token) {
        document.getElementById('loginSection')?.classList.add('is-hidden');
        document.getElementById('dashboardSection')?.classList.remove('is-hidden');
        await fetchLessons();
    } else {
        document.getElementById('loginSection')?.classList.remove('is-hidden');
        document.getElementById('dashboardSection')?.classList.add('is-hidden');
        initializeAuthDisplay();
    }

    initializeMobileMenu();
}

// Auth toggle functions
function toggleAuth() {
    const registerBox = document.getElementById('registerBox');
    const loginBox = document.getElementById('loginBox');

    if (registerBox.classList.contains('is-hidden')) {
        registerBox.classList.remove('is-hidden');
        loginBox.classList.add('is-hidden');
    } else {
        registerBox.classList.add('is-hidden');
        loginBox.classList.remove('is-hidden');
    }
}

// Initialize auth display state
function initializeAuthDisplay() {
    if (!localStorage.getItem('returning')) {
        document.getElementById('registerBox').classList.remove('is-hidden');
        document.getElementById('loginBox').classList.add('is-hidden');
        localStorage.setItem('returning', 'true');
    } else {
        document.getElementById('registerBox').classList.add('is-hidden');
        document.getElementById('loginBox').classList.remove('is-hidden');
    }
}

async function initializeProtectedPage() {
    if (!checkAuth()) {
        document.getElementById('protectedContent')?.classList.add('is-hidden');
        document.getElementById('notSignedIn')?.classList.remove('is-hidden');
        return;
    }
    
    document.getElementById('protectedContent')?.classList.remove('is-hidden');
    document.getElementById('notSignedIn')?.classList.add('is-hidden');
    
    // Initialize based on current page
    const currentPath = window.location.pathname;
    
    try {
        if (currentPath.includes('dashboard.html')) {
            await fetchLessons();
            await fetchProgress();
        } else if (currentPath.includes('progress.html')) {
            await fetchProgress();
        } else if (currentPath.includes('journal.html')) {
            await fetchJournal();
        }
    } catch (error) {
        console.error('Error initializing page:', error);
        showError('Error loading page content. Please refresh the page.');
    }
    
    initializeMobileMenu();
    updateAuthNavigation();
}

// Mobile menu functionality (Bulma)
function initializeMobileMenu() {
    // Get all "navbar-burger" elements
    const burgers = document.querySelectorAll('.navbar-burger');
    
    // Add click event to each burger
    burgers.forEach(burger => {
        burger.addEventListener('click', function() {
            // Get the target from the "data-target" attribute
            const targetId = this.dataset.target;
            const target = document.getElementById(targetId);
            
            // Toggle the class on both the burger and menu
            this.classList.toggle('is-active');
            target?.classList.toggle('is-active');
        });
    });
}

// Check if user is signed in, else redirect to homepage
function checkAuth() {
    const token = getAuthToken();
    const currentPath = window.location.pathname;
    
    if (token && isTokenExpired(token)) {
        localStorage.removeItem('token');
        window.location.href = '/web/index.html';
        return false;
    }

    // If on a protected route and not authenticated
    const protectedRoutes = ['/web/dashboard.html', '/web/journal.html', '/web/progress.html'];
    if (protectedRoutes.includes(currentPath) && !token) {
        window.location.href = '/web/index.html';
        return false;
    }
    
    // If authenticated and on login page, redirect to dashboard
    if (token && currentPath === '/web/index.html') {
        window.location.href = '/web/dashboard.html';
        return true;
    }
    
    return !!token;
}

// Check if user is logged in; if so, redirect from index.html to dashboard
function checkRedirect() {
    if (getAuthToken()) {
        window.location.href = "/web/dashboard.html";
    }
}

function updateAuthNavigation() {
    const token = getAuthToken();
    const authLinks = document.querySelectorAll('.auth-links');
    const logoutButtons = document.querySelectorAll('.logout-button');
    const loginButtons = document.querySelectorAll('.login-button');
    
    if (token) {
        // Show authenticated links
        authLinks.forEach(link => link.classList.remove('is-hidden'));
        logoutButtons.forEach(button => button.classList.remove('is-hidden'));
        loginButtons.forEach(button => button.classList.add('is-hidden'));
    } else {
        // Hide authenticated links
        authLinks.forEach(link => link.classList.add('is-hidden'));
        logoutButtons.forEach(button => button.classList.add('is-hidden'));
        loginButtons.forEach(button => button.classList.remove('is-hidden'));
    }
}

// Initialize app and manage login state
async function initializeApp() {
    const token = getAuthToken();
    if (token) {
        document.getElementById('loginSection')?.classList.add('is-hidden');
        document.getElementById('dashboardSection')?.classList.remove('is-hidden');
        await fetchLessons();
    } else {
        document.getElementById('loginSection')?.classList.remove('is-hidden');
        document.getElementById('dashboardSection')?.classList.add('is-hidden');
        initializeAuthDisplay();
    }

    initializeMobileMenu();
}

// Register user with improved error handling
async function registerUser(event) {
    event?.preventDefault(); // Prevent form submission
    disableForm('registerForm');
    
    const registerButton = document.getElementById('registerButton');
    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;

    // Add loading state
    registerButton.classList.add('is-loading');

    try {
        const response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.status === 409) {
            showError("This email is already registered. Please try logging in instead.");
            return;
        }

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            showSuccess("Registration successful! Redirecting...");
            setTimeout(() => {
                window.location.href = '/web/dashboard.html';
            }, 1000);
        } else {
            showError(data.message || "Registration failed. Please try again.");
        }
    } catch (error) {
        showError("Registration failed. Please try again.");
    } finally {
        registerButton.classList.remove('is-loading');
        enableForm('registerForm');
    }
}

// Add this to prevent double submission
function disableForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        const inputs = form.getElementsByTagName('input');
        const buttons = form.getElementsByTagName('button');
        
        // Disable all inputs
        for (let input of inputs) {
            input.disabled = true;
        }
        
        // Disable all buttons
        for (let button of buttons) {
            button.disabled = true;
            button.classList.add('is-loading');
        }
    }
}

function enableForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        const inputs = form.getElementsByTagName('input');
        const buttons = form.getElementsByTagName('button');
        
        // Enable all inputs
        for (let input of inputs) {
            input.disabled = false;
        }
        
        // Enable all buttons
        for (let button of buttons) {
            button.disabled = false;
            button.classList.remove('is-loading');
        }
    }
}

// Login user with improved error handling
async function loginUser(event) {
    event?.preventDefault(); // Prevent form submission
    disableForm('loginForm');
    
    const loginButton = document.getElementById('loginButton');
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    // Add loading state
    loginButton.classList.add('is-loading');

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.status === 404) {
            showError("This email is not registered. Please sign up first.");
            return;
        }

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            showSuccess("Login successful! Redirecting...");
            setTimeout(() => {
                window.location.href = '/web/dashboard.html';
            }, 1000);
        } else {
            showError(data.message || "Login failed. Please check your credentials.");
        }
    } catch (error) {
        showError("Login failed. Please try again.");
    } finally {
        loginButton.classList.remove('is-loading');
        enableForm('loginForm');
    }
}

// Logout user
function logoutUser() {
    localStorage.removeItem("token");
    window.location.href = "/web/index.html"; // Redirect to homepage
}

function disableForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        const inputs = form.getElementsByTagName('input');
        const buttons = form.getElementsByTagName('button');
        
        // Disable all inputs
        for (let input of inputs) {
            input.disabled = true;
        }
        
        // Disable all buttons
        for (let button of buttons) {
            button.disabled = true;
            button.classList.add('is-loading');
        }
    }
}

function enableForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        const inputs = form.getElementsByTagName('input');
        const buttons = form.getElementsByTagName('button');
        
        // Enable all inputs
        for (let input of inputs) {
            input.disabled = false;
        }
        
        // Enable all buttons
        for (let button of buttons) {
            button.disabled = false;
            button.classList.remove('is-loading');
        }
    }
}

// Get auth token from local storage
function getAuthToken() {
    return localStorage.getItem("token");
}

function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.add('is-loading');
    }
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.remove('is-loading');
    }
}

// Add better error handling
function showError(message, duration = 3000) {
    // Remove any existing notifications first
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());

    const errorDiv = document.createElement('div');
    errorDiv.className = 'notification is-danger';
    errorDiv.style.position = 'fixed';
    errorDiv.style.top = '20px';
    errorDiv.style.right = '20px';
    errorDiv.style.zIndex = '1000';
    errorDiv.innerHTML = `
        <button class="delete"></button>
        ${message}
    `;
    
    // Add to page
    document.body.appendChild(errorDiv);
    
    // Add close button functionality
    errorDiv.querySelector('.delete').addEventListener('click', () => {
        errorDiv.remove();
    });
    
    // Auto-remove after duration
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, duration);
}

// Add token expiration check
function isTokenExpired(token) {
    if (!token) return true;
    
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const payload = JSON.parse(window.atob(base64));
        
        return payload.exp ? Date.now() >= payload.exp * 1000 : false;
    } catch (e) {
        return true;
    }
}

// Fetch user progress
async function fetchUserProgress() {
    let token = getAuthToken();
    if (!token) {
        showError("Please log in first.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/progress`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });

        let data = await response.json();
        console.log(data);
    } catch (error) {
        console.error("Error fetching progress:", error);
    }
}

// Load lessons
async function loadLesson(lessonId) {
    const lessonCard = document.getElementById('lessonCard');
    const lessonTitle = document.getElementById('lessonTitle');
    const lessonContent = document.getElementById('lessonContent');
    const responseCard = document.getElementById('responseCard');
    const lessonSelectCard = document.getElementById('lessonSelectCard');

    try {
        const response = await fetch(`${API_BASE_URL}/lessons/${lessonId}`, {
            headers: {
                "Authorization": `Bearer ${getAuthToken()}`,
                "Content-Type": "application/json"
            }
        });

        const data = await response.json();

        if (data.status === "success" && data.lesson) {
            // Fade out selector
            lessonSelectCard.classList.add('fade-out');
            setTimeout(() => {
                lessonSelectCard.classList.add('is-hidden');
                
                // Update lesson content
                lessonTitle.textContent = data.lesson.title || `Lesson ${lessonId.split('_')[1]}`;
                
                // Create a scrollable content area
                lessonContent.style.maxHeight = '400px'; // Set a fixed height
                lessonContent.style.overflowY = 'auto';  // Make it scrollable
                lessonContent.innerHTML = formatLessonContent(data.lesson.text);
                
                // Show lesson card
                lessonCard.classList.remove('is-hidden');
                lessonCard.classList.add('fade-in');

                // Show response form if needed
                if (data.lesson.requires_response) {
                    responseCard.classList.remove('is-hidden');
                }

                // Show response form for steps (not main lessons)
                if (lessonId.includes('_step_')) {
                    responseCard.classList.remove('is-hidden');
                } else {
                    responseCard.classList.add('is-hidden');
                }

                // Update lesson navigation buttons
                updateLessonNavigation(lessonId, data.lesson.next);
            }, 300);
        }
    } catch (error) {
        console.error("Error loading lesson:", error);
        showError("Error loading lesson. Please try again.");
    }
}

// Format lesson content for web display
function formatLessonContent(text) {
    return text
        .replace(/\[([^\]]+)\]/g, '<$1>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .split('\n').join('<br>');
}

// Update lesson navigation buttons
function updateLessonNavigation(currentId, nextId) {
    if (!currentId) {
        console.error("updateLessonNavigation error: currentId is undefined");
        return;
    }

    const prevButton = document.getElementById('prevLesson');
    const nextButton = document.getElementById('nextLesson');

    const parts = currentId.split('_');
    if (parts.length < 2) {
        console.error("Invalid lesson ID format:", currentId);
        return;
    }

    const lessonNum = parts[1];
    const stepNum = parts[3] ? parseInt(parts[3]) : null;

    prevButton.disabled = !stepNum || stepNum === 1;
    nextButton.disabled = !nextId;

    prevButton.onclick = () => {
        if (stepNum && stepNum > 1) {
            const prevId = `lesson_${lessonNum}_step_${stepNum - 1}`;
            loadLesson(prevId);
        }
    };

    nextButton.onclick = () => {
        if (nextId) loadLesson(nextId);
    };
}

// Fetch and display lesson content
async function fetchLessons() {
    const token = getAuthToken();
    if (!token) {
        console.error("No auth token found");
        return;
    }

    try {
        console.log("Fetching lessons from:", `${API_BASE_URL}/lessons`);

        const response = await fetch(`${API_BASE_URL}/lessons`, {
            method: "GET",
            headers: { 
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            }
        });

        console.log("Response Status:", response.status);

        const data = await response.json();
        console.log("Raw API Response:", data);
        
        if (data.status === "success" && Array.isArray(data.lessons)) {
            console.log("Total Lessons Fetched:", data.lessons.length);

            // Debugging: Log all lessons
            console.log("Lessons Data:", JSON.stringify(data.lessons, null, 2));

            const selectElement = document.getElementById('lessonSelect');
            if (!selectElement) return;

            selectElement.innerHTML = '<option value="">What would you like to learn?</option>';

            const mainLessons = data.lessons.filter(lesson => {
                return (
                    lesson.lesson_id !== "lesson_1" && 
                    !lesson.lesson_id.includes("_step_") &&
                    !lesson.lesson_id.toLowerCase().includes("congratulations")
                );
            });
            
            console.log("Filtered Lessons After Debugging:", mainLessons);

            // Sorting
            const sortedLessons = mainLessons.sort((a, b) => {
                const aNum = parseInt(a.lesson_id.split('_')[1]) || 0;
                const bNum = parseInt(b.lesson_id.split('_')[1]) || 0;
                return aNum - bNum;
            });

            console.log("Sorted Lessons:", sortedLessons);

            sortedLessons.forEach(lesson => {
                if (lesson.lesson_id && lesson.title) {
                    const option = document.createElement('option');
                    option.value = lesson.lesson_id;
                    option.textContent = `📚 ${lesson.title}`;
                    selectElement.appendChild(option);
                }
            });
        }
    } catch (error) {
        console.error("Error fetching lessons:", error);
        const selectElement = document.getElementById('lessonSelect');
        if (selectElement) {
            selectElement.innerHTML = '<option value="">Error loading lessons. Please try again.</option>';
        }
    }
}

// Submit user response with feedback display
async function submitResponse(event) {
    event.preventDefault();
    
    const lessonSelect = document.getElementById("lessonSelect");
    const responseInput = document.getElementById("responseText");
    const submitButton = document.getElementById('submitButton');
    const feedbackCard = document.getElementById('feedbackCard');
    
    if (!lessonSelect || !responseInput || !submitButton) {
        console.error('Required form elements not found');
        showError('Error submitting response. Please refresh the page.');
        return;
    }
    
    const lessonId = lessonSelect.value;
    const responseText = responseInput.value;
    const token = getAuthToken();
    
    if (!token) {
        showError("Please log in first.");
        return;
    }

    // Show loading state
    submitButton.classList.add('is-loading');

    try {
        const response = await fetch(`${API_BASE_URL}/lessons/${lessonId}/response`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ response: responseText })
        });

        const data = await response.json();
        
        if (data.status === "success") {
            // Show feedback card if it exists
            if (feedbackCard) {
                feedbackCard.classList.remove('is-hidden');
            }

            // Update quality metrics if elements exist
            const responseQuality = document.getElementById('responseQuality');
            if (responseQuality) {
                responseQuality.textContent = `${data.quality_metrics?.overall_score || 0}%`;
            }

            // Update keywords if element exists
            const keywordsList = document.getElementById('keywordsList');
            if (keywordsList && data.quality_metrics?.keywords_used) {
                keywordsList.innerHTML = data.quality_metrics.keywords_used
                    .map(keyword => `<span class="tag is-primary is-light">${keyword}</span>`)
                    .join('');
            }

            // Update detailed feedback if element exists
            const feedbackContent = document.getElementById('feedbackContent');
            if (feedbackContent) {
                feedbackContent.innerHTML = data.feedback
                    .map(item => `<p>• ${item}</p>`)
                    .join('');
            }

            // Update skill progress if elements exist
            if (data.skills) {
                const skillsList = document.getElementById('skillsList');
                if (skillsList) {
                    skillsList.innerHTML = Object.entries(data.skills)
                        .map(([skill, details]) => `
                            <div class="mb-3">
                                <div class="level is-mobile mb-1">
                                    <div class="level-left">
                                        <span class="has-text-weight-medium">${skill}</span>
                                    </div>
                                    <div class="level-right">
                                        <span class="has-text-grey">${details.score}%</span>
                                    </div>
                                </div>
                                <progress 
                                    class="progress is-success" 
                                    value="${details.score}" 
                                    max="100"
                                ></progress>
                            </div>
                        `).join('');
                }
            }

            // Clear the response text
            responseInput.value = '';
            
            // Scroll to feedback if it exists
            if (feedbackCard) {
                feedbackCard.scrollIntoView({ behavior: 'smooth' });
            }
        } else {
            showError(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error("Error submitting response:", error);
        showError("Something went wrong. Please try again.");
    } finally {
        submitButton.classList.remove('is-loading');
    }
}

function showSuccess(message, duration = 3000) {
    const successDiv = document.createElement('div');
    successDiv.className = 'notification is-success';
    successDiv.style.position = 'fixed';
    successDiv.style.top = '20px';
    successDiv.style.right = '20px';
    successDiv.style.zIndex = '1000';
    successDiv.innerHTML = `
        <button class="delete"></button>
        ${message}
    `;
    
    // Add to page
    document.body.appendChild(successDiv);
    
    // Add close button functionality
    successDiv.querySelector('.delete').addEventListener('click', () => {
        successDiv.remove();
    });
    
    // Auto-remove after duration
    setTimeout(() => {
        if (successDiv.parentNode) {
            successDiv.remove();
        }
    }, duration);
}

// Fetch user progress
async function fetchProgress() {
    try {
        const token = getAuthToken();
        if (!token) {
            throw new Error('No auth token found');
        }

        showLoading('progressText');

        const response = await fetch(`${API_BASE_URL}/progress`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === "success") {
            // Update overall stats
            document.getElementById('overallProgress').textContent = 
                `${data.progress.completion_rate || 0}%`;
            document.getElementById('learningVelocity').textContent = 
                `${data.progress.learning_velocity || 0} lessons/week`;
            document.getElementById('engagementScore').textContent = 
                data.progress.engagement_score || 0;
            document.getElementById('activeDays').textContent = 
                data.progress.active_days || 0;

            // Update skill development
            if (data.progress.skills) {
                const skillDevelopment = document.getElementById('skillDevelopment');
                skillDevelopment.innerHTML = Object.entries(data.progress.skills)
                    .map(([skill, details]) => `
                        <div class="mb-4">
                            <div class="level is-mobile mb-2">
                                <div class="level-left">
                                    <span class="has-text-weight-medium">${skill}</span>
                                </div>
                                <div class="level-right">
                                    <div class="tags has-addons">
                                        <span class="tag is-dark">${details.level}</span>
                                        <span class="tag is-primary">${details.score}%</span>
                                    </div>
                                </div>
                            </div>
                            <progress 
                                class="progress is-primary" 
                                value="${details.score}" 
                                max="100"
                            ></progress>
                            ${details.recent_achievements ? `
                                <div class="is-size-7 has-text-grey mt-1">
                                    ${details.recent_achievements}
                                </div>
                            ` : ''}
                        </div>
                    `).join('');
            }

            // Update learning pathways
            if (data.progress.pathways) {
                const pathwaysList = document.getElementById('pathwaysList');
                pathwaysList.innerHTML = data.progress.pathways
                    .map(pathway => `
                        <div class="box">
                            <div class="level is-mobile">
                                <div class="level-left">
                                    <div>
                                        <p class="is-size-5 mb-2">${pathway.name}</p>
                                        <p class="has-text-grey">${pathway.description}</p>
                                    </div>
                                </div>
                                <div class="level-right">
                                    <div class="tags has-addons">
                                        <span class="tag is-dark">Progress</span>
                                        <span class="tag is-primary">${pathway.progress}%</span>
                                    </div>
                                </div>
                            </div>
                            <progress 
                                class="progress is-primary mt-3" 
                                value="${pathway.progress}" 
                                max="100"
                            ></progress>
                        </div>
                    `).join('');
            }

            // Update recent activity
            if (data.progress.recent_activity) {
                const recentActivity = document.getElementById('recentActivity');
                recentActivity.innerHTML = data.progress.recent_activity
                    .map(activity => `
                        <div class="box">
                            <div class="level is-mobile">
                                <div class="level-left">
                                    <div class="icon-text">
                                        <span class="icon has-text-primary">
                                            <i class="fas ${getActivityIcon(activity.type)}"></i>
                                        </span>
                                        <span>${activity.description}</span>
                                    </div>
                                </div>
                                <div class="level-right">
                                    <span class="has-text-grey is-size-7">
                                        ${formatDate(activity.timestamp)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    `).join('');
            }
        }
    } catch (error) {
        console.error('Error fetching progress:', error);
        document.getElementById('progressText').innerHTML = `
            <div class="notification is-danger is-light">
                Error loading progress. Please try again later.
            </div>
        `;
    } finally {
        hideLoading('progressText');
    }
}

// Helper function for activity icons
function getActivityIcon(type) {
    const icons = {
        'lesson_complete': 'fa-check-circle',
        'skill_increase': 'fa-level-up-alt',
        'streak_milestone': 'fa-fire',
        'feedback_received': 'fa-comment',
        'behavioral_insight': 'fa-lightbulb',
        'pathway_progress': 'fa-route',
        'default': 'fa-circle'
    };
    return icons[type] || icons.default;
}

// Helper function for date formatting
function formatDate(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        return date.toLocaleTimeString('en-GB', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else if (diffDays < 7) {
        return date.toLocaleDateString('en-GB', { weekday: 'long' });
    } else {
        return date.toLocaleDateString('en-GB', { 
            day: 'numeric', 
            month: 'short'
        });
    }
}

// Update dashboard stats
async function updateDashboardStats() {
    try {
        const token = getAuthToken();
        if (!token) return;

        const response = await fetch(`${API_BASE_URL}/dashboard/stats`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === "success") {
            // Update current lesson
            if (data.current_lesson) {
                document.getElementById('currentLesson').textContent = 
                    formatLessonName(data.current_lesson);
            }

            // Update completion rate
            if (data.completion_rate !== undefined) {
                document.getElementById('completionRate').textContent = 
                    `${data.completion_rate}%`;
            }

            // Update learning streak
            if (data.streak !== undefined) {
                const streakElement = document.getElementById('learningStreak');
                streakElement.textContent = `${data.streak} days`;
                
                // Add streak celebration if milestone
                if (data.streak_milestone) {
                    streakElement.classList.add('has-text-success');
                    showSuccess(`🎉 Congratulations! You've reached a ${data.streak} day streak!`);
                }
            }
        }
    } catch (error) {
        console.error('Error updating dashboard stats:', error);
    }
}

// Helper function to format lesson names
function formatLessonName(lessonId) {
    const parts = lessonId.split('_');
    const lessonNum = parts[1];
    const stepNum = parts[3];
    
    if (stepNum) {
        return `Lesson ${lessonNum} - Step ${stepNum}`;
    }
    return `Lesson ${lessonNum}`;
}

// Fetch journal entries
async function formatJournalEntry(entry) {
    const date = new Date(entry.timestamp).toLocaleDateString();
    const keywords = entry.keywords_used || [];
    
    return `
        <div class="box mb-5 fade-in">
            <div class="level is-mobile mb-2">
                <div class="level-left">
                    <div class="level-item">
                        <span class="icon-text">
                            <span class="icon has-text-primary">
                                <i class="fas fa-book"></i>
                            </span>
                            <strong>${entry.lesson}</strong>
                        </span>
                    </div>
                </div>
                <div class="level-right">
                    <div class="level-item">
                        <span class="icon-text has-text-grey">
                            <span class="icon">
                                <i class="fas fa-calendar"></i>
                            </span>
                            <span>${date}</span>
                        </span>
                    </div>
                </div>
            </div>
            <p class="mb-3">${entry.response}</p>
            ${keywords.length ? `
                <div class="tags">
                    ${keywords.map(keyword => `
                        <span class="tag is-primary is-light">
                            ${keyword}
                        </span>
                    `).join('')}
                </div>
            ` : ''}
            ${entry.quality_score ? `
                <div class="level is-mobile mt-3">
                    <div class="level-left">
                        <div class="level-item">
                            <span class="icon-text has-text-success">
                                <span class="icon">
                                    <i class="fas fa-chart-line"></i>
                                </span>
                                <span>Quality Score: ${entry.quality_score}%</span>
                            </span>
                        </div>
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

async function formatSkillProgress(skills) {
    return skills.map(skill => `
        <div class="mb-4">
            <div class="level is-mobile mb-2">
                <div class="level-left">
                    <span class="has-text-weight-medium">${skill.name}</span>
                </div>
                <div class="level-right">
                    <span class="has-text-grey">${skill.level}%</span>
                </div>
            </div>
            <progress 
                class="progress is-primary" 
                value="${skill.level}" 
                max="100"
            >
                ${skill.level}%
            </progress>
        </div>
    `).join('');
}

async function updateJournalMetrics(data) {
    // Update streak
    const streakCount = document.getElementById('streakCount');
    const streakMessage = document.getElementById('streakMessage');
    if (data.streak) {
        streakCount.textContent = data.streak;
        if (data.streak >= 7) {
            streakMessage.textContent = '🎉 Amazing weekly streak!';
        } else if (data.streak >= 3) {
            streakMessage.textContent = '🔥 Great consistency!';
        }
    }

    // Update total entries
    const totalEntries = document.getElementById('totalEntries');
    if (totalEntries) {
        totalEntries.textContent = data.total_entries || 0;
    }

    // Update quality score
    const qualityScore = document.getElementById('qualityScore');
    if (qualityScore) {
        qualityScore.textContent = `${Math.round(data.average_quality || 0)}%`;
    }
}

async function fetchJournal() {
    try {
        const token = getAuthToken();
        if (!token) {
            throw new Error('No auth token found');
        }

        showLoading('journalList');

        // Fetch journal entries
        const response = await fetch(`${API_BASE_URL}/journal`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === "success") {
            // Update metrics
            await updateJournalMetrics({
                streak: data.metrics?.streak || 0,
                total_entries: data.journal?.length || 0,
                average_quality: data.metrics?.average_quality || 0
            });

            // Format and display entries
            const journalList = document.getElementById('journalList');
            if (data.journal && data.journal.length > 0) {
                const entriesHTML = await Promise.all(
                    data.journal.map(entry => formatJournalEntry(entry))
                );
                journalList.innerHTML = entriesHTML.join('');
            } else {
                journalList.innerHTML = `
                    <div class="notification is-info is-light">
                        <p>No journal entries yet! Start your learning journey to begin documenting your progress.</p>
                        <p class="mt-3">
                            <a href="/web/dashboard.html" class="button is-primary">
                                Go to Learning Dashboard
                            </a>
                        </p>
                    </div>
                `;
            }

            // Update skills section if available
            if (data.skills) {
                const skillsList = document.getElementById('skillsList');
                skillsList.innerHTML = await formatSkillProgress(data.skills);
            }

            // Update feedback section if available
            if (data.latest_feedback) {
                const feedbackContent = document.getElementById('feedbackContent');
                feedbackContent.innerHTML = `
                    <div class="notification is-success is-light">
                        <p class="mb-2"><strong>Latest Feedback:</strong></p>
                        <p>${data.latest_feedback}</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error fetching journal:', error);
        document.getElementById('journalList').innerHTML = `
            <div class="notification is-danger is-light">
                <p>Error loading journal entries. Please try again later.</p>
            </div>
        `;
    } finally {
        hideLoading('journalList');
    }
}

// Initialize on page load
window.onload = initializeApp;

document.addEventListener('DOMContentLoaded', () => {
    updateAuthNavigation();
    initializeMobileMenu();
});

document.addEventListener('DOMContentLoaded', () => {
    // Get all "navbar-burger" elements
    const $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);

    // Add a click event on each of them
    $navbarBurgers.forEach(el => {
        el.addEventListener('click', () => {
            // Get the target from the "data-target" attribute
            const target = el.dataset.target;
            const $target = document.getElementById(target);

            // Toggle the "is-active" class on both the "navbar-burger" and the "navbar-menu"
            el.classList.toggle('is-active');
            $target.classList.toggle('is-active');
        });
    });
});

document.getElementById('lessonSelect')?.addEventListener('change', (e) => {
    if (e.target.value) {
        loadLesson(e.target.value);
    }
});