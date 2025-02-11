# Growth Clinic API Documentation

## Base URL
```
https://gclearnbot.onrender.com
```

## Authentication Endpoints

### 1. User Registration
- **Endpoint:** `/register`
- **Method:** POST
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```
- **Responses:**
  - Success (201): 
    ```json
    {
      "status": "success", 
      "token": "JWT_TOKEN"
    }
    ```
  - Error (409): User already exists
  - Error (400): Missing email or password

### 2. User Login
- **Endpoint:** `/login`
- **Method:** POST
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success", 
      "token": "JWT_TOKEN"
    }
    ```
  - Error (404): User not found
  - Error (401): Invalid credentials

## Lesson Endpoints

### 3. List Lessons
- **Endpoint:** `/lessons`
- **Method:** GET
- **Headers:** 
  - Authorization: Bearer JWT_TOKEN
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success", 
      "lessons": [
        {
          "lesson_id": "lesson_1", 
          "title": "Introduction to Design Thinking"
        }
      ]
    }
    ```

### 4. Get Specific Lesson
- **Endpoint:** `/lessons/<lesson_id>`
- **Method:** GET
- **Headers:** 
  - Authorization: Bearer JWT_TOKEN
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success",
      "lesson": {
        "lesson_id": "lesson_2",
        "title": "Design Thinking Basics",
        "text": "Lesson content...",
        "next": "lesson_2_step_1"
      }
    }
    ```

### 5. Submit Lesson Response
- **Endpoint:** `/lessons/<lesson_id>/response`
- **Method:** POST
- **Headers:** 
  - Authorization: Bearer JWT_TOKEN
- **Request Body:**
```json
{
  "user_id": "123456",
  "response": "My lesson response text"
}
```
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success", 
      "message": "Response saved"
    }
    ```

## Progress Endpoints

### 6. Get User Progress
- **Endpoint:** `/progress`
- **Method:** GET
- **Headers:** 
  - Authorization: Bearer JWT_TOKEN
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success",
      "progress": {
        "completed_lessons": ["lesson_1", "lesson_2"]
      }
    }
    ```

### 7. Get Complete Progress
- **Endpoint:** `/progress/complete/<user_id>`
- **Method:** GET
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success",
      "progress": {
        "total_responses": 10,
        "completed_lessons": 3,
        "engagement_score": 75
      }
    }
    ```

## Journal Endpoints

### 8. Get Journal Entries
- **Endpoint:** `/journal/<user_id>`
- **Method:** GET
- **Responses:**
  - Success (200):
    ```json
    {
      "status": "success", 
      "journal": [
        {
          "lesson": "lesson_1",
          "response": "My journal entry text",
          "timestamp": "2024-02-11T12:34:56Z"
        }
      ]
    }
    ```

## Implementation Notes
1. Always include the JWT token in the Authorization header for authenticated routes
2. Token should be in the format: `Bearer YOUR_JWT_TOKEN`
3. Handle potential errors by checking the `status` field in responses
4. Store the JWT token in `localStorage` after successful login/registration

## Error Handling
Most endpoints return errors with the following structure:
```json
{
  "status": "error",
  "message": "Detailed error description"
}
```

Possible status codes:
- 200: Successful request
- 400: Bad request (missing parameters)
- 401: Unauthorized (invalid token)
- 404: Resource not found
- 500: Server error

## Security Recommendations
1. Store JWT token securely in `localStorage`
2. Check token expiration
3. Implement token refresh mechanism
4. Use HTTPS for all API calls
5. Log out user and clear token on unauthorized access

## Additional Information
- **Platform:** Web Application (Growth Clinic)
- **Base Technology:** Quart (Python) Backend with JWT Authentication
- **Frontend:** JavaScript with Fetch API
- **Location of Implementation:** Lagos, Nigeria