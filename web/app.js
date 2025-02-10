const API_BASE_URL = "https://gclearnbot.onrender.com"; 


async function registerUser() {
    let email = document.getElementById("registerEmail").value.trim();
    let password = document.getElementById("registerPassword").value.trim();

    console.log("Registering user:", { email, password });  // ✅ Debugging log

    if (!email || !password) {
        alert("Please enter a valid email and password.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })  // ✅ Send JSON correctly
        });

        let data = await response.json();
        console.log("Register API Response:", data);  // ✅ Log API response

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
    let email = document.getElementById("email").value;
    let password = document.getElementById("password").value;

    console.log("Sending login request:", { email, password });  // ✅ Debug log

    try {
        let response = await fetch(`${API_BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        let data = await response.json();
        console.log("Login API Response:", data);  // ✅ Log API response

        if (data.status === "success") {
            localStorage.setItem("token", data.token);
            alert("Login successful!");
            window.location.reload();
        } else {
            alert("Login failed: " + data.message);
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
async function loadLesson(lessonId) {
    let token = getAuthToken();
    if (!token) {
        alert("Please log in first.");
        return;
    }

    try {
        let response = await fetch(`${API_BASE_URL}/lessons/${lessonId}`, {
            method: "GET",
            headers: { "Authorization": `Bearer ${token}` },
        });

        let data = await response.json();
        if (data.status === "success") {
            document.getElementById("lessonContent").innerHTML = `
                <h3>${data.lesson.title}</h3>
                <p>${data.lesson.text}</p>
            `;
        } else {
            alert(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error("Error loading lesson:", error);
    }
}

// Fetch and display lesson content
async function fetchLessons() {
    let token = getAuthToken();
    console.log("Using Token:", token);  // ✅ Check if the token is set

    if (!token) {
        alert("Please log in first.");
        return;
    }

    let response = await fetch(`${API_BASE_URL}/lessons`, {
        method: "GET",
        headers: { "Authorization": `Bearer ${token}` },
    });

    let data = await response.json();
    console.log("API Response:", data);  // ✅ Log full API response

    if (data.status === "success") {
        let lessonsContainer = document.getElementById("lessons");
        lessonsContainer.innerHTML = "";

        data.lessons.forEach(lesson => {
            let lessonDiv = document.createElement("div");
            lessonDiv.innerHTML = `<h3>${lesson.title}</h3>
                <p>${lesson.text}</p>
                <button onclick="loadLesson('${lesson.lesson_id}')">Start</button>`;
            lessonsContainer.appendChild(lessonDiv);
        });
    } else {
        alert(`Error: ${data.message}`);
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

// Load lessons on page load
window.onload = loadLessons;
