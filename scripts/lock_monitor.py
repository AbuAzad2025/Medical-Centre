"""
Real-Time Lock Monitoring Dashboard
===================================
Live monitoring of PostgreSQL locks, wait events, and query execution.

Usage:
    python -m scripts.lock_monitor --duration 60 --interval 2
    python -m scripts.lock_monitor --report --output dashboard.html
"""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2


class LockMonitor:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get(
            'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/medical_center'
        )
        self.output_dir = Path(__file__).parent.parent / 'reports' / 'lock_monitor'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        return psycopg2.connect(self.dsn)

    def get_active_locks(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                la.pid,
                la.mode AS lock_mode,
                la.granted,
                la.relation::regclass AS table_name,
                la.page AS page_num,
                la.tuple AS tuple_num,
                la.virtualxid AS vxid,
                la.transactionid AS xid,
                la.classid,
                la.objid,
                la.objsubid,
                COALESCE(a.query, '<idle>') AS query_preview,
                a.state,
                a.usename AS username,
                a.datname AS database_name,
                a.client_addr,
                a.application_name,
                a.backend_start,
                a.xact_start,
                a.query_start,
                a.state_change
            FROM pg_locks la
            JOIN pg_stat_activity a ON la.pid = a.pid
            WHERE la.pid != pg_backend_pid()
              AND a.datname = current_database()
            ORDER BY la.granted ASC, a.query_start DESC;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_lock_matrix(self) -> dict[str, Any]:
        locks = self.get_active_locks()

        granted = [lk for lk in locks if lk.get('granted')]
        waiting = [lk for lk in locks if not lk.get('granted')]

        by_table: dict[str, dict[str, int]] = {}
        for lock in locks:
            tbl = str(lock.get('table_name', 'unknown'))
            if tbl not in by_table:
                by_table[tbl] = {'granted': 0, 'waiting': 0}
            key = 'granted' if lock.get('granted') else 'waiting'
            by_table[tbl][key] += 1

        by_mode: dict[str, int] = {}
        for lock in locks:
            mode = str(lock.get('lock_mode', 'unknown'))
            by_mode[mode] = by_mode.get(mode, 0) + 1

        return {
            'total': len(locks),
            'granted': len(granted),
            'waiting': len(waiting),
            'by_table': by_table,
            'by_mode': by_mode,
            'waiting_queries': [
                {
                    'pid': lk['pid'],
                    'query': lk.get('query_preview', ''),
                    'table': str(lk.get('table_name', '')),
                    'mode': lk.get('lock_mode', ''),
                    'wait_time': self._seconds_since(lk.get('query_start')),
                }
                for lk in waiting
            ],
            'recent_granted': [
                {
                    'pid': gr['pid'],
                    'query': gr.get('query_preview', ''),
                    'table': str(gr.get('table_name', '')),
                    'mode': gr.get('lock_mode', ''),
                }
                for gr in granted[-10:]
            ],
        }

    def _seconds_since(self, dt) -> float:
        if dt is None:
            return 0
        try:
            return (datetime.now(UTC) - dt.replace(tzinfo=UTC)).total_seconds()
        except Exception:
            return 0

    def get_transaction_health(self) -> dict[str, Any]:
        query = """
            SELECT
                pid,
                state,
                usename,
                query,
                state_change,
                xact_start,
                query_start,
                backend_start,
                application_name,
                COUNT(*) OVER() AS same_state_count
            FROM pg_stat_activity
            WHERE state IN ('active', 'idle in transaction', 'idle in transaction (aborted)')
              AND pid != pg_backend_pid()
            ORDER BY xact_start NULLS LAST, query_start DESC;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            data = [dict(zip(cols, row)) for row in rows]

        idle_in_tx = [d for d in data if 'idle in transaction' in str(d.get('state', ''))]
        long_running = [
            d for d in data if d.get('xact_start') and self._seconds_since(d['xact_start']) > 5
        ]

        return {
            'total_active': len(data),
            'idle_in_transaction': len(idle_in_tx),
            'long_running_transactions': len(long_running),
            'idle_in_transaction_pids': [d['pid'] for d in idle_in_tx],
            'long_running_pids': [d['pid'] for d in long_running],
            'details': data[:20],
        }

    def print_dashboard(self, duration: int = 60, interval: int = 2):
        print(f'\n{"=" * 100}')
        print(f'REAL-TIME LOCK MONITOR — Duration: {duration}s, Interval: {interval}s')
        print(f'{"=" * 100}')
        print('Press Ctrl+C to stop\n')

        start_time = time.time()
        samples = []

        try:
            while time.time() - start_time < duration:
                ts = datetime.now(UTC).strftime('%H:%M:%S')

                locks = self.get_lock_matrix()
                health = self.get_transaction_health()

                sample = {'timestamp': ts, 'locks': locks, 'health': health}
                samples.append(sample)

                granted = locks.get('granted', 0)
                waiting = locks.get('waiting', 0)
                idle = health.get('idle_in_transaction', 0)
                long_tx = health.get('long_running_transactions', 0)

                wait_pct = (
                    (waiting / max(1, granted + waiting)) * 100 if (granted + waiting) > 0 else 0
                )

                bar_len = 40
                fill = (
                    int(bar_len * granted / max(1, granted + waiting))
                    if (granted + waiting) > 0
                    else 0
                )
                bar = '█' * fill + '░' * (bar_len - fill)

                print(
                    f'\r[{ts}] Lock Matrix: {bar} | Granted={granted} Waiting={waiting} ({wait_pct:.1f}%) '
                    f'| IdleTX={idle} LongTX={long_tx}',
                    end='',
                    flush=True,
                )

                if waiting > 0:
                    print('\n  ⚠ Waiting queries:')
                    for wq in locks.get('waiting_queries', [])[:3]:
                        print(f'    PID={wq["pid"]} {wq["query"][:60]}')

                time.sleep(interval)

        except KeyboardInterrupt:
            print('\n\n[Stopped]')

        print(f'\n\n{"=" * 100}')
        print('LOCK SUMMARY')
        print(f'{"=" * 100}')

        all_locks = self.get_active_locks()
        if all_locks:
            print(f'\nTotal active locks: {len(all_locks)}')
            print('\nBy table:')
            for tbl, counts in locks.get('by_table', {}).items():
                print(f'  {tbl}: Granted={counts["granted"]}, Waiting={counts["waiting"]}')

            print('\nBy lock mode:')
            for mode, count in locks.get('by_mode', {}).items():
                print(f'  {mode}: {count}')
        else:
            print('No active locks detected.')

        health = self.get_transaction_health()
        if health['idle_in_transaction'] > 0:
            print(f'\n⚠ {health["idle_in_transaction"]} idle-in-transaction sessions:')
            for d in health['details'][:5]:
                if 'idle in transaction' in str(d.get('state', '')):
                    secs = self._seconds_since(d.get('xact_start'))
                    print(
                        f'  PID={d["pid"]} Duration={secs:.1f}s Query={str(d.get("query", ""))[:50]}'
                    )

        report_path = (
            self.output_dir / f'lock_monitor_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'duration_s': duration,
                    'interval_s': interval,
                    'samples': samples,
                    'final_locks': self.get_lock_matrix(),
                    'final_health': self.get_transaction_health(),
                },
                f,
                indent=2,
                default=str,
            )

        print(f'\n[Report] Saved to: {report_path}')

    def generate_html_dashboard(self, output_path: Path | None = None):

        locks = self.get_lock_matrix()
        health = self.get_transaction_health()

        if output_path is None:
            output_path = (
                self.output_dir / f'dashboard_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.html'
            )

        html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lock Monitor Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #0f1117; color: #e0e0e0; padding: 1rem; }}
        h1 {{ color: #00d4ff; margin-bottom: 1rem; font-size: 1.5rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1rem; }}
        .card {{ background: #1a1d27; border-radius: 8px; padding: 1rem; border: 1px solid #2d2f3a; }}
        .card h2 {{ color: #00d4ff; font-size: 1rem; margin-bottom: 0.75rem; border-bottom: 1px solid #2d2f3a; padding-bottom: 0.5rem; }}
        .metric {{ display: flex; justify-content: space-between; padding: 0.25rem 0; }}
        .metric .value {{ font-weight: bold; color: #00ff88; }}
        .metric.warning .value {{ color: #ffaa00; }}
        .metric.danger .value {{ color: #ff4444; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{ text-align: right; color: #888; padding: 0.25rem; border-bottom: 1px solid #2d2f3a; }}
        td {{ padding: 0.25rem; border-bottom: 1px solid #222; }}
        .badge {{ display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.75rem; }}
        .badge-granted {{ background: #00ff8822; color: #00ff88; }}
        .badge-waiting {{ background: #ffaa0022; color: #ffaa00; }}
        .badge-idle {{ background: #ff444422; color: #ff4444; }}
        pre {{ font-size: 0.75rem; color: #888; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>🔒 Lock Monitor Dashboard — {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}</h1>

    <div class="grid">
        <div class="card">
            <h2>📊 Lock Summary</h2>
            <div class="metric {'danger' if locks['waiting'] > 0 else ''}">
                <span>Waiting Locks</span>
                <span class="value">{locks['waiting']}</span>
            </div>
            <div class="metric">
                <span>Granted Locks</span>
                <span class="value">{locks['granted']}</span>
            </div>
            <div class="metric">
                <span>Total Locks</span>
                <span class="value">{locks['total']}</span>
            </div>
        </div>

        <div class="card">
            <h2>💾 Transaction Health</h2>
            <div class="metric {'warning' if health['idle_in_transaction'] > 0 else ''}">
                <span>Idle in Transaction</span>
                <span class="value">{health['idle_in_transaction']}</span>
            </div>
            <div class="metric {'danger' if health['long_running_transactions'] > 0 else ''}">
                <span>Long Running (>5s)</span>
                <span class="value">{health['long_running_transactions']}</span>
            </div>
            <div class="metric">
                <span>Total Active</span>
                <span class="value">{health['total_active']}</span>
            </div>
        </div>

        <div class="card">
            <h2>📋 Lock Modes</h2>
            {
            ''.join(
                f'<div class="metric"><span>{mode}</span><span class="value">{count}</span></div>'
                for mode, count in locks.get('by_mode', {}).items()
            )
        }
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>⏳ Waiting Queries</h2>
            {
            '<table><tr><th>PID</th><th>Table</th><th>Mode</th><th>Wait Time</th><th>Query</th></tr>'
            + ''.join(
                f'<tr><td>{wq["pid"]}</td><td>{wq["table"]}</td><td>{wq["mode"]}</td>'
                f'<td>{wq["wait_time"]:.1f}s</td><td><pre>{wq["query"][:80]}</pre></td></tr>'
                for wq in locks.get('waiting_queries', [])
            )
            + '</table>'
            if locks.get('waiting_queries')
            else '<p>No waiting queries</p>'
        }
        </div>

        <div class="card">
            <h2>🔄 Recently Granted</h2>
            {
            '<table><tr><th>PID</th><th>Table</th><th>Mode</th><th>Query</th></tr>'
            + ''.join(
                f'<tr><td>{rq["pid"]}</td><td>{rq["table"]}</td><td>{rq["mode"]}</td>'
                f'<td><pre>{rq["query"][:80]}</pre></td></tr>'
                for rq in locks.get('recent_granted', [])
            )
            + '</table>'
            if locks.get('recent_granted')
            else '<p>No granted locks</p>'
        }
        </div>
    </div>

    <div class="card">
        <h2>📈 Tables with Locks</h2>
        <table>
            <tr><th>Table</th><th>Granted</th><th>Waiting</th></tr>
            {
            ''.join(
                f"<tr><td>{tbl}</td><td><span class='badge badge-granted'>{c['granted']}</span></td>"
                f"<td><span class='badge badge-waiting'>{c['waiting']}</span></td></tr>"
                for tbl, c in locks.get('by_table', {}).items()
            )
        }
        </table>
    </div>
</body>
</html>"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f'[Dashboard] Generated: {output_path}')
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Real-Time Lock Monitor')
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Monitoring duration in seconds (0 = single snapshot)',
    )
    parser.add_argument('--interval', type=int, default=2, help='Sampling interval in seconds')
    parser.add_argument('--report', action='store_true', help='Generate HTML dashboard')
    parser.add_argument('--dsn', type=str, default=None, help='PostgreSQL connection string')

    args = parser.parse_args()

    monitor = LockMonitor(dsn=args.dsn)

    if args.report:
        monitor.generate_html_dashboard()
    elif args.duration > 0:
        monitor.print_dashboard(duration=args.duration, interval=args.interval)
    else:
        locks = monitor.get_lock_matrix()
        health = monitor.get_transaction_health()
        print(
            f'Locks: {locks["total"]} total, {locks["granted"]} granted, {locks["waiting"]} waiting'
        )
        print(
            f'Health: {health["total_active"]} active, {health["idle_in_transaction"]} idle in transaction'
        )


if __name__ == '__main__':
    main()
