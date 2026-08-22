"""
FileService — secure file management with tenant isolation and S3/MinIO support
"""

import hashlib
import os
from datetime import UTC, datetime

from flask import current_app, g
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.extensions import db
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class FileService:
    # Default allowed extensions (can be overridden by config)
    DEFAULT_ALLOWED_EXTENSIONS = {
        'png',
        'jpg',
        'jpeg',
        'gif',
        'pdf',
        'doc',
        'docx',
        'xls',
        'xlsx',
        'txt',
        'csv',
        'dcm',
        'dicom',
    }

    @staticmethod
    def _sha256(file_data: bytes) -> str:
        return hashlib.sha256(file_data).hexdigest()

    @staticmethod
    def _get_s3_client():
        """Get configured S3/MinIO client"""
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError('boto3 is required for S3/MinIO storage') from exc

        endpoint_url = current_app.config.get('S3_ENDPOINT_URL')
        region = current_app.config.get('S3_REGION', 'us-east-1')
        access_key = current_app.config.get('S3_ACCESS_KEY')
        secret_key = current_app.config.get('S3_SECRET_KEY')
        force_path_style = current_app.config.get('S3_FORCE_PATH_STYLE', False)

        client_kwargs = {
            'region_name': region,
        }
        if endpoint_url:
            client_kwargs['endpoint_url'] = endpoint_url
        if access_key and secret_key:
            client_kwargs['aws_access_key_id'] = access_key
            client_kwargs['aws_secret_access_key'] = secret_key
        if force_path_style:
            client_kwargs['config'] = __import__('botocore.config', fromlist=['Config']).Config(
                s3={'addressing_style': 'path'}
            )

        return boto3.client('s3', **client_kwargs)

    @staticmethod
    def _get_allowed_extensions() -> set:
        """Get allowed extensions from config or use defaults"""
        allowed = current_app.config.get('ALLOWED_UPLOAD_EXTENSIONS')
        if allowed:
            return {ext.strip().lower() for ext in allowed}
        return FileService.DEFAULT_ALLOWED_EXTENSIONS

    @staticmethod
    def _get_max_file_size() -> int:
        """Get max file size in bytes from config"""
        max_mb = current_app.config.get('MAX_FILE_SIZE_MB', 16)
        return max_mb * 1024 * 1024

    @staticmethod
    def _get_storage_backend() -> str:
        """Get storage backend from config"""
        return current_app.config.get('STORAGE_BACKEND', 'local').lower()

    @staticmethod
    def _get_s3_bucket() -> str:
        """Get S3 bucket from config"""
        return current_app.config.get('S3_BUCKET', 'medical-uploads')

    @staticmethod
    def _tenant_path(tenant_id: int | None, filename: str) -> str:
        tenant_part = f'tenant_{tenant_id}' if tenant_id else 'no_tenant'
        return os.path.join(tenant_part, filename)

    @staticmethod
    def allowed_file(filename: str) -> bool:
        ext = filename.rsplit('.', 1)[-1].lower()
        return ext in FileService._get_allowed_extensions()

    @staticmethod
    def validate_file(file_storage, filename: str) -> tuple[bool, str | None]:
        """
        Validate file before upload.
        Returns (is_valid, error_message)
        """
        if not file_storage or not filename:
            return False, 'ملف غير صالح'

        # Check extension
        if not FileService.allowed_file(filename):
            allowed = ', '.join(sorted(FileService._get_allowed_extensions()))
            return False, f'نوع الملف غير مسموح. المسموح: {allowed}'

        # Check file size (read first chunk to check)
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(0)

        max_size = FileService._get_max_file_size()
        if file_size > max_size:
            max_mb = current_app.config.get('MAX_FILE_SIZE_MB', 16)
            return False, f'حجم الملف يتجاوز الحد المسموح ({max_mb}MB)'

        # Check MIME type matches extension
        ext = filename.rsplit('.', 1)[-1].lower()
        mime_map = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'dcm': 'application/dicom',
            'dicom': 'application/dicom',
        }
        expected_mime = mime_map.get(ext)
        if expected_mime and file_storage.content_type != expected_mime:
            # Allow but log warning
            current_app.logger.warning(
                f'MIME type mismatch: expected {expected_mime}, got {file_storage.content_type} for {filename}'
            )

        return True, None

    @staticmethod
    def upload(
        file_storage, related_entity_type: str, related_entity_id: int, description: str = ''
    ) -> dict | None:
        if not file_storage or not file_storage.filename:
            return None

        original_name = secure_filename(file_storage.filename)
        is_valid, error = FileService.validate_file(file_storage, original_name)
        if not is_valid:
            current_app.logger.warning(f'File validation failed: {error}')
            return None

        file_data = file_storage.read()
        file_hash = FileService._sha256(file_data)
        tenant_id = getattr(g, 'tenant_id', None)
        storage_backend = FileService._get_storage_backend()

        ts = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
        stored_name = f'{ts}_{file_hash[:12]}_{original_name}'

        from models.file_management import FileUpload

        if storage_backend in ('s3', 'minio'):
            # Upload to S3/MinIO
            s3_client = FileService._get_s3_client()
            bucket = FileService._get_s3_bucket()
            s3_key = FileService._tenant_path(tenant_id, stored_name)

            try:
                s3_client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=file_data,
                    ContentType=file_storage.content_type or 'application/octet-stream',
                    Metadata={
                        'original_filename': original_name,
                        'file_hash': file_hash,
                        'tenant_id': str(tenant_id) if tenant_id else 'no_tenant',
                        'related_entity_type': related_entity_type,
                        'related_entity_id': str(related_entity_id),
                    },
                )
                # Get ETag for integrity verification
                etag = s3_client.head_object(Bucket=bucket, Key=s3_key)['ETag'].strip('"')

                upload = FileUpload(
                    tenant_id=tenant_id,
                    filename=stored_name,
                    original_filename=original_name,
                    file_path=s3_key,  # Store S3 key in file_path for compatibility
                    file_hash=file_hash,
                    file_size=len(file_data),
                    file_type=file_storage.content_type or 'application/octet-stream',
                    file_extension=original_name.rsplit('.', 1)[-1].lower(),
                    storage_backend=storage_backend,
                    s3_key=s3_key,
                    s3_bucket=bucket,
                    s3_region=current_app.config.get('S3_REGION', 'us-east-1'),
                    s3_etag=etag,
                    related_entity_type=related_entity_type,
                    related_entity_id=related_entity_id,
                    uploaded_by=(getattr(g, 'current_user', None) and g.current_user.id) or 0,
                    description=description,
                )
            except Exception:
                current_app.logger.exception('S3 upload failed:')
                return None
        else:
            # Local storage (legacy)
            upload_dir = os.path.join(
                current_app.root_path, 'uploads', FileService._tenant_path(tenant_id, '')
            )
            os.makedirs(upload_dir, exist_ok=True)

            file_path = os.path.join(upload_dir, stored_name)

            with open(file_path, 'wb') as f:
                f.write(file_data)

            upload = FileUpload(
                tenant_id=tenant_id,
                filename=stored_name,
                original_filename=original_name,
                file_path=file_path,
                file_hash=file_hash,
                file_size=len(file_data),
                file_type=file_storage.content_type or 'application/octet-stream',
                file_extension=original_name.rsplit('.', 1)[-1].lower(),
                storage_backend='local',
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                uploaded_by=(getattr(g, 'current_user', None) and g.current_user.id) or 0,
                description=description,
            )

        db.session.add(upload)
        safe_commit(db.session, error_message='Failed to save file upload record', reraise=True)
        return {'id': upload.id, 'filename': original_name, 'hash': file_hash}

    @staticmethod
    def generate_presigned_url(upload, expiry: int | None = None) -> str | None:
        """Generate pre-signed URL for S3/MinIO object"""
        if upload.storage_backend not in ('s3', 'minio'):
            return None

        try:
            s3_client = FileService._get_s3_client()
            bucket = upload.s3_bucket or FileService._get_s3_bucket()
            key = upload.s3_key or upload.file_path

            if not bucket or not key:
                return None

            if expiry is None:
                expiry = current_app.config.get('S3_PRESIGNED_URL_EXPIRY', 3600)

            return s3_client.generate_presigned_url(
                'get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=expiry
            )
        except Exception:
            current_app.logger.exception('Failed to generate presigned URL:')
            return None

    @staticmethod
    def download_file(upload) -> tuple[bytes, str, str] | None:
        """
        Download file content.
        Returns (file_data, original_filename, content_type) or None
        """
        if upload.storage_backend in ('s3', 'minio'):
            try:
                s3_client = FileService._get_s3_client()
                bucket = upload.s3_bucket or FileService._get_s3_bucket()
                key = upload.s3_key or upload.file_path

                response = s3_client.get_object(Bucket=bucket, Key=key)
                file_data = response['Body'].read()

                # Verify integrity
                if upload.file_hash:
                    actual_hash = FileService._sha256(file_data)
                    if actual_hash != upload.file_hash:
                        current_app.logger.error(f'File integrity check failed for {upload.id}')
                        return None

                return file_data, upload.original_filename, upload.file_type
            except Exception:
                current_app.logger.exception('S3 download failed:')
                return None
        else:
            # Local storage
            file_path = upload.file_path
            if not file_path or not os.path.exists(file_path):
                return None
            try:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                return file_data, upload.original_filename, upload.file_type
            except Exception:
                current_app.logger.exception('Local file download failed:')
                return None

    @staticmethod
    def get_by_entity(
        related_entity_type: str, related_entity_id: int, tenant_id: int | None = None
    ) -> list:
        from models.file_management import FileUpload

        tid = tenant_id or getattr(g, 'tenant_id', None)
        query = select(FileUpload)
        if tid:
            query = query.filter_by(tenant_id=tid)
        return query.order_by(FileUpload.uploaded_at.desc()).all()

    @staticmethod
    def delete(file_id: int) -> bool:
        from models.file_management import FileUpload

        try:
            upload = get_tenant_record(FileUpload, file_id)
        except TenantContextError:
            return False

        try:
            if upload.storage_backend in ('s3', 'minio'):
                s3_client = FileService._get_s3_client()
                bucket = upload.s3_bucket or FileService._get_s3_bucket()
                key = upload.s3_key or upload.file_path
                if bucket and key:
                    s3_client.delete_object(Bucket=bucket, Key=key)
            # Local storage
            elif upload.file_path and os.path.exists(upload.file_path):
                os.remove(upload.file_path)

            db.session.delete(upload)
            return safe_commit(db.session, error_message='Failed to delete file record')
        except Exception:
            current_app.logger.exception('File delete failed:')
            return False

    @staticmethod
    def get_file_stream(upload, chunk_size: int = 8192):
        """Stream file content for large files (S3 only)"""
        if upload.storage_backend not in ('s3', 'minio'):
            return None

        try:
            s3_client = FileService._get_s3_client()
            bucket = upload.s3_bucket or FileService._get_s3_bucket()
            key = upload.s3_key or upload.file_path

            response = s3_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].iter_chunks(chunk_size=chunk_size)
        except Exception:
            current_app.logger.exception('S3 stream failed:')
            return None
