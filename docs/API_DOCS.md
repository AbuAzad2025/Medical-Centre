# AZAD Medical Centre Platform - API Documentation

## Base URL
`http://localhost:8000`

## Authentication
All API endpoints require authentication via session cookie (login via `/auth/login`).

## CSRF Protection
All POST/PUT/DELETE requests require CSRF token in `X-CSRFToken` header.

## Endpoints

### Health
- `GET /__health` - Liveness probe (always 200)
- `GET /health` - Readiness probe (DB, Redis, Stripe, SMS)

### Search
- `GET /api/search?q=<query>` - Global search (patients, appointments, prescriptions)

### Dashboard
- `GET /api/dashboard/snapshot` - Dashboard data snapshot

### User
- `GET /api/user/preferences` - User preferences
- `POST /api/user/preferences` - Update preferences

### Lab
- `GET /api/lab/*` - Lab API endpoints

### Radiology
- `GET /api/radiology/*` - Radiology API endpoints

### FHIR
- `GET /api/fhir/patient/<id>` - FHIR Patient
- `GET /api/fhir/encounter/<id>` - FHIR Encounter
- `GET /api/fhir/organization/<id>` - FHIR Organization
- `GET /api/fhir/practitioner/<id>` - FHIR Practitioner
- `GET /api/fhir/appointment/<id>` - FHIR Appointment

### Reception
- `GET /reception/api/patients` - List patients
- `GET /reception/api/doctors` - List doctors
- `GET /reception/api/department-services` - Department services
- `GET /reception/api/department-staff` - Department staff
- `GET /reception/api/queue-snapshot` - Queue snapshot
- `GET /reception/api/queue-status-all` - All queue statuses
- `GET /reception/api/queue-wait-metrics` - Queue wait metrics
- `GET /reception/api/smart-patient-search` - Smart patient search
- `GET /reception/api/visit-pricing` - Visit pricing
- `GET /reception/api/available-times` - Available time slots

### Super Admin
- `GET /super-admin/api/audit-log` - Audit log API
- `GET /super-admin/api/*` - Various super admin APIs

### Owner
- `GET /owner/api/tenants` - List tenants
- `GET /owner/api/tenants/<id>/modules` - Tenant modules
- `GET /owner/api/tenants/<id>/limits` - Tenant limits
- `GET /owner/api/tenants/<id>/features/<key>/toggle` - Toggle feature
- `GET /owner/api/bundles` - List bundles
- `GET /owner/api/bundles/<id>` - Get bundle
- `POST /owner/api/bundles` - Create bundle
- `PUT /owner/api/bundles/<id>` - Update bundle
- `DELETE /owner/api/bundles/<id>` - Delete bundle
- `POST /owner/api/tenants/provision` - Provision tenant
- `GET /owner/api/assumptions` - List assumptions
- `POST /owner/api/assumptions` - Create assumption
- `POST /owner/api/assumptions/<id>/revoke` - Revoke assumption

### Authentication
- `POST /auth/login` - Login
- `GET /auth/logout` - Logout
- `GET /auth/profile` - User profile

### Language
- `GET /set-language/<lang_code>` - Set language (ar/en)

### Response Format
All API responses are JSON with appropriate HTTP status codes.

### Error Handling
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error

### Rate Limiting
API endpoints are rate-limited per user/tenant.

### Versioning
Current API version: v1 (no version prefix in URLs)