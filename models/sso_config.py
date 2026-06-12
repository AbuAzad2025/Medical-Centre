"""
SSO / LDAP / Active Directory Configuration
"""
from datetime import datetime, timezone
from app_factory import db

class SSOConfiguration(db.Model):
    __tablename__ = 'sso_configurations'

    id = db.Column(db.Integer, primary_key=True)

    provider_type = db.Column(db.String(30), nullable=False, index=True)
    # ldap | active_directory | saml | oauth2 | openid_connect

    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    # Connection settings
    server_url = db.Column(db.String(255), nullable=True)  # ldap:// or ldaps://
    port = db.Column(db.Integer, nullable=True, default=636)
    bind_dn = db.Column(db.String(255), nullable=True)
    bind_password = db.Column(db.String(255), nullable=True)  # Should be encrypted
    base_dn = db.Column(db.String(255), nullable=True)
    user_search_filter = db.Column(db.String(255), nullable=True)
    # Example: (sAMAccountName=%(username)s)

    # Attribute mappings
    attr_username = db.Column(db.String(50), default='sAMAccountName', nullable=False)
    attr_email = db.Column(db.String(50), default='mail', nullable=False)
    attr_full_name = db.Column(db.String(50), default='displayName', nullable=False)
    attr_phone = db.Column(db.String(50), default='telephoneNumber', nullable=True)
    attr_department = db.Column(db.String(50), default='department', nullable=True)

    # SAML / OAuth2 settings
    saml_entity_id = db.Column(db.String(255), nullable=True)
    saml_idp_url = db.Column(db.String(500), nullable=True)
    saml_sp_certificate = db.Column(db.Text, nullable=True)
    saml_sp_private_key = db.Column(db.Text, nullable=True)
    saml_idp_certificate = db.Column(db.Text, nullable=True)

    oauth_client_id = db.Column(db.String(255), nullable=True)
    oauth_client_secret = db.Column(db.String(255), nullable=True)
    oauth_authorization_url = db.Column(db.String(500), nullable=True)
    oauth_token_url = db.Column(db.String(500), nullable=True)
    oauth_userinfo_url = db.Column(db.String(500), nullable=True)
    oauth_scopes = db.Column(db.String(255), default='openid email profile', nullable=True)

    # Auto-provisioning
    auto_create_user = db.Column(db.Boolean, default=True, nullable=False)
    default_role = db.Column(db.String(50), default='user', nullable=False)
    default_department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)

    # SSL/TLS
    use_ssl = db.Column(db.Boolean, default=True, nullable=False)
    verify_ssl = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<SSOConfiguration {self.name} type={self.provider_type}>"


class SSOUserMapping(db.Model):
    __tablename__ = 'sso_user_mappings'

    id = db.Column(db.Integer, primary_key=True)
    sso_config_id = db.Column(db.Integer, db.ForeignKey('sso_configurations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    external_id = db.Column(db.String(255), nullable=False, index=True)
    external_username = db.Column(db.String(120), nullable=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sso_config = db.relationship('SSOConfiguration', lazy='selectin')
    user = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<SSOUserMapping user={self.user_id} external={self.external_id}>"
