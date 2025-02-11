const API_BASE_URL = "https://gclearnbot.onrender.com"; 

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

// Mobile menu functionality (Bulma)
function initializeMobileMenu() {
    const burger = document.querySelector('.navbar-burger');
    const menu = document.querySelector('.navbar-menu');

    if (burger && menu) {
        burger.addEventListener('click', () => {
            burger.classList.toggle('is-active');
            menu.classList.toggle('is-active');
        });
    }
}


// Check if user is logged in; if so, redirect from index.html to dashboard
function checkRedirect() {
    if (getAuthToken()) {
        window.location.href = "/web/dashboard.html";
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
async function registerUser() {
    let email = document.getElementById("registerEmail").value.trim();
    let password = document.getElementById("registerPassword").value.trim();

    if (!email || !password) {
        alert("Please enter a valid email and password.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        let data = await response.json();

        if (response.status === 409) {
            alert("This email is already registered. Please try logging in instead.");
            return;
        }

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            alert("Registration successful! You are now logged in.");
            window.location.reload();
        } else {
            alert("Registration failed: " + data.message);
        }
    } catch (error) {
        console.error("Error registering user:", error);
        alert("Registration failed. Please try again.");
    }
}

// Login user
async function loginUser() {
    let email = document.getElementById("email").value.trim();
    let password = document.getElementById("password").value.trim();

    if (!email || !password) {
        alert("Please enter a valid email and password.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        let data = await response.json();

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            alert("Login successful!");
            window.location.reload();
        } else {
            alert(data.message || "Login failed. Please check your credentials.");
        }
    } catch (error) {
        console.error("Error logging in:", error);
        alert("Login failed. Please try again.");
    }
}

// Logout user
function logoutUser() {
    localStorage.removeItem("token");
    alert("You have been logged out.");
    window.location.reload();
}

// Get auth token from local storage
function getAuthToken() {
    return localStorage.getItem("token");
}

// Fetch user progress
async function fetchUserProgress() {
    let token = getAuthToken();
    if (!token) {
        alert("Please log in first.");
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
async function loadLesson() {
    const lessonSelect = document.getElementById("lessonSelect");
    const lessonId = lessonSelect.value;

    if (!lessonId) {
        alert("Please select a lesson first");
        return;
    }

    const token = getAuthToken();
    try {
        const response = await fetch(`${API_BASE_URL}/lessons/${lessonId}`, {
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            }
        });

        const data = await response.json();
        console.log("Load lesson response:", data);

        if (data.status === "success") {
            document.getElementById("lessonContent").innerHTML = data.content;
        } else {
            alert("Failed to load lesson.");
        }
    } catch (error) {
        console.error("Error loading lesson:", error);
    }
}

// Fetch and display lesson content
async function fetchLessons() {
    const token = getAuthToken();
    console.log("Using Token:", token);

    if (!token) {
        console.error("No auth token found");
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/lessons`, {
            method: "GET",
            headers: { 
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
        });

        const data = await response.json();
        console.log("Lessons API Response:", data);

        // Use querySelector to match the exact select element structure from your HTML
        const selectElement = document.querySelector('input[type="text"][placeholder="Select a lesson..."]');
        
        if (!selectElement) {
            console.error("Could not find lesson select element");
            console.log("Available elements:", document.querySelectorAll('select, input'));
            return;
        }

        // Create select element to replace the input
        const newSelect = document.createElement('select');
        newSelect.className = selectElement.className;
        newSelect.style = selectElement.style;
        
        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select a lesson...';
        newSelect.appendChild(defaultOption);

        if (data.status === "success" && Array.isArray(data.lessons)) {
            // Sort lessons
            const sortedLessons = data.lessons.sort((a, b) => {
                const aNum = parseInt(a.lesson_id.split('_')[1]) || 0;
                const bNum = parseInt(b.lesson_id.split('_')[1]) || 0;
                return aNum - bNum;
            });

            // Add lessons
            sortedLessons.forEach(lesson => {
                if (lesson.lesson_id && lesson.title) {
                    const option = document.createElement('option');
                    option.value = lesson.lesson_id;
                    option.textContent = `Lesson ${lesson.lesson_id.split('_')[1]}: ${lesson.title}`;
                    newSelect.appendChild(option);
                }
            });

            // Replace input with select
            selectElement.parentNode.replaceChild(newSelect, selectElement);
            console.log("Successfully replaced input with populated select");
        }
    } catch (error) {
        console.error("Error in fetchLessons:", error);
    }
}

// Submit user response
async function submitResponse() {
    const lessonId = document.getElementById("lessonSelect").value;
    const responseText = document.getElementById("responseText").value;
    const token = getAuthToken(); // Get stored JWT token

    if (!token) {
        alert("Please log in first.");
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
            document.getElementById("responseMessage").classList.remove("d-none");
            setTimeout(() => document.getElementById("responseMessage").classList.add("d-none"), 3000);
        } else {
            alert(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error("Error submitting response:", error);
        alert("Something went wrong. Please try again.");
    }
}

// Fetch user progress
async function fetchProgress() {
    const token = getAuthToken();
    console.log("Fetching progress with token:", token);  // ✅ Log the token

    if (!token) {
        alert("Please log in first.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/progress`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` }
        });

        let data = await response.json();
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
            alert(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error("Error fetching progress:", error);
    }
}


// Fetch journal entries
async function fetchJournal() {
    const journalList = document.getElementById("journalList");
    journalList.innerHTML = '<li class="list-group-item">Loading...</li>';

    try {
        let response = await fetch(`${API_BASE_URL}/journal/${USER_ID}`);
        let data = await response.json();

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
        console.error("Error fetching journal:", error);
    }
}

// Initialize the app
async function initializeApp() {
    const token = getAuthToken();
    if (token) {
        // Remove login section
        const loginSection = document.getElementById('loginSection');
        if (loginSection) {
            loginSection.style.display = 'none';
        }
        
        // Show dashboard
        const dashboardSection = document.getElementById('dashboardSection');
        if (dashboardSection) {
            dashboardSection.style.display = 'block';
        }
        
        // Fetch lessons
        await fetchLessons();
    } else {
        // Show login section
        const loginSection = document.getElementById('loginSection');
        if (loginSection) {
            loginSection.style.display = 'block';
        }
        
        // Hide dashboard
        const dashboardSection = document.getElementById('dashboardSection');
        if (dashboardSection) {
            dashboardSection.style.display = 'none';
        }
    }
}

// Initialize on page load
window.onload = initializeApp;