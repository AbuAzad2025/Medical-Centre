"""
APM Query Profiler — PostgreSQL Performance Monitoring
=================================================
Real-time monitoring of query performance, index usage, and lock contention.

Usage:
    python -m scripts.apm_profiler --duration 300 --interval 5
    python -m scripts.apm_profiler --report idx_usage
    python -m scripts.apm_profiler --report lock_analysis
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2


class APMProfiler:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get(
            'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/medical_center'
        )
        self.output_dir = Path(__file__).parent.parent / 'reports' / 'apm'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        return psycopg2.connect(self.dsn)

    def get_slow_queries(self, limit: int = 50) -> list[dict[str, Any]]:
        query = """
            SELECT
                query,
                calls,
                total_exec_time / calls AS avg_ms,
                total_exec_time AS total_ms,
                rows,
                mean_exec_time AS avg_ms_v2,
                stddev_exec_time,
                min_exec_time,
                max_exec_time,
                shared_blks_hit,
                shared_blks_read,
                shared_blks_written,
                local_blks_hit,
                local_blks_read,
                local_blks dirtied,
                local_blks written,
                temp_blks_read,
                temp_blks_written,
                blk_read_time,
                blk_write_time
            FROM pg_stat_statements
            WHERE calls > 0
            ORDER BY total_exec_time DESC
            LIMIT %s;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query, (limit,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_index_usage(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan AS scans,
                idx_tup_read AS tuples_read,
                idx_tup_fetch AS tuples_fetched,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan > 0
            ORDER BY idx_scan DESC;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_unused_indexes(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
                idx_scan AS times_used
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
              AND indexname NOT LIKE '%_pkey'
              AND indexname NOT LIKE '%_seq_%'
            ORDER BY pg_relation_size(indexrelid) DESC;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_lock_contention(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                COALESCE(blocking_activity.pid, -1) AS blocking_pid,
                blocking_activity.query AS blocking_query,
                blocked_activity.pid AS blocked_pid,
                blocked_activity.query AS blocked_query,
                blocked_activity.mode AS lock_mode,
                blocked_activity.granted,
                blocked_activity.relation::regclass AS table_name
            FROM pg_stat_activity AS blocked_activity
            LEFT JOIN pg_stat_activity AS blocking_activity
                ON blocking_activity.pid = ANY(pg_blocking_pids(blocked_activity.pid))
            WHERE blocked_activity.pid != pg_backend_pid()
              AND (blocked_activity.state = 'active' OR blocked_activity.state = 'idle in transaction')
            ORDER BY blocked_activity.query_start;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_wait_events(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                state,
                wait_event_type,
                wait_event,
                COUNT(*) AS count,
                pg_blocking_pids(pid) AS blocked_by,
                left(query, 100) AS query_preview
            FROM pg_stat_activity
            WHERE state NOT IN ('idle')
              AND wait_event IS NOT NULL
              AND pid != pg_backend_pid()
            GROUP BY state, wait_event_type, wait_event, pg_blocking_pids(pid), left(query, 100)
            ORDER BY count DESC;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_connection_stats(self) -> dict[str, Any]:
        query = """
            SELECT
                numbackends AS total_connections,
                xact_commit AS commits,
                xact_rollback AS rollbacks,
                blks_read,
                blks_hit,
                blk_read_time,
                blk_write_time,
                maxxid AS max_transaction_age,
                aspirational_xid AS aspirational_age
            FROM pg_stat_database
            WHERE datname = current_database();
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row)) if row else {}

    def get_table_bloat_analysis(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) -
                               pg_relation_size(schemaname||'.'||tablename)) AS bloat_size,
                n_live_tup AS live_rows,
                n_dead_tup AS dead_rows,
                CASE WHEN n_live_tup + n_dead_tup > 0
                     THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                     ELSE 0 END AS dead_tuple_pct
            FROM pg_stat_user_tables
            WHERE n_live_tup + n_dead_tup > 100
            ORDER BY n_dead_tup DESC
            LIMIT 20;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_index_hit_ratio(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                relname AS table_name,
                CASE WHEN idx_blks_hit + idx_blks_read = 0 THEN 0
                     ELSE round(100.0 * idx_blks_hit / (idx_blks_hit + idx_blks_read), 2)
                END AS index_hit_ratio_pct,
                idx_blks_hit AS index_hits,
                idx_blks_read AS index_misses,
                idx_blks_hit + idx_blks_read AS total_index_access
            FROM pg_statio_user_tables
            WHERE idx_blks_hit + idx_blks_read > 0
            ORDER BY idx_blks_hit + idx_blks_read DESC
            LIMIT 20;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def realtime_monitor(self, duration_seconds: int = 60, interval_seconds: int = 5):
        samples = []
        start = datetime.now(UTC)
        end_time = start.timestamp() + duration_seconds

        print(
            f'[APM] Starting real-time monitoring for {duration_seconds}s (interval={interval_seconds}s)'
        )
        print(f'[APM] Output directory: {self.output_dir}')
        print('-' * 80)

        sample_num = 0
        while datetime.now(UTC).timestamp() < end_time:
            sample_num += 1
            ts = datetime.now(UTC).isoformat()

            conn_stats = self.get_connection_stats()
            slow = self.get_slow_queries(10)
            locks = self.get_lock_contention()
            waits = self.get_wait_events()

            sample = {
                'timestamp': ts,
                'sample': sample_num,
                'connections': conn_stats,
                'slow_queries_count': len(slow),
                'lock_contention_count': len(locks),
                'wait_events_count': len(waits),
                'top_slow_query': slow[0]['query'][:200] if slow else None,
                'top_slow_avg_ms': round(slow[0]['avg_ms'], 2) if slow else None,
            }
            samples.append(sample)

            print(
                f'[{ts}] '
                f'Slow: {sample["slow_queries_count"]} | '
                f'Locks: {sample["lock_contention_count"]} | '
                f'Waits: {sample["wait_events_count"]} | '
                f'Top: {sample["top_slow_avg_ms"]}ms'
            )

            import time

            time.sleep(interval_seconds)

        report_path = self.output_dir / f'realtime_{start.strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'start': start.isoformat(),
                    'end': datetime.now(UTC).isoformat(),
                    'duration_s': duration_seconds,
                    'samples': samples,
                },
                f,
                indent=2,
                default=str,
            )

        print(f'[APM] Real-time report saved: {report_path}')
        return samples

    def report_slow_queries(self, output_format: str = 'table'):
        data = self.get_slow_queries(50)

        if output_format == 'json':
            path = (
                self.output_dir / f'slow_queries_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            print(f'[APM] Slow queries report: {path}')
            return data

        print('\n' + '=' * 100)
        print('TOP 50 SLOW QUERIES BY TOTAL TIME')
        print('=' * 100)
        print(f'{"Avg(ms)":>10} {"Calls":>8} {"Total(s)":>10} {"Rows":>8} {"Query":<60}')
        print('-' * 100)

        for row in data:
            avg = round(row.get('avg_ms') or row.get('avg_ms_v2') or 0, 2)
            calls = row.get('calls', 0)
            total = round((row.get('total_ms') or 0) / 1000, 2)
            rows = row.get('rows', 0)
            q = (row.get('query') or '')[:60]
            print(f'{avg:>10.2f} {calls:>8} {total:>10.2f} {rows:>8} {q}')

        print()
        return data

    def report_index_usage(self, output_format: str = 'table'):
        data = self.get_index_usage()

        if output_format == 'json':
            path = (
                self.output_dir / f'index_usage_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            print(f'[APM] Index usage report: {path}')
            return data

        print('\n' + '=' * 100)
        print('INDEX USAGE (scans > 0)')
        print('=' * 100)
        print(f'{"Scans":>12} {"Table":<30} {"Index":<35} {"Size":>10}')
        print('-' * 100)

        for row in data:
            scans = row.get('scans', 0)
            table = row.get('tablename', '')
            idx = row.get('indexname', '')
            size = row.get('index_size', '')
            print(f'{scans:>12,} {table:<30} {idx:<35} {size:>10}')

        print()
        return data

    def report_lock_analysis(self, output_format: str = 'table'):
        data = self.get_lock_contention()

        if output_format == 'json':
            path = (
                self.output_dir
                / f'lock_contention_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            print(f'[APM] Lock contention report: {path}')
            return data

        print('\n' + '=' * 100)
        print('LOCK CONTENTION ANALYSIS')
        print('=' * 100)

        if not data:
            print('No lock contention detected.')
        else:
            print(f'{"Blocking PID":>12} {"Blocked PID":>12} {"Lock Mode":<20} {"Table":<30}')
            print('-' * 100)

            for row in data:
                bp = row.get('blocking_pid', 'N/A')
                bb = row.get('blocked_pid', 'N/A')
                mode = row.get('lock_mode', '')
                tbl = row.get('table_name', '')
                print(f'{bp:>12} {bb:>12} {mode:<20} {tbl:<30}')

                if row.get('blocking_query'):
                    print(f'  BLOCKER: {row["blocking_query"][:80]}')
                if row.get('blocked_query'):
                    print(f'  BLOCKED: {row["blocked_query"][:80]}')
                print()

        return data

    def report_unused_indexes(self, output_format: str = 'table'):
        data = self.get_unused_indexes()

        if output_format == 'json':
            path = (
                self.output_dir
                / f'unused_indexes_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            print(f'[APM] Unused indexes report: {path}')
            return data

        print('\n' + '=' * 100)
        print('UNUSED INDEXES (potential bloat)')
        print('=' * 100)
        print(f'{"Schema":<15} {"Table":<25} {"Index":<40} {"Size":>10} {"Scans":>8}')
        print('-' * 100)

        for row in data:
            schema = row.get('schemaname', '')
            table = row.get('tablename', '')
            idx = row.get('indexname', '')
            size = row.get('index_size', '')
            scans = row.get('times_used', 0)
            print(f'{schema:<15} {table:<25} {idx:<40} {size:>10} {scans:>8}')

        print()
        return data

    def report_full(self):
        print('\n' + '=' * 80)
        print('APM FULL REPORT')
        print(f'Generated: {datetime.now(UTC).isoformat()}')
        print('=' * 80)

        self.report_slow_queries()
        self.report_index_usage()
        self.report_lock_analysis()
        self.report_unused_indexes()

        conn = self.get_connection_stats()
        print('\n' + '=' * 80)
        print('DATABASE CONNECTION STATS')
        print('=' * 80)
        for k, v in conn.items():
            print(f'  {k}: {v}')

        bloat = self.get_table_bloat_analysis()
        print('\n' + '=' * 80)
        print('TABLE BLOAT ANALYSIS (top 20)')
        print('=' * 80)
        print(f'{"Table":<40} {"Total":>10} {"Dead Rows":>10} {"Dead%":>8}')
        print('-' * 80)
        for row in bloat[:20]:
            tbl = f'{row.get("schemaname", "")}.{row.get("tablename", "")}'
            total = row.get('total_size', '')
            dead = row.get('dead_rows', 0)
            pct = row.get('dead_tuple_pct', 0)
            print(f'{tbl:<40} {total:>10} {dead:>10} {pct:>7.2f}%')


def main():
    parser = argparse.ArgumentParser(description='APM Query Profiler for PostgreSQL')
    parser.add_argument(
        '--duration', type=int, default=0, help='Real-time monitoring duration in seconds'
    )
    parser.add_argument('--interval', type=int, default=5, help='Sampling interval in seconds')
    parser.add_argument(
        '--report',
        choices=['slow', 'idx_usage', 'locks', 'unused', 'full'],
        default='full',
        help='Report type to generate',
    )
    parser.add_argument(
        '--format', choices=['table', 'json'], default='table', help='Output format'
    )
    parser.add_argument('--dsn', type=str, default=None, help='PostgreSQL connection string')

    args = parser.parse_args()

    profiler = APMProfiler(dsn=args.dsn)

    if args.duration > 0:
        profiler.realtime_monitor(duration_seconds=args.duration, interval_seconds=args.interval)
    elif args.report == 'slow':
        profiler.report_slow_queries(output_format=args.format)
    elif args.report == 'idx_usage':
        profiler.report_index_usage(output_format=args.format)
    elif args.report == 'locks':
        profiler.report_lock_analysis(output_format=args.format)
    elif args.report == 'unused':
        profiler.report_unused_indexes(output_format=args.format)
    elif args.report == 'full':
        profiler.report_full()


if __name__ == '__main__':
    main()
