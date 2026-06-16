"""
FileService — secure file management with tenant isolation
"""
import os
import hashlib
from datetime import datetime, timezone
from flask import g, current_app
from werkzeug.utils import secure_filename
from app.extensions import db


class FileService:
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'csv', 'dcm'}

    @staticmethod
    def _sha256(file_data: bytes) -> str:
        return hashlib.sha256(file_data).hexdigest()

    @staticmethod
    def _tenant_path(tenant_id: int | None, filename: str) -> str:
        tenant_part = f"tenant_{tenant_id}" if tenant_id else "no_tenant"
        return os.path.join(tenant_part, filename)

    @staticmethod
    def allowed_file(filename: str) -> bool:
        ext = filename.rsplit('.', 1)[-1].lower()
        return ext in FileService.ALLOWED_EXTENSIONS

    @staticmethod
    def upload(file_storage, related_entity_type: str, related_entity_id: int, description: str = "") -> dict | None:
        if not file_storage or not file_storage.filename:
            return None
        if not FileService.allowed_file(file_storage.filename):
            return None

        original_name = secure_filename(file_storage.filename)
        file_data = file_storage.read()
        file_hash = FileService._sha256(file_data)
        tenant_id = getattr(g, 'tenant_id', None)

        upload_dir = os.path.join(
            current_app.root_path, 'uploads',
            FileService._tenant_path(tenant_id, '')
        )
        os.makedirs(upload_dir, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        stored_name = f"{ts}_{file_hash[:12]}_{original_name}"
        file_path = os.path.join(upload_dir, stored_name)

        with open(file_path, 'wb') as f:
            f.write(file_data)

        from models.file_management import FileUpload
        upload = FileUpload(
            tenant_id=tenant_id,
            filename=stored_name,
            original_filename=original_name,
            file_path=file_path,
            file_hash=file_hash,
            file_size=len(file_data),
            file_type=file_storage.content_type or 'application/octet-stream',
            file_extension=original_name.rsplit('.', 1)[-1].lower(),
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            uploaded_by=getattr(g, 'current_user', None) and g.current_user.id or 0,
            description=description,
        )
        db.session.add(upload)
        db.session.commit()
        return {"id": upload.id, "filename": original_name, "hash": file_hash}

    @staticmethod
    def get_by_entity(related_entity_type: str, related_entity_id: int, tenant_id: int | None = None) -> list:
        from models.file_management import FileUpload
        tid = tenant_id or getattr(g, 'tenant_id', None)
        query = FileUpload.query.filter_by(
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        if tid:
            query = query.filter_by(tenant_id=tid)
        return query.order_by(FileUpload.uploaded_at.desc()).all()

    @staticmethod
    def delete(file_id: int) -> bool:
        from models.file_management import FileUpload
        upload = FileUpload.query.get(file_id)
        if not upload:
            return False
        try:
            if os.path.exists(upload.file_path):
                os.remove(upload.file_path)
            db.session.delete(upload)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False