# API Documentation (OpenAPI 3.0)

## Base URL

`http://localhost:5000/api`

## Authentication

### Login

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "success": true,
  "token": "jwt-token-or-session-id"
}
```

### Logout

```http
POST /auth/logout
Headers: Authorization: Bearer <token>
```

## Radiology Module

### Templates

#### List Templates

```http
GET /radiology/api/report-templates
```

**Query Parameters:**
- `modality`: Filter by modality (XRAY, CT, MRI, US)
- `active_only`: Include inactive templates (default: true, set to "0" or "false" to exclude)

**Response:**
```json
{
  "success": true,
  "templates": [
    {
      "id": "template-uuid",
      "name": "Template Name",
      "modality": "XRAY",
      "findings": "Findings text",
      "impression": "Impression text",
      "recommendations": "Recommendations text",
      "is_active": true
    }
  ]
}
```

#### Create Template

```http
POST /radiology/api/report-templates
Content-Type: application/json

{
  "name": "Template Name",
  "modality": "XRAY",
  "findings": "Findings text",
  "impression": "Impression text",
  "recommendations": "Recommendations text",
  "is_active": true
}
```

**Response (201):**
```json
{
  "success": true,
  "id": "new-template-uuid"
}
```

#### Update Template

```http
POST /radiology/api/report-templates/{template_id}
Content-Type: application/json

{
  "name": "Updated Template Name",
  "modality": "CT",
  ...
}
```

**Response:**
```json
{
  "success": true,
  "id": "template-uuid"
}
```

#### Delete Template

```http
POST /radiology/api/report-templates/{template_id}/delete
```

**Response:**
```json
{
  "success": true
}
```

### Macros

#### List Macros

```http
GET /radiology/api/report-macros
```

**Response:** Same structure as templates

#### Create Macro

```http
POST /radiology/api/report-macros
Content-Type: application/json

{
  "name": "Macro Name",
  "text": "Macro text body"
}
```

**Response (201):**
```json
{
  "success": true,
  "id": "new-macro-uuid"
}
```

#### Update Macro

```http
POST /radiology/api/report-macros/{macro_id}
```

**Response:** Success status

#### Delete Macro

```http
POST /radiology/api/report-macros/{macro_id}/delete
```

**Response:** Success status

### Worklist

#### View Worklist

```http
GET /radiology/worklist?status=REQUESTED
```

**Query Parameters:**
- `status`: Filter by status (REQUESTED, IN_PROGRESS, DONE, DONE_TODAY)

**Response:** HTML page with radiology requests

#### Claim Request

```http
POST /radiology/worklist/claim/{request_id}
Headers: Accept: application/json
```

**Response:**
```json
{
  "success": true,
  "message": "تم استلام الطلب"
}
```

#### Complete Request

```http
POST /radiology/worklist/complete/{request_id}
Headers: Accept: application/json
Content-Type: application/json

{
  "findings": "No acute findings",
  "impression": "Normal",
  "is_critical": "on"  // optional
}
```

**Response:**
```json
{
  "success": true,
  "message": "تم إكمال الطلب"
}
```

### Doctor Routes

#### Create Radiology Request

```http
POST /doctor/radiology-request/{visit_id}
Content-Type: application/x-www-form-urlencoded

{
  "modality": "XRAY",
  "body_part": "Chest",
  "notes": "PA view needed"
}
```

**Response:** Success (200/302) or free-text variant

## Error Responses

All endpoints return consistent error formats:

```json
{
  "success": false,
  "message": "Error message in Arabic"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `302` - Redirect (form submissions)
- `400` - Bad request (validation error)
- `403` - Forbidden (insufficient role)
- `404` - Not found
- `401` - Unauthenticated
- `500` - Server error

## Role Permissions

| Role | Access |
|------|--------|
| `doctor` | Create radiology requests, view worklist |
| `radiology` | View/worklist, claim/complete requests |
| `manager` | Manage templates & macros |
| `super_admin` | Full access, all administrative functions |
| `reception` | View limited data, tenant selection |

## API Contract Tests

The CI/CD pipeline includes API contract tests that verify:
1. Anonymous access is properly gated
2. Protected endpoints require authentication
3. HTTP methods return correct status codes
4. GET JSON endpoints never 500/error
5. POST JSON handles empty/malformed bodies gracefully