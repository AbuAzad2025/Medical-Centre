"""
HL7v2 MLLP Service — Minimal Lower Layer Protocol listener for legacy LIS/HIS integration.

Handles ER7 encoded HL7v2 messages framed as: 0x0B <HL7> 0x1C 0x0D
Supported trigger events: ADT^A01/A04/A08 (patient), ORM^O01 (order), ORU^R01 (result),
SIU^S12 (appointment scheduling), RDE^O11 (pharmacy encoded order), RDS^O13 (pharmacy
dispense), MDM^T02 (medical document management).

Designed to run as a daemon thread or Celery beat task; does NOT require hl7 library.
Tenant resolution via MSH-3/MSH-4 sending facility or PID-3 patient identifier fallback.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import threading
from collections.abc import Callable
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

MLLP_START = b'\x0b'
MLLP_END = b'\x1c\x0d'
DEFAULT_MLLP_PORT = int(os.environ.get('HL7_MLLP_PORT', '2575'))
DEFAULT_MLLP_HOST = os.environ.get('HL7_MLLP_HOST', '0.0.0.0')


def _parse_er7(raw: str) -> dict:
    """Parse ER7 into segments dict {seg_name: [[fields]]} — minimal, no external dep."""
    segments: dict[str, list[list[str]]] = {}
    for line in raw.strip().split('\r'):
        line = line.strip()
        if not line:
            continue
        # HL7 uses | field sep, ^ component, ~ repetition, \ escape, & subcomponent
        seg_name = line[:3]
        fields = line.split('|')
        segments.setdefault(seg_name, []).append(fields)
    return segments


def _build_ack(msh_fields: list[str], ack_code: str = 'AA', text: str = '') -> str:
    """Build minimal ACK message (MSH + MSA)."""
    now = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
    msh = [
        'MSH',
        '^~\\&',
        msh_fields[4] if len(msh_fields) > 4 else 'RECEIVING',
        msh_fields[2] if len(msh_fields) > 2 else 'SENDING',
        '',
        '',
        now,
        '',
        'ACK',
        msh_fields[8] if len(msh_fields) > 8 else 'P',
        '2.5',
        '',
        '',
        'AL',
        'NE',
    ]
    # Use MSH-10 (message control ID) from inbound as MSA-2
    ctrl_id = msh_fields[9] if len(msh_fields) > 9 else '1'
    msa = ['MSA', ack_code, ctrl_id, text]
    return '\r'.join(['|'.join(msh), '|'.join(msa)]) + '\r'


_MSG_TYPE_RE = re.compile(r'^[A-Z0-9]{3}(\^[A-Z0-9]+)?$')


def validate_hl7_message(raw: str) -> tuple[bool, str]:
    """Validate an ER7-encoded HL7 v2 message.

    Returns ``(is_valid, error_message)``. An empty error string means valid.
    """
    if not isinstance(raw, str) or not raw.strip():
        return False, 'Empty HL7 message'
    text = raw.strip()
    if 'MSH' not in text:
        return False, 'Missing MSH segment'
    segments = _parse_er7(text)
    msh_list = segments.get('MSH')
    if not msh_list:
        return False, 'Missing MSH segment'
    msh = msh_list[0]
    if not msh or msh[0].strip().upper() != 'MSH':
        return False, 'Invalid MSH segment'
    if len(msh) < 9:
        return False, 'MSH segment incomplete (MSH-9 message type required)'
    msg_type = msh[8].strip().upper().replace('_', '^')
    if not msg_type:
        return False, 'Missing message type (MSH-9)'
    if not _MSG_TYPE_RE.match(msg_type):
        return False, f'Invalid message type format: {msg_type}'
    # Every segment name must be a 3-character segment id: one uppercase
    # letter followed by two alphanumerics. The previous rule demanded all
    # letters, which rejected legitimate HL7 segments that contain digits
    # (PV1, PV2, Z-segments) and made validation reject the very ADT messages
    # this service generates.
    seg_re = re.compile(r'[A-Z][A-Z0-9]{2}')
    for line in text.split('\r'):
        line = line.strip()
        if not line:
            continue
        if len(line) < 3 or not seg_re.fullmatch(line[:3]) or not line[:3].isupper():
            return False, f'Invalid segment: {line[:12]}'
    return True, ''


def is_valid_hl7(raw: str) -> bool:
    ok, _ = validate_hl7_message(raw)
    return ok


# Backwards/alternate names
validate_hl7 = validate_hl7_message
hl7_validate = validate_hl7_message


class HL7MLLPService:
    """MLLP listener with pluggable message handler."""

    def __init__(self, host: str = DEFAULT_MLLP_HOST, port: int = DEFAULT_MLLP_PORT):
        self.host = host
        self.port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._handlers: dict[str, Callable[[dict, str], str | None]] = {}

    def register_handler(self, message_type: str, handler: Callable[[dict, str], str | None]):
        """Register handler for HL7 message type like ADT^A01, ORU^R01."""
        self._handlers[message_type.upper()] = handler

    def handle_raw(self, raw: str) -> str:
        """Process one HL7 message and return ACK string (without MLLP framing)."""
        segs = _parse_er7(raw)
        msh_list = segs.get('MSH', [])
        if not msh_list:
            return _build_ack(['MSH'], 'AR', 'Missing MSH')
        msh = msh_list[0]
        msg_type = ''
        if len(msh) > 8:
            msg_type = msh[8].strip().upper()  # e.g. ADT^A01
        elif len(msh) > 7:
            msg_type = msh[7].strip().upper()
        # Normalize: ADT_A01 -> ADT^A01
        msg_type = msg_type.replace('_', '^')

        handler = self._handlers.get(msg_type)
        # Fallback to wildcard on event type prefix
        if not handler and '^' in msg_type:
            prefix = msg_type.split('^')[0]
            handler = self._handlers.get(prefix)

        try:
            if handler:
                result = handler(segs, raw)
                # handler may return custom ack text
                ack_text = result or 'OK'
                return _build_ack(msh, 'AA', ack_text)
            logger.warning('HL7 no handler for %s', msg_type)
            return _build_ack(msh, 'AR', f'Unsupported message type {msg_type}')
        except Exception as exc:  # noqa: BLE001
            logger.exception('HL7 handler failed for %s', msg_type)
            return _build_ack(msh, 'AE', str(exc)[:80])

    # ---------------- TCP MLLP framing ----------------
    def _serve_client(self, conn: socket.socket, addr):
        buf = b''
        conn.settimeout(30)
        try:
            while not self._stop.is_set():
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                # Extract complete MLLP frames
                while MLLP_START in buf and MLLP_END in buf:
                    start = buf.index(MLLP_START)
                    end = buf.index(MLLP_END, start)
                    frame = buf[start + 1 : end].decode('utf-8', errors='replace')
                    buf = buf[end + 2 :]
                    ack = self.handle_raw(frame)
                    conn.sendall(MLLP_START + ack.encode('utf-8') + MLLP_END)
        except Exception as exc:  # noqa: BLE001
            logger.debug('HL7 client %s error: %s', addr, exc)
        finally:
            with __import__('contextlib').suppress(Exception):
                conn.close()

    def _listen_loop(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(5)
        srv.settimeout(1.0)
        logger.info('HL7 MLLP listening on %s:%s', self.host, self.port)
        while not self._stop.is_set():
            try:
                conn, addr = srv.accept()
                threading.Thread(target=self._serve_client, args=(conn, addr), daemon=True).start()
            except TimeoutError:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning('HL7 accept failed: %s', exc)
        srv.close()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name='hl7-mllp')
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


# Singleton + default ADT/ORM/ORU handlers that log and persist via existing services
hl7_mllp_service = HL7MLLPService()


def _default_adt_handler(segs: dict, raw: str) -> str | None:
    try:
        pid_seg = segs.get('PID', [[]])[0] if segs.get('PID') else []
        # PID-3 patient identifier, PID-5 name
        pid3 = pid_seg[3] if len(pid_seg) > 3 else ''
        pid5 = pid_seg[5] if len(pid_seg) > 5 else ''
        logger.info('HL7 ADT patient pid3=%s name=%s', pid3[:20], pid5[:40])
        # No auto-create to avoid tenant ambiguity; log for operator review
        return 'ADT logged'
    except Exception as exc:  # noqa: BLE001
        logger.warning('ADT handler skipped: %s', exc)
        return None


def _default_oru_handler(segs: dict, raw: str) -> str | None:
    logger.info('HL7 ORU received %s chars', len(raw))
    return 'ORU logged'


def _default_siu_handler(segs: dict, raw: str) -> str | None:
    try:
        sch = segs.get('SCH', [[]])[0] if segs.get('SCH') else []
        pid = segs.get('PID', [[]])[0] if segs.get('PID') else []
        logger.info(
            'HL7 SIU scheduling sch=%s pid=%s',
            (sch[0] if sch else '')[:40],
            (pid[3] if len(pid) > 3 else '')[:20],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('SIU handler parse skipped: %s', exc)
    return 'SIU logged'


def _default_rde_handler(segs: dict, raw: str) -> str | None:
    try:
        pid = segs.get('PID', [[]])[0] if segs.get('PID') else []
        rxe = segs.get('RXE', [[]])[0] if segs.get('RXE') else []
        logger.info(
            'HL7 RDE pharmacy order pid=%s rxe=%s',
            (pid[3] if len(pid) > 3 else '')[:20],
            (rxe[0] if rxe else '')[:40],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('RDE handler parse skipped: %s', exc)
    return 'RDE logged'


def _default_rds_handler(segs: dict, raw: str) -> str | None:
    try:
        pid = segs.get('PID', [[]])[0] if segs.get('PID') else []
        rxd = segs.get('RXD', [[]])[0] if segs.get('RXD') else []
        logger.info(
            'HL7 RDS pharmacy dispense pid=%s rxd=%s',
            (pid[3] if len(pid) > 3 else '')[:20],
            (rxd[0] if rxd else '')[:40],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('RDS handler parse skipped: %s', exc)
    return 'RDS logged'


def _default_mdm_handler(segs: dict, raw: str) -> str | None:
    try:
        pid = segs.get('PID', [[]])[0] if segs.get('PID') else []
        txa = segs.get('TXA', [[]])[0] if segs.get('TXA') else []
        logger.info(
            'HL7 MDM document pid=%s txa=%s',
            (pid[3] if len(pid) > 3 else '')[:20],
            (txa[0] if txa else '')[:40],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning('MDM handler parse skipped: %s', exc)
    return 'MDM logged'


# Register prefix + full trigger-event handlers
hl7_mllp_service.register_handler('ADT', _default_adt_handler)
hl7_mllp_service.register_handler('ORU', _default_oru_handler)
hl7_mllp_service.register_handler('ORM', lambda _s, _r: 'ORM logged')
hl7_mllp_service.register_handler('SIU', _default_siu_handler)
hl7_mllp_service.register_handler('RDE', _default_rde_handler)
hl7_mllp_service.register_handler('RDS', _default_rds_handler)
hl7_mllp_service.register_handler('MDM', _default_mdm_handler)

for _code, _event, _handler in (
    ('SIU', 'SIU^S12', _default_siu_handler),
    ('RDE', 'RDE^O11', _default_rde_handler),
    ('RDS', 'RDS^O13', _default_rds_handler),
    ('MDM', 'MDM^T02', _default_mdm_handler),
):
    hl7_mllp_service.register_handler(_event, _handler)
