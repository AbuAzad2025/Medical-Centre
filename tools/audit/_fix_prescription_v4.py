import io

P = 'routes/emergency/orders.py'
t = io.open(P, encoding='utf-8').read()

# Find the exact block to replace
old = '''            try:
                db.session.add(
                    AuditTrail(
                        entity_type='visit' if visit else 'patient',
                        entity_id=visit.id if visit else emergency.patient_id,
                        action='create',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description=f'\\u0635\\u0641\\u062e\\u0629 \\u0637\\u0628\\u064a\\u0629 \\u0644\\u062d\\u0627\\u0644\\u062a\\u0637\u0648\u0627\u0626 #{emergency.id}',
                        new_values=json.dumps({'prescription_id': result.id}),
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')

            flash('\\u062a\\u0645 \\u0627\\u0646\\u0634\\u0627\\u0621 \\u0627\\u0644\\u0648\\u0635\\u0641 \\u0628\\u0646\u062c\u0627\\u062d', 'success')
            return redirect(url_for('emergency.patient_queue'))'''

new = '''            try:
                db.session.add(
                    AuditTrail(
                        entity_type='visit' if visit else 'patient',
                        entity_id=visit.id if visit else emergency.patient_id,
                        action='create',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description=f'\\u0635\\u0641\\u062e\\u0629 \\u0637\\u0628\\u064a\\u0629 \\u0644\\u062d\\u0627\\u0644\\u062a\\u0637\\u0648\\u0627\\u0626\\u064a #{emergency.id}',
                        new_values=json.dumps({'prescription_id': result.id}),
                    )
                )
                if visit:
                    visit.prescription_issued = True
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')

            flash('\\u062a\\u0645 \\u0627\\u0646\\u0634\\u0627\\u0621 \\u0627\\u0644\\u0648\\u0635\\u0641 \\u0628\\u0646\\u062c\\u062d', 'success')
            return redirect(url_for('emergency.patient_queue'))'''

if t.count(old) == 1:
    t = t.replace(old, new)
    io.open(P, 'w', encoding='utf-8', newline='').write(t)
    print('patched')
else:
    print(f'not found, count={t.count(old)}')
    # Debug: find the region
    idx = t.find('safe_commit(db.session, error_message=\\'database commit failed\\'')
    if idx >= 0:
        print(t[idx:idx+500])

io.open(P, 'w', encoding='utf-8', newline='').write(t)
print('done')