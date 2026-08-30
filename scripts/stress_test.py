"""
Stress & Concurrency Testing for Payment & Inventory Operations
============================================================
Simulates concurrent payment processing and inventory modifications
to verify row-level locking behavior under load.

Usage:
    python -m scripts.stress_test --test payments --concurrency 10 --iterations 100
    python -m scripts.stress_test --test inventory --concurrency 5 --iterations 50
    python -m scripts.stress_test --test all --concurrency 20 --iterations 200
"""

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from psycopg2 import errors
from psycopg2.pool import ThreadedConnectionPool


@dataclass
class TestResult:
    test_name: str
    thread_id: int
    iteration: int
    success: bool
    duration_ms: float
    error_message: str | None = None
    row_version: int | None = None
    lock_acquired: bool = False
    wait_time_ms: float = 0


@dataclass
class TestSummary:
    test_name: str
    total_requests: int
    successful: int
    failed: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    lock_waits: int
    deadlocks: int
    timeout_errors: int
    unique_errors: dict[str, int] = field(default_factory=dict)
    results: list[TestResult] = field(default_factory=list)


class ConcurrencyTester:
    def __init__(self, dsn: str | None = None, max_connections: int = 30):
        self.dsn = dsn or os.environ.get(
            'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/medical_center'
        )
        self.pool = ThreadedConnectionPool(minconn=2, maxconn=max_connections, dsn=self.dsn)
        self.output_dir = Path(__file__).parent.parent / 'reports' / 'stress_tests'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._results: list[TestResult] = []
        self._lock = threading.Lock()
        self._tenant_id = 1
        self._visit_id = None
        self._medication_id = None

    def get_connection(self):
        return self.pool.getconn()

    def return_connection(self, conn):
        self.pool.putconn(conn)

    def setup_test_data(self):
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            cur.execute(
                "SELECT id FROM visits WHERE payment_status IN ('PENDING', 'PARTIAL', 'DEBT') LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                self._visit_id = row[0]
            else:
                cur.execute('SELECT id FROM visits LIMIT 1')
                row = cur.fetchone()
                self._visit_id = row[0] if row else 1

            cur.execute('SELECT id FROM medications WHERE is_active = true LIMIT 1')
            row = cur.fetchone()
            if row:
                self._medication_id = row[0]
            else:
                self._medication_id = 1

            conn.commit()
            print(f'[Setup] Test visit_id={self._visit_id}, medication_id={self._medication_id}')
        except Exception as e:
            conn.rollback()
            print(f'[Setup] Error: {e}')
            self._visit_id = 1
            self._medication_id = 1
        finally:
            self.return_connection(conn)

    def record_result(self, result: TestResult):
        with self._lock:
            self._results.append(result)

    def test_concurrent_payment_allocation(
        self, thread_id: int, iterations: int, payment_amount: float = 100.0
    ) -> list[TestResult]:
        results = []

        for i in range(iterations):
            start = time.perf_counter()
            wait_time = 0
            success = False
            error_msg = None
            lock_acquired = False
            row_version = None

            conn = self.get_connection()
            try:
                conn.autocommit = False
                cur = conn.cursor()

                cur.execute('BEGIN')

                cur.execute(
                    """
                    SELECT id, paid_amount, total_amount
                    FROM invoices
                    WHERE visit_id = %s
                    AND status != 'PAID'
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE
                """,
                    (self._visit_id,),
                )
                invoice = cur.fetchone()

                if invoice:
                    invoice_id, current_paid, total_amount = invoice
                    new_paid = float(current_paid or 0) + payment_amount
                    status = 'PAID' if new_paid >= float(total_amount) else 'PARTIAL'

                    time.sleep(0.01)

                    cur.execute(
                        """
                        UPDATE invoices
                        SET paid_amount = %s, status = %s, updated_at = NOW()
                        WHERE id = %s
                        RETURNING xmax
                    """,
                        (new_paid, status, invoice_id),
                    )

                    row_version = cur.fetchone()[0]
                    lock_acquired = True

                cur.execute('COMMIT')
                success = True

            except errors.LockNotAvailable as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'LockNotAvailable: {e}'
                lock_acquired = False
            except errors.DeadlockDetected as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'Deadlock: {e}'
            except errors.QueryTimeout as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'Timeout: {e}'
            except Exception as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = str(e)
            finally:
                self.return_connection(conn)

            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                test_name='payment_allocation',
                thread_id=thread_id,
                iteration=i,
                success=success,
                duration_ms=round(duration, 2),
                error_message=error_msg,
                row_version=row_version,
                lock_acquired=lock_acquired,
                wait_time_ms=round(wait_time, 2),
            )
            results.append(result)
            self.record_result(result)

        return results

    def test_concurrent_inventory_adjustment(
        self, thread_id: int, iterations: int, quantity_change: int = -1
    ) -> list[TestResult]:
        results = []

        for i in range(iterations):
            start = time.perf_counter()
            wait_time = 0
            success = False
            error_msg = None
            lock_acquired = False
            row_version = None

            conn = self.get_connection()
            try:
                conn.autocommit = False
                cur = conn.cursor()

                cur.execute('BEGIN')

                cur.execute(
                    """
                    SELECT id, stock_quantity
                    FROM medications
                    WHERE id = %s
                    FOR UPDATE
                """,
                    (self._medication_id,),
                )
                med = cur.fetchone()

                if med:
                    med_id, current_stock = med

                    time.sleep(0.005)

                    new_stock = max(0, (current_stock or 0) + quantity_change)
                    cur.execute(
                        """
                        UPDATE medications
                        SET stock_quantity = %s, updated_at = NOW()
                        WHERE id = %s
                        RETURNING xmax
                    """,
                        (new_stock, med_id),
                    )

                    row_version = cur.fetchone()[0]
                    lock_acquired = True

                cur.execute('COMMIT')
                success = True

            except errors.LockNotAvailable as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'LockNotAvailable: {e}'
            except errors.DeadlockDetected as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'Deadlock: {e}'
            except errors.QueryTimeout as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = f'Timeout: {e}'
            except Exception as e:
                conn.rollback()
                wait_time = (time.perf_counter() - start) * 1000
                error_msg = str(e)
            finally:
                self.return_connection(conn)

            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                test_name='inventory_adjustment',
                thread_id=thread_id,
                iteration=i,
                success=success,
                duration_ms=round(duration, 2),
                error_message=error_msg,
                row_version=row_version,
                lock_acquired=lock_acquired,
                wait_time_ms=round(wait_time, 2),
            )
            results.append(result)
            self.record_result(result)

        return results

    def test_double_spend_attack(
        self, thread_id: int, iterations: int, payment_amount: float = 5000.0
    ) -> list[TestResult]:
        results = []
        idempotency_keys = set()

        for i in range(iterations):
            start = time.perf_counter()
            success = False
            error_msg = None
            double_spend_detected = False

            conn = self.get_connection()
            try:
                idempotency_key = f'double_spend_{self._visit_id}_{i}'
                idempotency_keys.add(idempotency_key)

                conn.autocommit = False
                cur = conn.cursor()

                cur.execute(
                    """
                    SELECT id, total_amount, paid_amount
                    FROM invoices
                    WHERE visit_id = %s
                    AND status != 'PAID'
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE
                """,
                    (self._visit_id,),
                )
                invoice = cur.fetchone()

                if invoice:
                    invoice_id, total_amount, current_paid = invoice
                    remaining = float(total_amount) - float(current_paid or 0)

                    if remaining >= payment_amount:
                        new_paid = float(current_paid or 0) + payment_amount

                        time.sleep(0.02)

                        cur.execute(
                            """
                            UPDATE invoices
                            SET paid_amount = %s, status = 'PARTIAL', updated_at = NOW()
                            WHERE id = %s
                            AND paid_amount = %s
                            RETURNING id
                        """,
                            (new_paid, invoice_id, current_paid),
                        )

                        updated = cur.fetchone()
                        if updated is None:
                            double_spend_detected = True
                            error_msg = 'Double-spend BLOCKED by row version'
                        else:
                            success = True

                cur.execute('COMMIT')

            except errors.LockNotAvailable as e:
                conn.rollback()
                error_msg = f'LockNotAvailable: {e}'
            except Exception as e:
                conn.rollback()
                error_msg = str(e)
            finally:
                self.return_connection(conn)

            duration = (time.perf_counter() - start) * 1000
            result = TestResult(
                test_name='double_spend_attack',
                thread_id=thread_id,
                iteration=i,
                success=success,
                duration_ms=round(duration, 2),
                error_message=error_msg,
                row_version=1 if double_spend_detected else 0,
            )
            results.append(result)
            self.record_result(result)

        return results

    def summarize(self, test_name: str) -> TestSummary:
        results = [r for r in self._results if r.test_name == test_name]
        if not results:
            return TestSummary(
                test_name=test_name,
                total_requests=0,
                successful=0,
                failed=0,
                avg_duration_ms=0,
                min_duration_ms=0,
                max_duration_ms=0,
                p95_duration_ms=0,
                p99_duration_ms=0,
                lock_waits=0,
                deadlocks=0,
                timeout_errors=0,
            )

        durations = sorted([r.duration_ms for r in results])
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]

        error_counts: dict[str, int] = {}
        for r in failures:
            err = r.error_message or 'Unknown'
            error_counts[err] = error_counts.get(err, 0) + 1

        deadlocks = sum(1 for r in failures if r.error_message and 'Deadlock' in r.error_message)
        timeouts = sum(1 for r in failures if r.error_message and 'Timeout' in r.error_message)
        lock_waits = sum(1 for r in results if r.wait_time_ms > 0)

        def percentile(data, p):
            idx = int(len(data) * p / 100)
            return data[min(idx, len(data) - 1)]

        return TestSummary(
            test_name=test_name,
            total_requests=len(results),
            successful=len(successes),
            failed=len(failures),
            avg_duration_ms=round(sum(durations) / len(durations), 2),
            min_duration_ms=round(min(durations), 2),
            max_duration_ms=round(max(durations), 2),
            p95_duration_ms=round(percentile(durations, 95), 2),
            p99_duration_ms=round(percentile(durations, 99), 2),
            lock_waits=lock_waits,
            deadlocks=deadlocks,
            timeout_errors=timeouts,
            unique_errors=error_counts,
            results=results,
        )

    def run_stress_test(self, test_name: str, concurrency: int, iterations_per_thread: int):
        print(f'\n{"=" * 80}')
        print(f'STRESS TEST: {test_name}')
        print(f'Concurrency: {concurrency} threads x {iterations_per_thread} iterations')
        print(f'{"=" * 80}')

        self.setup_test_data()
        start_time = time.perf_counter()

        if test_name == 'payments':
            test_func = self.test_concurrent_payment_allocation
        elif test_name == 'inventory':
            test_func = self.test_concurrent_inventory_adjustment
        elif test_name == 'double_spend':
            test_func = self.test_double_spend_attack
        else:
            raise ValueError(f'Unknown test: {test_name}')

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for thread_id in range(concurrency):
                future = executor.submit(
                    test_func, thread_id=thread_id, iterations=iterations_per_thread
                )
                futures.append(future)

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f'[Error] Thread failed: {e}')

        total_time = time.perf_counter() - start_time
        summary = self.summarize(test_name)

        print(f'\n[Results] Completed in {total_time:.2f}s')
        print(f'  Total requests:    {summary.total_requests}')
        print(
            f'  Successful:         {summary.successful} ({100 * summary.successful / max(1, summary.total_requests):.1f}%)'
        )
        print(f'  Failed:             {summary.failed}')
        print(f'  Deadlocks:          {summary.deadlocks}')
        print(f'  Timeouts:           {summary.timeout_errors}')
        print(f'  Lock waits:         {summary.lock_waits}')
        print(f'  Avg duration:       {summary.avg_duration_ms:.2f}ms')
        print(f'  P95 duration:       {summary.p95_duration_ms:.2f}ms')
        print(f'  P99 duration:       {summary.p99_duration_ms:.2f}ms')
        print(f'  Max duration:       {summary.max_duration_ms:.2f}ms')

        if summary.unique_errors:
            print('\n[Error Distribution]')
            for err, count in summary.unique_errors.items():
                print(f'  {err}: {count}')

        report_path = (
            self.output_dir / f'{test_name}_{datetime.now(UTC).strftime("%Y%m%d_%H%M%S")}.json'
        )
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'test_name': test_name,
                    'concurrency': concurrency,
                    'iterations_per_thread': iterations_per_thread,
                    'total_time_s': round(total_time, 2),
                    'summary': {
                        'total_requests': summary.total_requests,
                        'successful': summary.successful,
                        'failed': summary.failed,
                        'avg_duration_ms': summary.avg_duration_ms,
                        'min_duration_ms': summary.min_duration_ms,
                        'max_duration_ms': summary.max_duration_ms,
                        'p95_duration_ms': summary.p95_duration_ms,
                        'p99_duration_ms': summary.p99_duration_ms,
                        'lock_waits': summary.lock_waits,
                        'deadlocks': summary.deadlocks,
                        'timeout_errors': summary.timeout_errors,
                        'unique_errors': summary.unique_errors,
                    },
                    'results': [
                        {
                            'thread_id': r.thread_id,
                            'iteration': r.iteration,
                            'success': r.success,
                            'duration_ms': r.duration_ms,
                            'error_message': r.error_message,
                            'lock_acquired': r.lock_acquired,
                            'wait_time_ms': r.wait_time_ms,
                        }
                        for r in summary.results
                    ],
                },
                f,
                indent=2,
                default=str,
            )

        print(f'\n[Report] Saved to: {report_path}')
        return summary

    def close(self):
        self.pool.closeall()


def main():
    parser = argparse.ArgumentParser(description='Stress & Concurrency Tester')
    parser.add_argument(
        '--test',
        choices=['payments', 'inventory', 'double_spend', 'all'],
        default='all',
        help='Test to run',
    )
    parser.add_argument('--concurrency', type=int, default=10, help='Number of concurrent threads')
    parser.add_argument('--iterations', type=int, default=50, help='Iterations per thread')
    parser.add_argument('--dsn', type=str, default=None, help='PostgreSQL connection string')

    args = parser.parse_args()

    tester = ConcurrencyTester(dsn=args.dsn)

    try:
        if args.test == 'all':
            tester.run_stress_test('payments', args.concurrency, args.iterations)
            tester.run_stress_test('inventory', args.concurrency, args.iterations)
            tester.run_stress_test('double_spend', args.concurrency, args.iterations)
        else:
            tester.run_stress_test(args.test, args.concurrency, args.iterations)
    finally:
        tester.close()


if __name__ == '__main__':
    main()
