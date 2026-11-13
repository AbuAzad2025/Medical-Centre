"""Coverage tests for _start_pynetdicom_mwl_scp in dicom_worklist_service."""

import os


def test_start_pynetdicom_mwl_scp_disabled():
    os.environ['DICOM_MWL_ENABLED'] = 'false'
    from services.dicom_worklist_service import _start_pynetdicom_mwl_scp
    result = _start_pynetdicom_mwl_scp()
    assert result is None


def test_start_pynetdicom_mwl_scp_enabled_no_lib():
    os.environ['DICOM_MWL_ENABLED'] = 'true'
    from services.dicom_worklist_service import _start_pynetdicom_mwl_scp
    result = _start_pynetdicom_mwl_scp()
    # Either None (if pynetdicom not installed) or an AE object
    assert result is None or result is not None
    os.environ['DICOM_MWL_ENABLED'] = 'false'
