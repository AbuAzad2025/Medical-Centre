# AZAD Medical Centre Platform - Admin Guide

## System Administration

### Initial Setup
1. Install PostgreSQL 16+
2. Create database: `CREATE DATABASE medical_local OWNER postgres;`
3. Set environment variables:
   - `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medical_local`
   - `SECRET_KEY=<your-secret-key-min-32-chars>`
   - `APP_ENV=development`
   - `FLASK_ENV=development`
   - `RLS_BYPASS_ALLOWED=1`
4. Run migrations: `python -m flask db upgrade heads`
5. Run bootstrap: `python -c "from app_factory import create_app; app = create_app('development'); app.app_context().push(); from app.core.platform_bootstrap import run_platform_bootstrap; run_platform_bootstrap()"`
6. Run seed: `python scripts/seed_comprehensive.py --clean`

### User Management
- Go to **Super Admin → Users**
- Create new users with roles
- Assign departments
- Reset passwords
- Deactivate users

### Department Management
- Go to **Super Admin → Departments**
- Create/edit departments
- Assign staff to departments
- Configure department workflows

### Service Management
- Go to **Super Admin → Services**
- Create services with pricing
- Enable/disable services
- Configure service categories

### Role & Permission Management
- Go to **Super Admin → Roles**
- Create custom roles
- Assign permissions to roles
- Manage role-permission matrix

### Module Management
- Go to **Owner → Modules**
- Enable/disable modules per tenant
- Configure module settings
- View module usage

### Package Management
- Go to **Owner → Packages**
- Create/edit packages
- Configure pricing
- Manage subscriptions

### System Configuration
- Go to **Super Admin → System Config**
- Configure branding
- Set currency
- Configure notifications
- Set up email/SMS

### Audit & Security
- Go to **Super Admin → Security Center**
- View audit logs
- Monitor security events
- Review access logs
- Check system health

### Backup & Restore
- Go to **Super Admin → Backup**
- Create manual backup
- Configure automated backups
- Restore from backup

### Performance Monitoring
- Go to **Super Admin → Performance**
- View slow queries
- Monitor system metrics
- Check database health

### Troubleshooting
- Check logs in `logs/` directory
- Verify database connection
- Check environment variables
- Review audit logs for errors
- Use `/health` endpoint for system status