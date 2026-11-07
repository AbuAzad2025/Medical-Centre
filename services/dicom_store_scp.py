"""DICOM Store SCP — Receive DICOM images from modalities."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

DICOM_STORE_PORT = 11113
DICOM_STORE_AE_TITLE = 'MEDICAL_STORE'


class DICOMStoreSCP:
    """DICOM Store SCP for receiving images from modalities."""

    def __init__(self, ae_title: str = DICOM_STORE_AE_TITLE, port: int = DICOM_STORE_PORT):
        self.ae_title = ae_title
        self.port = port
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        """Start the DICOM Store SCP listener."""
        try:
            from pynetdicom import AE, evt
            from pynetdicom.sop_class import (
                CTImageStorage,
                MRImageStorage,
                SecondaryCaptureImageStorage,
                UltrasoundImageStorage,
                XRayAngiographicImageStorage,
            )
        except ImportError:
            logger.warning('pynetdicom not installed — DICOM Store SCP disabled')
            return

        ae = AE(ae_title=self.ae_title)
        storage_classes = [
            CTImageStorage,
            MRImageStorage,
            SecondaryCaptureImageStorage,
            UltrasoundImageStorage,
            XRayAngiographicImageStorage,
        ]
        for sc in storage_classes:
            ae.add_supported_context(sc)

        handlers = [(evt.EVT_C_STORE, self._handle_store)]
        self._ae = ae
        self._running = True
        self._thread = threading.Thread(target=self._run, args=(ae, handlers), daemon=True)
        self._thread.start()
        logger.info('DICOM Store SCP started on port %d (AE: %s)', self.port, self.ae_title)

    def _run(self, ae, handlers):
        ae.start_server(('', self.port), block=True, evt_handlers=handlers)

    def _handle_store(self, event):
        """Handle incoming C-STORE request."""
        try:
            ds = event.dataset
            ds.file_meta = event.file_meta
            # Save to storage
            import os

            storage_dir = os.environ.get('DICOM_STORAGE_DIR', 'dicom_storage')
            os.makedirs(storage_dir, exist_ok=True)
            filename = f'{ds.SOPInstanceUID}.dcm'
            filepath = os.path.join(storage_dir, filename)
            ds.save_as(filepath, write_like_original=False)
            logger.info('Stored DICOM instance: %s', ds.SOPInstanceUID)
            return 0x0000  # Success
        except Exception:
            logger.exception('DICOM store failed')
            return 0xC000  # Failure

    def stop(self):
        """Stop the DICOM Store SCP listener."""
        self._running = False
        if hasattr(self, '_ae'):
            self._ae.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info('DICOM Store SCP stopped')

    def is_running(self) -> bool:
        return self._running


# Singleton
dicom_store_scp = DICOMStoreSCP()
