"""Behavioural tests for services.hl7_message_generator (HL7 v2 builders)."""

from __future__ import annotations

import socket
import threading

import services.hl7_message_generator as hl7


class TestSegments:
    def test_build_segment_joins_with_pipes(self):
        assert hl7.build_segment('PID', ['1', 'abc']) == 'PID|1|abc'

    def test_build_segment_strips_newlines(self):
        assert hl7.build_segment('PID', ['1\r2\n']) == 'PID|12'

    def test_build_segment_list_values_become_repeats(self):
        assert hl7.build_segment('PID', [['a', 'b']]) == 'PID|a~b'

    def test_build_segment_none_is_empty(self):
        assert hl7.build_segment('PID', [None]) == 'PID|'


class TestMsh:
    def test_msh_contains_type_version_and_encoding(self):
        msh = hl7.build_msh(
            message_type='ADT^A01', control_id='C123', message_time='20260101120000'
        )
        assert msh.startswith('MSH|^~\\&|')
        parts = msh.split('|')
        assert parts[2] == 'MEDICAL'  # MSH-3 sending app
        assert parts[8] == 'ADT^A01'  # MSH-9 message type
        assert parts[9] == 'C123'  # MSH-10 control id
        assert parts[11] == '2.5'  # MSH-12 version

    def test_msh_defaults(self):
        msh = hl7.build_msh()
        assert '|P|2.5' in msh


class TestPid:
    def test_name_and_plain_identifier(self):
        pid = hl7.build_pid('P123', family_name='Ali', given_name='Hassan')
        parts = pid.split('|')
        assert parts[3] == 'P123'  # PID-3
        assert parts[5] == 'Ali^Hassan'  # PID-5

    def test_national_id_embedded_in_patient_id(self):
        pid = hl7.build_pid('P123', national_id='NAT42')
        parts = pid.split('|')
        assert parts[3] == 'P123^^^NAT42'

    def test_no_name_means_empty_field(self):
        pid = hl7.build_pid('P123')
        assert pid.split('|')[5] == ''


class TestPv1:
    def test_visit_number_lands_in_pv1_19(self):
        pv1 = hl7.build_pv1('V555', patient_class='I', attending_doctor='DR-7')
        parts = pv1.split('|')
        assert len(parts) == 20  # 'PV1' + 19 fields
        assert parts[1] == ''  # PV1-1 set id
        assert parts[2] == 'I'  # PV1-2 patient class
        assert parts[7] == 'DR-7'  # PV1-7 attending doctor
        assert parts[19] == 'V555'  # PV1-19 visit number

    def test_no_visit_number_gives_empty_pv1_19(self):
        parts = hl7.build_pv1().split('|')
        assert len(parts) == 20
        assert parts[19] == ''


class TestAssemble:
    def test_trailing_cr(self):
        assert hl7.assemble_message(['MSH|a', 'PID|b']) == 'MSH|a\rPID|b\r'

    def test_empty_segments_skipped(self):
        assert hl7.assemble_message(['MSH|a', '']) == 'MSH|a\r'


class TestAck:
    def test_ack_reverses_direction_and_codes(self):
        msh_fields = [
            '',
            '^~\\&',
            'SENDAPP',
            'SENDFAC',
            'RECAPP',
            'RECFAC',
            '',
            '',
            'ADT^A01',
            'CTRL9',
            'P',
        ]
        ack = hl7.build_ack(msh_fields, ack_code='CA', text='rejected')
        parts_msh = ack.split('\r')[0].split('|')
        assert parts_msh[2] == 'RECAPP'  # sending is the original receiver
        assert parts_msh[4] == 'SENDAPP'  # receiving is the original sender
        msa = ack.split('\r')[1]
        assert msa.startswith('MSA|CA|CTRL9|rejected')

    def test_ack_minimal_fields(self):
        ack = hl7.build_ack(['', '', '', '', '', '', '', '', ''], ack_code='AA')
        assert '\rMSA|AA|1|' in ack


class TestBuilders:
    def test_build_adt_with_and_without_visit(self):
        with_visit = hl7.build_adt('P1', trigger_event='A01', visit_id='V9', family_name='Ali')
        assert 'MSH|^~\\&|' in with_visit
        assert '|ADT^A01|' in with_visit
        assert 'PID|' in with_visit
        assert 'PV1|' in with_visit
        without_visit = hl7.build_adt('P1', trigger_event='A01')
        assert 'PV1|' not in without_visit

    def test_build_adt_trigger_case_insensitive(self):
        assert 'ADT^A08' in hl7.build_adt('P1', trigger_event='a08')

    def test_build_orm_with_test(self):
        msg = hl7.build_orm('P1', order_id='O77', test_code='CBC', test_name='Complete Blood Count')
        assert 'ORC|NW|O77|O77|' in msg
        assert 'CBC^Complete Blood Count' in msg

    def test_build_oru_numeric_and_string_results(self):
        msg = hl7.build_oru(
            'P1',
            results=[
                {'code': 'HB', 'name': 'Hemoglobin', 'value': '13.5', 'unit': 'g/dL'},
                {'code': 'SEX', 'name': 'Sex', 'value': 'M'},
            ],
        )
        lines = [ln for ln in msg.split('\r') if ln.startswith('OBX')]
        assert len(lines) == 2
        assert lines[0].split('|')[2] == 'NM'
        assert lines[1].split('|')[2] == 'ST'
        assert '13.5' in lines[0]

    def test_build_siu_with_visit(self):
        msg = hl7.build_siu('P1', appointment_id='APT1', start_time='20260102090000', visit_id='V1')
        assert 'SCH|APT1' in msg
        assert 'PV1|' in msg

    def test_build_siu_without_visit(self):
        msg = hl7.build_siu('P1', appointment_id='APT2')
        assert 'PV1|' not in msg

    def test_build_rde_carries_drug_fields(self):
        msg = hl7.build_rde(
            'P1',
            order_id='RX1',
            drug_code='D100',
            drug_name='Amoxicillin',
            dose=500,
            route='PO',
            frequency='TID',
        )
        assert 'D100^Amoxicillin' in msg
        assert 'PO' in msg
        assert 'TID' in msg

    def test_build_rds_carries_dispense(self):
        msg = hl7.build_rds(
            'P1', dispense_id='DS1', drug_code='D100', drug_name='Amoxicillin', quantity=30
        )
        assert 'RXD|DS1|D100^Amoxicillin|30' in msg

    def test_build_mdm_with_and_without_body(self):
        with_text = hl7.build_mdm(
            'P1', document_id='DOC1', title='Discharge Summary', text='summary body'
        )
        assert 'TXA|1|' in with_text
        assert 'Discharge Summary' in with_text
        assert 'OBX|1|TX|DOC' in with_text
        without_text = hl7.build_mdm('P1', document_id='DOC2')
        assert 'DOC2' in without_text
        assert 'OBX' not in without_text


class TestDispatcher:
    def test_generate_message_dispatches_on_prefix(self):
        msg = hl7.generate_message('ORM^O01', patient_id='P9', order_id='O1')
        assert 'ORC|NW|O1|O1|' in msg

    def test_generate_message_propagates_trigger_from_type(self):
        msg = hl7.generate_message('ADT^A08', patient_id='P9')
        assert '|ADT^A08|' in msg

    def test_generate_message_unknown_type_falls_back_to_msh(self):
        msg = hl7.generate_message('ZZZ^A99', patient_id='P9')
        assert '|ZZZ^A99|' in msg
        assert 'PID|' not in msg

    def test_generate_message_accepts_positional_data_dict(self):
        msg = hl7.generate_message('ADT^A01', {'patient_id': 'P7', 'family_name': 'Ali'})
        assert 'P7' in msg

    def test_alias_entrypoints_agree(self):
        via_build = hl7.build_message('ADT^A01', patient_id='P1')
        via_create = hl7.create_message('ADT^A01', patient_id='P1')
        via_make = hl7.make_message('ADT^A01', patient_id='P1')
        via_render = hl7.render_message('ADT^A01', patient_id='P1')
        for msg in (via_build, via_create, via_make, via_render):
            assert '|ADT^A01|' in msg
            assert 'PID|' in msg

    def test_convenience_builders_set_trigger_event(self):
        assert '|ADT^A01|' in hl7.build_adt_a01('P1')
        assert '|ADT^A04|' in hl7.build_adt_a04('P1')
        assert '|ADT^A08|' in hl7.build_adt_a08('P1')
        assert '|ORM^O01|' in hl7.build_orm_o01('P1')
        assert '|ORU^R01|' in hl7.build_oru_r01('P1')
        assert '|SIU^S12|' in hl7.build_siu_s12('P1', appointment_id='APT')
        assert '|RDE^O11|' in hl7.build_rde_o11('P1')
        assert '|RDS^O13|' in hl7.build_rds_o13('P1')
        assert '|MDM^T02|' in hl7.build_mdm_t02('P1')


class TestMllp:
    def test_frame_mllp_wraps_with_start_and_end(self):
        framed = hl7.frame_mllp('MSH|^~\\&|')
        assert framed[0:1] == b'\x0b'
        assert framed[-2:] == b'\x1c\x0d'
        assert b'MSH|^~\\&|' in framed

    def test_send_mllp_roundtrip_with_real_socket(self):
        """Full MLLP round trip against a live localhost socket server."""
        port_holder: dict = {}

        ready = threading.Event()

        def serve():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            port_holder['port'] = server.getsockname()[1]
            ready.set()
            with server:
                conn, _ = server.accept()
                buf = b''
                with conn:
                    while hl7.MLLP_END not in buf:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                    ack = hl7.build_ack(
                        ['', '^~\\&', 'REC', 'FAC', 'SND', 'FAC2', '', '', 'ADT^A01', 'C9', 'P'],
                        ack_code='AA',
                    )
                    conn.sendall(hl7.frame_mllp(ack))

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        assert ready.wait(timeout=5)
        msg = hl7.build_adt('P1', trigger_event='A01')
        response = hl7.send_mllp('127.0.0.1', port_holder['port'], msg, timeout=5.0)
        thread.join(timeout=5)
        assert 'MSA|AA|C9|' in response

    def test_send_mllp_unsolicited_unframed_response(self):
        """If the peer returns raw bytes without framing, they come back decoded."""

        ready = threading.Event()

        def serve_raw():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('127.0.0.1', 0))
            server.listen(1)
            port_holder['port'] = server.getsockname()[1]
            ready.set()
            with server:
                conn, _ = server.accept()
                with conn:
                    buf = b''
                    while hl7.MLLP_END not in buf:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                    conn.sendall(b'RAW-ACK')

        port_holder: dict = {}
        thread = threading.Thread(target=serve_raw, daemon=True)
        thread.start()
        assert ready.wait(timeout=5)
        response = hl7.send_mllp('127.0.0.1', port_holder['port'], 'MSH|x', timeout=5.0)
        thread.join(timeout=5)
        assert response == 'RAW-ACK'


class TestFacade:
    def test_class_facade_generate_and_build(self):
        via_gen = hl7.HL7MessageGenerator.generate('ADT^A01', patient_id='P1')
        assert 'PID|' in via_gen
        via_build = hl7.HL7MessageGenerator.build('ORM^O01', patient_id='P1', order_id='O2')
        assert 'ORC|NW|O2|O2|' in via_build

    def test_class_facade_static_builders(self):
        assert hasattr(hl7.HL7MessageGenerator, 'build_adt')
        assert 'PID|' in hl7.HL7MessageGenerator.build_adt('P1')
        assert 'ORC|NW|' in hl7.HL7MessageGenerator.build_orm('P1', order_id='O1')
        assert 'OBX|' in hl7.HL7MessageGenerator.build_oru('P1', results=[{'value': '1'}])
        assert 'SCH|' in hl7.HL7MessageGenerator.build_siu('P1', appointment_id='AP')
        assert 'RXE|' in hl7.HL7MessageGenerator.build_rde('P1', order_id='O1')
        assert 'RXD|' in hl7.HL7MessageGenerator.build_rds('P1', dispense_id='D1')
        assert 'TXA|' in hl7.HL7MessageGenerator.build_mdm('P1', document_id='DOC')
        assert 'MSA|AA|' in hl7.HL7MessageGenerator.build_ack(['', '', '', '', '', '', '', '', ''])

    def test_class_aliases_are_same_object(self):
        assert hl7.HL7Generator is hl7.HL7MessageGenerator
        assert hl7.HL7MessageBuilder is hl7.HL7MessageGenerator
        assert hl7.MessageGenerator is hl7.HL7MessageGenerator


class TestValidation:
    def test_validate_message_accepts_generated_adt(self):
        msg = hl7.build_adt('P1', trigger_event='A01', visit_id='V1')
        ok, err = hl7.validate_message(msg)
        assert ok, err

    def test_validate_message_rejects_garbage(self):
        ok, err = hl7.validate_message('not hl7 at all')
        assert not ok
        assert err
