"""
HL7 v2 message generation utilities — build ER7-encoded messages for sending to
external systems (LIS/HIS/HL7 gateways) over MLLP or HTTP.

Provides generic segment helpers plus convenience builders for the trigger events
supported by the inbound MLLP service (ADT, ORM, ORU, SIU, RDE, RDS, MDM) and
ACK messages. No external dependency on the ``hl7`` package is required.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import Any

MLLP_START = b'\x0b'
MLLP_END = b'\x1c\x0d'
DEFAULT_SEPARATOR = '|'
ENCODING_CHARS = '^~\\&'


def _now_ts() -> str:
    return datetime.now(UTC).strftime('%Y%m%d%H%M%S')


def _str(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return '~'.join(_str(v) for v in value)
    return str(value).replace('\r', '').replace('\n', '')


def build_segment(name: str, fields: list[Any]) -> str:
    """Join a segment name with its fields using the HL7 field separator."""
    return '|'.join([name] + [_str(f) for f in fields])


def build_msh(
    sending_app: str = 'MEDICAL',
    sending_facility: str = '',
    receiving_app: str = 'EXTERNAL',
    receiving_facility: str = '',
    message_type: str = 'ADT^A01',
    control_id: str | None = None,
    processing_id: str = 'P',
    version: str = '2.5',
    message_time: str | None = None,
) -> str:
    """Build an MSH segment."""
    ctrl = control_id or str(int(datetime.now(UTC).timestamp()))
    fields = [
        ENCODING_CHARS,
        sending_app,
        sending_facility,
        receiving_app,
        receiving_facility,
        message_time or _now_ts(),
        '',
        message_type,
        ctrl,
        processing_id,
        version,
    ]
    return build_segment('MSH', fields)


def build_pid(
    patient_id: Any,
    family_name: str = '',
    given_name: str = '',
    birth_date: str = '',
    gender: str = '',
    address: str = '',
    phone: str = '',
    national_id: str = '',
) -> str:
    """Build a PID segment."""
    name = f'{family_name}^{given_name}' if (family_name or given_name) else ''
    identifier = patient_id
    if national_id:
        identifier = f'{patient_id}^^^{national_id}'
    fields = [
        '',  # PID-1 set ID
        '',  # PID-2 patient id (external, deprecated)
        identifier,  # PID-3
        '',  # PID-4 alternate
        name,  # PID-5
        '',  # PID-6 mother's maiden
        birth_date,  # PID-7
        gender,  # PID-8
        '',  # PID-9 alias
        '',  # PID-10 race
        address,  # PID-11 address
        '',  # PID-12 county
        phone,  # PID-13 phone home
    ]
    return build_segment('PID', fields)


def build_pv1(
    visit_id: Any = '',
    patient_class: str = 'O',
    location: str = '',
    attending_doctor: str = '',
) -> str:
    """Build a PV1 segment."""
    fields = [
        '',  # PV1-1 set id
        patient_class,  # PV1-2
        location,  # PV1-3
        '',  # PV1-4
        '',  # PV1-5
        '',  # PV1-6
        attending_doctor,  # PV1-7
    ]
    # attach visit id into PV1-19 (visit number) when provided
    while len(fields) < 19:
        fields.append('')
    if len(fields) == 19:
        fields.append(_str(visit_id))
    else:
        fields[19] = _str(visit_id)
    return build_segment('PV1', fields)


def assemble_message(segments: list[str]) -> str:
    """Join segments with CR and trailing CR."""
    return '\r'.join(s for s in segments if s) + '\r'


def build_ack(
    msh_fields: list[str],
    ack_code: str = 'AA',
    text: str = '',
    control_id: str | None = None,
) -> str:
    """Build a minimal ACK message."""
    now = _now_ts()
    msh = build_msh(
        sending_app=msh_fields[4] if len(msh_fields) > 4 else 'RECEIVING',
        sending_facility=msh_fields[5] if len(msh_fields) > 5 else '',
        receiving_app=msh_fields[2] if len(msh_fields) > 2 else 'SENDING',
        receiving_facility=msh_fields[3] if len(msh_fields) > 3 else '',
        message_type='ACK',
        control_id=control_id or (msh_fields[9] if len(msh_fields) > 9 else None),
        message_time=now,
    )
    ctrl_id = msh_fields[9] if len(msh_fields) > 9 else '1'
    msa = build_segment('MSA', [ack_code, ctrl_id, text])
    return assemble_message([msh, msa])


# ---------------------------------------------------------------------------
# Trigger-event specific builders
# ---------------------------------------------------------------------------


def build_adt(
    patient_id: Any,
    trigger_event: str = 'A01',
    family_name: str = '',
    given_name: str = '',
    birth_date: str = '',
    gender: str = '',
    visit_id: Any = '',
    **kwargs: Any,
) -> str:
    event = trigger_event.upper()
    msg_type = f'ADT^{event}'
    segments = [
        build_msh(message_type=msg_type, **_msh_kwargs(kwargs)),
        build_pid(patient_id, family_name, given_name, birth_date, gender),
    ]
    if visit_id not in ('', None):
        segments.append(build_pv1(visit_id))
    return assemble_message(segments)


def build_orm(
    patient_id: Any,
    order_id: Any = '',
    trigger_event: str = 'O01',
    family_name: str = '',
    given_name: str = '',
    test_code: str = '',
    test_name: str = '',
    **kwargs: Any,
) -> str:
    msg_type = f'ORM^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    segments.append(build_pid(patient_id, family_name, given_name))
    orc = build_segment(
        'ORC',
        ['NW', _str(order_id), _str(order_id), '', 'CM'],
    )
    segments.append(orc)
    if test_code or test_name:
        obr = build_segment(
            'OBR',
            ['', _str(order_id), _str(order_id), f'{test_code}^{test_name}'],
        )
        segments.append(obr)
    return assemble_message(segments)


def build_oru(
    patient_id: Any,
    trigger_event: str = 'R01',
    family_name: str = '',
    given_name: str = '',
    results: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> str:
    msg_type = f'ORU^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    segments.append(build_pid(patient_id, family_name, given_name))
    obr = build_segment('OBR', ['', '1', '1', 'LAB^Lab Result'])
    segments.append(obr)
    for r in results or []:
        obx = build_segment(
            'OBX',
            [
                '1',
                'NM' if _is_number(r.get('value')) else 'ST',
                f"{r.get('code', '')}^{r.get('name', '')}",
                '',
                _str(r.get('value')),
                r.get('unit', ''),
                r.get('reference_range', ''),
                r.get('flag', ''),
            ],
        )
        segments.append(obx)
    return assemble_message(segments)


def build_siu(
    patient_id: Any,
    trigger_event: str = 'S12',
    family_name: str = '',
    given_name: str = '',
    appointment_id: Any = '',
    start_time: str = '',
    end_time: str = '',
    location: str = '',
    **kwargs: Any,
) -> str:
    """SIU^S12 appointment scheduling message."""
    msg_type = f'SIU^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    sch = build_segment(
        'SCH',
        [
            _str(appointment_id),
            '',
            '',
            '',
            '',
            '',
            start_time or _now_ts(),
            end_time or '',
            '',
            '',
            location,
        ],
    )
    segments.append(sch)
    segments.append(build_pid(patient_id, family_name, given_name))
    if kwargs.get('visit_id') not in (None, ''):
        segments.append(build_pv1(kwargs.get('visit_id'), location=location))
    return assemble_message(segments)


def build_rde(
    patient_id: Any,
    trigger_event: str = 'O11',
    family_name: str = '',
    given_name: str = '',
    order_id: Any = '',
    drug_code: str = '',
    drug_name: str = '',
    dose: Any = '',
    route: str = '',
    frequency: str = '',
    **kwargs: Any,
) -> str:
    """RDE^O11 pharmacy encoded order message."""
    msg_type = f'RDE^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    segments.append(build_pid(patient_id, family_name, given_name))
    orc = build_segment('ORC', ['NW', _str(order_id), _str(order_id)])
    segments.append(orc)
    rxe = build_segment(
        'RXE',
        [
            '',
            f'{drug_code}^{drug_name}',
            _str(dose),
            '',
            route,
            frequency,
        ],
    )
    segments.append(rxe)
    return assemble_message(segments)


def build_rds(
    patient_id: Any,
    trigger_event: str = 'O13',
    family_name: str = '',
    given_name: str = '',
    dispense_id: Any = '',
    drug_code: str = '',
    drug_name: str = '',
    quantity: Any = '',
    **kwargs: Any,
) -> str:
    """RDS^O13 pharmacy dispense message."""
    msg_type = f'RDS^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    segments.append(build_pid(patient_id, family_name, given_name))
    orc = build_segment('ORC', ['RE', _str(dispense_id), _str(dispense_id)])
    segments.append(orc)
    rxd = build_segment(
        'RXD',
        [
            _str(dispense_id),
            f'{drug_code}^{drug_name}',
            _str(quantity),
        ],
    )
    segments.append(rxd)
    return assemble_message(segments)


def build_mdm(
    patient_id: Any,
    trigger_event: str = 'T02',
    family_name: str = '',
    given_name: str = '',
    document_id: Any = '',
    document_type: str = '',
    title: str = '',
    text: str = '',
    **kwargs: Any,
) -> str:
    """MDM^T02 medical document management message."""
    msg_type = f'MDM^{trigger_event.upper()}'
    segments = [build_msh(message_type=msg_type, **_msh_kwargs(kwargs))]
    segments.append(build_pid(patient_id, family_name, given_name))
    txa = build_segment(
        'TXA',
        [
            '1',
            document_type,
            'TX',
            '',
            '',
            _now_ts(),
            '',
            '',
            '',
            '',
            _str(document_id),
            title,
        ],
    )
    segments.append(txa)
    if text:
        segments.append(build_segment('OBX', ['1', 'TX', 'DOC', '', text]))
    return assemble_message(segments)


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------

_BUILDERS = {
    'ADT': build_adt,
    'ORM': build_orm,
    'ORU': build_oru,
    'SIU': build_siu,
    'RDE': build_rde,
    'RDS': build_rds,
    'MDM': build_mdm,
}


def _prefix(msg_type: str) -> str:
    return msg_type.split('^', maxsplit=1)[0].upper().strip()


def _msh_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        'sending_app',
        'sending_facility',
        'receiving_app',
        'receiving_facility',
        'control_id',
        'processing_id',
        'version',
        'message_time',
    }
    return {k: v for k, v in kwargs.items() if k in allowed}


def _is_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def generate_message(message_type: str, data: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Generate an HL7 v2 message for the given message type.

    ``data`` (or keyword arguments) is forwarded to the type-specific builder.
    """
    data = dict(data or {})
    data.update(kwargs)
    prefix = _prefix(message_type)
    # allow message_type to carry trigger event
    if '^' in message_type and 'trigger_event' not in data:
        data['trigger_event'] = message_type.split('^', 1)[1]
    builder = _BUILDERS.get(prefix)
    if builder is None:
        # Minimal fallback: MSH only
        return assemble_message([build_msh(message_type=message_type)])
    # Remove builder-unknown msh kwargs already handled via _msh_kwargs inside builders
    return builder(**data)


def build_message(message_type: str, payload: Any = None, **kwargs: Any) -> str:
    if isinstance(payload, dict):
        kwargs = {**payload, **kwargs}
    return generate_message(message_type, kwargs)


def create_message(message_type: str, *args: Any, **kwargs: Any) -> str:
    return generate_message(message_type, **kwargs)


def make_message(message_type: str, **kwargs: Any) -> str:
    return generate_message(message_type, **kwargs)


def render_message(message_type: str, **kwargs: Any) -> str:
    return generate_message(message_type, **kwargs)


# Aliases for common trigger events
def build_adt_a01(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'A01')
    return build_adt(*a, **k)


def build_adt_a04(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'A04')
    return build_adt(*a, **k)


def build_adt_a08(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'A08')
    return build_adt(*a, **k)


def build_orm_o01(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'O01')
    return build_orm(*a, **k)


def build_oru_r01(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'R01')
    return build_oru(*a, **k)


def build_siu_s12(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'S12')
    return build_siu(*a, **k)


def build_rde_o11(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'O11')
    return build_rde(*a, **k)


def build_rds_o13(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'O13')
    return build_rds(*a, **k)


def build_mdm_t02(*a: Any, **k: Any) -> str:
    k.setdefault('trigger_event', 'T02')
    return build_mdm(*a, **k)


# ---------------------------------------------------------------------------
# MLLP framing / sending
# ---------------------------------------------------------------------------


def frame_mllp(message: str) -> bytes:
    return MLLP_START + message.encode('utf-8') + MLLP_END


def send_mllp(
    host: str,
    port: int,
    message: str,
    timeout: float = 10.0,
) -> str:
    """Send a message over MLLP and return the ACK (without framing)."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(frame_mllp(message))
        buf = b''
        while MLLP_END not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    # strip framing
    if MLLP_START in buf and MLLP_END in buf:
        start = buf.index(MLLP_START)
        end = buf.index(MLLP_END, start)
        return buf[start + 1 : end].decode('utf-8', errors='replace')
    return buf.decode('utf-8', errors='replace')


# Aliases
send_message = send_mllp
send_hl7_message = send_mllp
send_to_external = send_mllp
transmit_message = send_mllp
transmit_hl7 = send_mllp
send_hl7 = send_mllp


class HL7MessageGenerator:
    """Class-based facade for generation utilities."""

    @staticmethod
    def generate(message_type: str, *args: Any, **kwargs: Any) -> str:
        return generate_message(message_type, *args, **kwargs)

    @staticmethod
    def build(message_type: str, *args: Any, **kwargs: Any) -> str:
        return generate_message(message_type, *args, **kwargs)

    @staticmethod
    def send(host: str, port: int, message: str, timeout: float = 10.0) -> str:
        return send_mllp(host, port, message, timeout=timeout)

    # convenience
    build_adt = staticmethod(build_adt)
    build_orm = staticmethod(build_orm)
    build_oru = staticmethod(build_oru)
    build_siu = staticmethod(build_siu)
    build_rde = staticmethod(build_rde)
    build_rds = staticmethod(build_rds)
    build_mdm = staticmethod(build_mdm)
    build_ack = staticmethod(build_ack)


# Alias classes
HL7Generator = HL7MessageGenerator
HL7MessageBuilder = HL7MessageGenerator
MessageGenerator = HL7MessageGenerator


# Validation re-export
try:
    from services.hl7_mllp_service import validate_hl7_message
except Exception:  # pragma: no cover
    def validate_hl7_message(raw: str) -> tuple[bool, str]:  # type: ignore[misc]
        return ('MSH' in (raw or ''), '' if 'MSH' in (raw or '') else 'Missing MSH')


def validate_message(raw: str) -> tuple[bool, str]:
    return validate_hl7_message(raw)


__all__ = [
    'HL7Generator',
    'HL7MessageBuilder',
    'HL7MessageGenerator',
    'MessageGenerator',
    'assemble_message',
    'build_ack',
    'build_adt',
    'build_adt_a01',
    'build_adt_a04',
    'build_adt_a08',
    'build_mdm',
    'build_mdm_t02',
    'build_message',
    'build_msh',
    'build_orm',
    'build_orm_o01',
    'build_oru',
    'build_oru_r01',
    'build_pid',
    'build_pv1',
    'build_rde',
    'build_rde_o11',
    'build_rds',
    'build_rds_o13',
    'build_siu',
    'build_siu_s12',
    'create_message',
    'frame_mllp',
    'generate_message',
    'make_message',
    'render_message',
    'send_hl7',
    'send_hl7_message',
    'send_message',
    'send_mllp',
    'send_to_external',
    'transmit_hl7',
    'transmit_message',
    'validate_hl7_message',
    'validate_message',
]
