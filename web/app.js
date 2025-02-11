const API_BASE_URL = "https://gclearnbot.onrender.com"; 


async function registerUser() {
    let email = document.getElementById("registerEmail").value.trim();
    let password = document.getElementById("registerPassword").value.trim();

    console.log("Registering user:", { email, password });

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
        console.log("Register API Response:", data);

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

async function loginUser() {
    let email = document.getElementById("email").value.trim();
    let password = document.getElementById("password").value.trim();

    console.log("Sending login request:", { email, password });

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
        console.log("Login API Response:", data);

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

function logoutUser() {
    localStorage.removeItem("token");  // ✅ Remove token from local storage
    alert("You have been logged out.");
    window.location.reload();  // ✅ Refresh the page to go back to login screen
}

function getAuthToken() {
    return localStorage.getItem("token");
}

// Example of an API request with authentication
async function fetchUserProgress() {
    let token = getAuthToken();
    if (!token) {
        alert("Please log in first.");
        return;
    }

    let response = await fetch(`${API_BASE_URL}/progress`, {
        method: "GET",
        headers: { "Authorization": `Bearer ${token}` },
    });

    let data = await response.json();
    console.log(data);
}

// Load available lessons into the dropdown
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
            const lessonCard = document.getElementById("lessonCard");
            const lessonTitle = document.getElementById("lessonTitle");
            const lessonContent = document.getElementById("lessonContent");

            lessonTitle.textContent = data.lesson.title;
            lessonContent.innerHTML = data.lesson.text.replace(/\n/g, '<br>');
            lessonCard.classList.remove("d-none");
        } else {
            alert("Error loading lesson content");
        }
    } catch (error) {
        console.error("Error loading lesson:", error);
        alert("Failed to load lesson content");
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

        // Get the select element - match the exact structure in your HTML
        const select = document.querySelector('select');
        
        if (!select) {
            console.error("Select element not found");
            return;
        }

        // Clear current options
        select.innerHTML = '<option value="">Select a lesson...</option>';

        if (data.status === "success" && Array.isArray(data.lessons)) {
            // Sort lessons by number
            const sortedLessons = data.lessons.sort((a, b) => {
                const aNum = parseInt(a.lesson_id.split('_')[1]) || 0;
                const bNum = parseInt(b.lesson_id.split('_')[1]) || 0;
                return aNum - bNum;
            });

            // Add lessons to select
            sortedLessons.forEach(lesson => {
                if (lesson.lesson_id && lesson.title) {
                    const option = document.createElement("option");
                    option.value = lesson.lesson_id;
                    option.textContent = `Lesson ${lesson.lesson_id.split('_')[1]}: ${lesson.title}`;
                    select.appendChild(option);
                }
            });
        } else {
            console.error("Invalid lessons data:", data);
        }
    } catch (error) {
        console.error("Error fetching lessons:", error);
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