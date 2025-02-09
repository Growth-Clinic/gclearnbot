const API_BASE_URL = "https://gclearnbot.onrender.com";  // Change this to your Render URL when deployed


async function registerUser(email, password) {
    let response = await fetch(`${API_BASE_URL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });

    let data = await response.json();
    alert(data.message);
}

async function loginUser(email, password) {
    let response = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });

    let data = await response.json();
    if (data.status === "success") {
        localStorage.setItem("token", data.token);
        alert("Login successful!");
    } else {
        alert("Login failed: " + data.message);
    }
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
async function loadLessons() {
    const lessonSelect = document.getElementById("lessonSelect");
    lessonSelect.innerHTML = '<option>Loading...</option>';

    try {
        let response = await fetch(`${API_BASE_URL}/lessons`);
        let data = await response.json();

        if (data.status === "success") {
            lessonSelect.innerHTML = "";
            data.lessons.forEach(lesson => {
                let option = document.createElement("option");
                option.value = lesson.lesson_id;
                option.textContent = lesson.title;
                lessonSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error("Error fetching lessons:", error);
    }
}

// Fetch and display lesson content
async function fetchLessons() {
    let token = getAuthToken();
    if (!token) {
        alert("Please log in first.");
        return;
    }

    let response = await fetch(`${API_BASE_URL}/lessons`, {
        method: "GET",
        headers: { "Authorization": `Bearer ${token}` },
    });

    let data = await response.json();
    console.log(data);
}

// Submit user response
async function submitResponse() {
    const lessonId = document.getElementById("lessonSelect").value;
    const responseText = document.getElementById("responseText").value;

    try {
        let response = await fetch(`${API_BASE_URL}/lessons/${lessonId}/response`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: USER_ID, response: responseText })
        });

        let data = await response.json();
        if (data.status === "success") {
            document.getElementById("responseMessage").classList.remove("d-none");
            setTimeout(() => document.getElementById("responseMessage").classList.add("d-none"), 3000);
        }
    } catch (error) {
        console.error("Error submitting response:", error);
    }
}

// Fetch user progress
async function fetchProgress() {
    try {
        let response = await fetch(`${API_BASE_URL}/progress/${USER_ID}`);
        let data = await response.json();

        if (data.status === "success") {
            document.getElementById("progressText").textContent = `Completed ${data.progress.completed_lessons.length} lessons.`;
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
