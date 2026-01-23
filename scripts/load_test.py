import argparse
import concurrent.futures
import re
import time
import urllib.parse
import urllib.request
import http.cookiejar


def _build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get_csrf_token(html: str) -> str:
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else ''


def _login(opener, base_url: str, username: str, password: str) -> bool:
    login_url = urllib.parse.urljoin(base_url, '/auth/login')
    with opener.open(login_url, timeout=20) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    token = _get_csrf_token(html)
    data = urllib.parse.urlencode({
        'username': username,
        'password': password,
        'csrf_token': token
    }).encode('utf-8')
    req = urllib.request.Request(login_url, data=data, method='POST')
    with opener.open(req, timeout=20) as resp:
        return resp.status in (200, 302)


def _fetch(opener, url: str):
    start = time.time()
    status = 0
    try:
        with opener.open(url, timeout=20) as resp:
            resp.read()
            status = resp.status
    except Exception:
        status = 0
    return time.time() - start, status


def run(base_url: str, endpoints: list[str], concurrency: int, total: int, username: str | None, password: str | None):
    opener = _build_opener()
    if username and password:
        ok = _login(opener, base_url, username, password)
        if not ok:
            print('login_failed')
            return
    urls = [urllib.parse.urljoin(base_url, e) for e in endpoints]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = []
        for i in range(total):
            url = urls[i % len(urls)]
            futures.append(ex.submit(_fetch, opener, url))
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    latencies = [r[0] for r in results]
    statuses = [r[1] for r in results]
    ok_count = sum(1 for s in statuses if s and 200 <= s < 400)
    avg = sum(latencies) / len(latencies) if latencies else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0
    print(f"requests={len(results)} ok={ok_count} avg={avg:.3f}s p95={p95:.3f}s")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--endpoints', nargs='+', required=True)
    parser.add_argument('--concurrency', type=int, default=10)
    parser.add_argument('--total', type=int, default=200)
    parser.add_argument('--username')
    parser.add_argument('--password')
    args = parser.parse_args()
    run(args.base_url, args.endpoints, args.concurrency, args.total, args.username, args.password)
