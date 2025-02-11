# Growth Clinic API Documentation

## Base Information
- **Base URL:** `https://gclearnbot.onrender.com`
- **Authentication:** JWT-based
- **Location:** Lagos, Nigeria
- **Technologies:** 
  - Backend: Quart (Python)
  - Authentication: JWT
  - Database: MongoDB

## Authentication Endpoints

### 1. User Registration
- **URL:** `/register`
- **Method:** `POST`
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```
- **Successful Response:** 
  - **Code:** 201
  - **Content:** 
    ```json
    {
      "status": "success",
      "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
    ```
- **Error Responses:**
  - **409 Conflict:** User already exists
  - **400 Bad Request:** Missing email or password

### 2. User Login
- **URL:** `/login`
- **Method:** `POST`
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```
- **Successful Response:**
  - **Code:** 200
  - **Content:** 
    ```json
    {
      "status": "success",
      "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
    ```
- **Error Responses:**
  - **404 Not Found:** User not found
  - **401 Unauthorized:** Invalid credentials

## Lesson Endpoints

### 3. List All Lessons
- **URL:** `/lessons`
- **Method:** `GET`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success",
      "lessons": [
        {
          "lesson_id": "lesson_1",
          "title": "Lesson Title"
        }
      ]
    }
    ```

### 4. Get Specific Lesson
- **URL:** `/lessons/<lesson_id>`
- **Method:** `GET`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success",
      "lesson": {
        "lesson_id": "lesson_2",
        "title": "Lesson Title",
        "text": "Lesson content...",
        "next": "lesson_2_step_1"
      }
    }
    ```

### 5. Submit Lesson Response
- **URL:** `/lessons/<lesson_id>/response`
- **Method:** `POST`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
  - `Content-Type: application/json`
- **Request Body:**
```json
{
  "response": "User's lesson response text"
}
```
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success",
      "message": "Response saved"
    }
    ```

## Progress Endpoints

### 6. Get User Progress
- **URL:** `/progress`
- **Method:** `GET`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success",
      "progress": {
        "completed_lessons": ["lesson_1", "lesson_2"]
      }
    }
    ```

### 7. Get Detailed Progress
- **URL:** `/progress/complete/<user_id>`
- **Method:** `GET`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
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
- **URL:** `/journal`
- **Method:** `GET`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success", 
      "journal": [
        {
          "lesson": "lesson_1",
          "response": "Journal entry text",
          "timestamp": "2024-02-11T12:34:56Z"
        }
      ]
    }
    ```

## Additional Endpoints

### 9. Health Check
- **URL:** `/health`
- **Method:** `GET`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "healthy",
      "timestamp": "2024-02-11T12:34:56Z",
      "db": "connected"
    }
    ```

### 10. Analytics
- **URL:** `/analytics`
- **Method:** `GET`
- **Headers:** 
  - `Authorization: Bearer <JWT_TOKEN>`
- **Successful Response:**
  - **Code:** 200
  - **Content:**
    ```json
    {
      "status": "success",
      "data": {
        "user_metrics": {
          "total_users": 100,
          "active_users": {...},
          "retention_rates": {...}
        },
        "learning_metrics": {
          "average_completion_rate": 65.5,
          "lesson_distribution": {...}
        }
      }
    }
    ```

## Error Handling

All endpoints return errors in the following format:
```json
{
  "status": "error",
  "message": "Detailed error description"
}
```

### Common Error Codes
- **400:** Bad Request
- **401:** Unauthorized
- **404:** Not Found
- **500:** Internal Server Error

## Authentication & Security

### Token Management
1. Tokens are JWT-based
2. Token is required for most endpoints
3. Include token in `Authorization` header as `Bearer <TOKEN>`
4. Tokens have an expiration time

### Security Best Practices
1. Always use HTTPS
2. Store token securely in `localStorage`
3. Check token expiration before API calls
4. Implement token refresh mechanism
5. Log out and clear token on unauthorized access

## Rate Limiting
- Specific rate limit details to be confirmed with backend team

## Versioning
- Current API version: No explicit versioning (v1 implied)

## Support
- **Contact:** growthclinic@gmail.com
- **Location:** Lagos, Nigeria
