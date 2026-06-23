"""PWA routes — manifest + offline shell (§25.4)."""
from flask import Blueprint, jsonify, render_template, url_for

pwa_bp = Blueprint('pwa', __name__)


@pwa_bp.route('/manifest.webmanifest')
def manifest():
    """Dynamic manifest with tenant branding when available."""
    from flask import g
    ui = getattr(g, 'ui', None) or {}
    org = ui.get('organization_name') if isinstance(ui, dict) else getattr(ui, 'organization_name', None)
    primary = ui.get('primary_color') if isinstance(ui, dict) else getattr(ui, 'primary_color', None)
    primary = primary or '#0f4c81'
    return jsonify({
        'name': org or 'منصة آزاد الطبية',
        'short_name': (org or 'آزاد مد')[:12],
        'description': 'نظام المعلومات الصحية المتقدم',
        'start_url': '/',
        'scope': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': primary,
        'orientation': 'portrait-primary',
        'lang': 'ar',
        'dir': 'rtl',
        'icons': [
            {'src': url_for('static', filename='img/icon-192x192.png'), 'sizes': '192x192', 'type': 'image/png'},
            {'src': url_for('static', filename='img/icon-512x512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ],
        'categories': ['medical', 'health', 'productivity'],
    })


@pwa_bp.route('/offline')
def offline():
    return render_template('pwa/offline.html')
