# Microservices Architecture & Tenant Isolation

## Overview
The Medical Centre system has been restructured to support microservices deployment
while maintaining strict tenant isolation across all services.

## Service Decomposition

| Service | Port | Modules | Description |
|---|---|---|---|
| core-api | 8080 | reception, doctor, nursing, emergency | Core clinical operations |
| pharmacy-service | 8081 | pharmacy | Medication management, dispensing, POS |
| lab-service | 8082 | lab | Lab requests, results, quality |
| billing-service | 8083 | billing, accounting | Invoices, payments, GL, reports |
| worker | — | — | Celery background tasks |
| api-gateway | 80 | — | Nginx reverse proxy + tenant routing |

## Tenant Isolation (العزل)

### How It Works
1. **Database Level**: PostgreSQL Row-Level Security (RLS) policies enforce tenant isolation
   - 216 RLS policies across 216 tables
   - `app.tenant_id` session variable set per connection
   - RLS policies filter rows by `tenant_id = current_setting('app.tenant_id')`

2. **Application Level**: 
   - `TenantMiddleware` binds tenant from session/JWT on every request
   - `g.tenant_id` propagates through the request lifecycle
   - `auto_assign_tenant` sets `tenant_id` on new records
   - `_tenant_filter_bypass` only for super_admin cross-tenant operations

3. **Inter-Service Level**:
   - API Gateway propagates `X-Tenant-ID` header to all services
   - Each service independently validates tenant context
   - Shared PostgreSQL with RLS ensures data isolation even if a service is compromised

4. **Service-Level Isolation**:
   - Each service runs with `RLS_BYPASS_ALLOWED=0`
   - No service can access another tenant's data
   - Tenant context is validated on every database query

### Deployment Modes
- **Monolith**: `docker-compose.yml` (single app container)
- **Microservices**: `docker-compose.microservices.yml` (split services)
- **Kubernetes**: `k8s/` manifests (production-ready)

### CDN Configuration
- Static assets served with long-term caching (1 year)
- Uploads served with short cache (1 hour) + tenant isolation
- Nginx compression (gzip) for CSS/JS/JSON/SVG
- See `nginx/cdn.conf` for CDN origin configuration

### Migration Path
1. Start with monolith (docker-compose.yml)
2. Gradually extract services (docker-compose.microservices.yml)
3. Deploy to Kubernetes (k8s/) when ready
4. Add CDN (CloudFront/Cloudflare) for static assets

### Security Notes
- Never set `RLS_BYPASS_ALLOWED=1` in production
- All services must propagate tenant context
- Database connections must set `app.tenant_id` before queries
- Audit all cross-service calls for tenant leakage
---