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
        document.getElementById('protectedContent').classList.add('is-hidden');
        document.getElementById('notSignedIn').classList.remove('is-hidden');
        return;
    }
    
    document.getElementById('protectedContent').classList.remove('is-hidden');
    document.getElementById('notSignedIn').classList.add('is-hidden');
    
    // Initialize based on current page
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('dashboard.html')) {
        await fetchLessons();
        await fetchProgress();
    } else if (currentPath.includes('progress.html')) {
        await fetchProgress();
    } else if (currentPath.includes('journal.html')) {
        await fetchJournal();
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

// Improve the authentication check
function checkAuth() {
    const token = getAuthToken();
    const currentPath = window.location.pathname;
    
    if (token && isTokenExpired(token)) {
        localStorage.removeItem('token');
        showError('Your session has expired. Please log in again.');
        window.location.href = '/web/index.html';
        return false;
    }

    // If on a protected route and not authenticated
    if (PROTECTED_ROUTES.includes(currentPath) && !token) {
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

// Register user
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
            window.location.href = '/web/dashboard.html';
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

// Login user
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

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            window.location.href = '/web/dashboard.html';
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
    alert("You have been logged out.");
    window.location.reload();
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
    const errorDiv = document.createElement('div');
    errorDiv.className = 'notification is-danger';
    errorDiv.innerHTML = `
        <button class="delete"></button>
        ${message}
    `;
    
    // Add to page
    document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.container').firstChild);
    
    // Add close button functionality
    errorDiv.querySelector('.delete').addEventListener('click', () => {
        errorDiv.remove();
    });
    
    // Auto-remove after duration
    setTimeout(() => {
        errorDiv.remove();
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
                lessonContent.innerHTML = formatLessonContent(data.lesson.text);
                
                // Show lesson card
                lessonCard.classList.remove('is-hidden');
                lessonCard.classList.add('fade-in');

                // Show response form if needed
                if (data.lesson.requires_response) {
                    responseCard.classList.remove('is-hidden');
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
                    option.textContent = `📚 ${lesson.description}`;
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

// Submit user response
async function submitResponse() {
    event?.preventDefault();
    const lessonId = document.getElementById("lessonSelect").value;
    const responseText = document.getElementById("responseText").value;
    const token = getAuthToken(); // Get stored JWT token
    const submitButton = document.getElementById('submitButton');
    showLoading('submitButton');

    if (!token) {
        showError("Please log in first.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/lessons/${lessonId}/response`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ response: responseText })
        });

        let data = await response.json();
        if (data.status === "success") {
            document.getElementById("responseMessage").classList.remove("is-hidden");
            setTimeout(() => document.getElementById("responseMessage").classList.add("is-hidden"), 3000);
        } else {
            showError(`Error: ${data.message}`);
        } 
    } catch (error) {
        console.error("Error submitting response:", error);
        showError("Something went wrong. Please try again.");
    } finally {
        hideLoading('submitButton');
    }
}

// Fetch user progress
async function fetchProgress() {
    const token = getAuthToken();
    if (!token) {
        showError("Please log in first.");
        return;
    }

    const progressText = document.getElementById("progressText");
    progressText.innerHTML = '<div class="has-text-centered">Loading...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/progress`, {
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            }
        });

        if (response.status === 404 || response.status === 500) {
            progressText.innerHTML = `
                <div class="notification is-info">
                    <p>No progress data yet! Start your learning journey to track your progress.</p>
                    <p class="mt-3">
                        <a href="/web/dashboard.html" class="button is-primary">Go to Learning Dashboard</a>
                    </p>
                </div>`;
            return;
        }

        const data = await response.json();
        console.log("Progress API Response:", data);  // ✅ Log full API response

        if (data.status === "success") {
            let progressDiv = document.getElementById("progressText");
            progressDiv.innerHTML = `<p>Completed Lessons: ${data.progress.completed_lessons.length}</p>`;

            let lessonList = "<ul>";
            data.progress.completed_lessons.forEach(lesson => {
                lessonList += `<li>${lesson}</li>`;
            });
            lessonList += "</ul>";

            progressDiv.innerHTML += lessonList;
        } else {
            showError(`Error: ${data.message}`);
        }
    } catch (error) {
        progressText.innerHTML = `
            <div class="notification is-info">
                <p>No progress data yet! Start your learning journey to track your progress.</p>
                <p class="mt-3">
                    <a href="/web/dashboard.html" class="button is-primary">Go to Learning Dashboard</a>
                </p>
            </div>`;
    } finally {
        hideLoading('refreshProgress');
    }
}

// Fetch journal entries
async function fetchJournal() {
    const token = getAuthToken();
    if (!token) {
        showError("Please log in first.");
        return;
    }

    const journalList = document.getElementById("journalList");
    journalList.innerHTML = '<li class="list-group-item">Loading...</li>';

    try {
        const response = await fetch(`${API_BASE_URL}/journal`, {
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            }
        });

        if (response.status === 404) {
            journalList.innerHTML = `
                <div class="notification is-info">
                    <p>No journal entries yet! Start your learning journey to begin documenting your progress.</p>
                    <p class="mt-3">
                        <a href="/web/dashboard.html" class="button is-primary">Go to Learning Dashboard</a>
                    </p>
                </div>`;
            return;
        }

        const data = await response.json();

        if (data.status === "success") {
            journalList.innerHTML = "";
            data.journal.forEach(entry => {
                let listItem = document.createElement("li");
                listItem.className = "list-group-item";
                listItem.textContent = `📖 ${entry.lesson}: ${entry.response}`;
                journalList.appendChild(listItem);
            });
        }
    } catch (error) {
        journalList.innerHTML = `
            <div class="notification is-info">
                <p>No journal entries yet! Start your learning journey to begin documenting your progress.</p>
                <p class="mt-3">
                    <a href="/web/dashboard.html" class="button is-primary">Go to Learning Dashboard</a>
                </p>
            </div>`;
    }
}

// Initialize on page load
window.onload = initializeApp;

document.addEventListener('DOMContentLoaded', () => {
    updateAuthNavigation();
    initializeMobileMenu();
});

document.getElementById('lessonSelect')?.addEventListener('change', (e) => {
    if (e.target.value) {
        loadLesson(e.target.value);
    }
});