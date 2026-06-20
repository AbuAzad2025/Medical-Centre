"""
Webhook dispatch service — fires HTTP POST to registered webhooks on platform events.

Features:
- Retry queue with exponential backoff
- Dead letter queue for failed webhooks
- Background processing for non-blocking dispatch
- HMAC-SHA256 signature verification
"""
import hashlib
import hmac
import json
import logging
import time
import threading
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from queue import Queue, Empty
from threading import Lock

logger = logging.getLogger(__name__)

EVENT_TENANT_CREATED = 'tenant.created'
EVENT_TENANT_SUSPENDED = 'tenant.suspended'
EVENT_TENANT_ACTIVATED = 'tenant.activated'
EVENT_TENANT_DELETED = 'tenant.deleted'
EVENT_BUNDLE_CHANGED = 'bundle.changed'
EVENT_MODULE_ACTIVATED = 'module.activated'
EVENT_MODULE_DEACTIVATED = 'module.deactivated'
EVENT_HIGH_RESOURCE_USAGE = 'resource.high_usage'

SUPPORTED_EVENTS = frozenset({
    EVENT_TENANT_CREATED,
    EVENT_TENANT_SUSPENDED,
    EVENT_TENANT_ACTIVATED,
    EVENT_TENANT_DELETED,
    EVENT_BUNDLE_CHANGED,
    EVENT_MODULE_ACTIVATED,
    EVENT_MODULE_DEACTIVATED,
    EVENT_HIGH_RESOURCE_USAGE,
})

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0
DEAD_LETTER_THRESHOLD = 5  # total failures before moving to dead letter

# Queues
_dispatch_queue = Queue()
_retry_queue = Queue()
_dead_letter_queue = Queue()

# Thread management
_processing_thread = None
_thread_lock = Lock()
_thread_running = False


def _load_webhooks():
    from models.system_config import SystemConfig
    from app.extensions import db
    cfg = db.session.query(SystemConfig).filter_by(config_key='owner_webhooks').first()
    if cfg and cfg.config_value:
        try:
            return json.loads(cfg.config_value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _sign_payload(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def _dispatch_single(webhook: dict, event: str, payload: dict, retry_count: int = 0):
    url = webhook.get('url', '').strip()
    if not url:
        return False
    secret = webhook.get('secret', '')
    body = json.dumps(payload, ensure_ascii=False, default=str).encode('utf-8')
    signature = _sign_payload(body, secret) if secret else ''
    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Event': event,
        'X-Webhook-Signature': signature,
        'User-Agent': 'MedicalSystem-Webhook/1.0',
    }
    req = Request(url, data=body, headers=headers, method='POST')
    try:
        with urlopen(req, timeout=10) as resp:
            status = resp.status
            logger.info("Webhook %s event=%s status=%s", url, event, status)
            return 200 <= status < 300
    except HTTPError as e:
        logger.warning("Webhook HTTP error %s event=%s status=%s", url, event, e.code)
        return False
    except URLError as e:
        logger.warning("Webhook connection error %s event=%s %s", url, event, e.reason)
        return False
    except Exception as e:
        logger.error("Webhook unexpected error %s event=%s %s", url, event, e)
        return False


def _enqueue_for_retry(webhook: dict, event: str, payload: dict, retry_count: int):
    """Add webhook to retry queue with backoff delay."""
    delay = min(INITIAL_RETRY_DELAY * (2 ** retry_count), MAX_RETRY_DELAY)
    retry_item = {
        'webhook': webhook,
        'event': event,
        'payload': payload,
        'retry_count': retry_count,
        'next_retry': time.time() + delay,
        'total_attempts': retry_count + 1,
    }
    _retry_queue.put(retry_item)
    logger.info("Webhook queued for retry %s (attempt %s, delay %.1fs)", webhook.get('url'), retry_count + 1, delay)


def _enqueue_to_dead_letter(webhook: dict, event: str, payload: dict, error: str):
    """Move webhook to dead letter queue after max retries exceeded."""
    dead_item = {
        'webhook': webhook,
        'event': event,
        'payload': payload,
        'error': error,
        'failed_at': datetime.now(timezone.utc).isoformat(),
    }
    _dead_letter_queue.put(dead_item)
    logger.error("Webhook moved to dead letter: %s event=%s error=%s", webhook.get('url'), event, error)


def _process_retry_queue():
    """Background thread to process retry queue."""
    while _thread_running:
        try:
            item = _retry_queue.get(timeout=1)
            now = time.time()
            if now < item['next_retry']:
                _retry_queue.put(item)
                time.sleep(1)
                continue

            success = _dispatch_single(item['webhook'], item['event'], item['payload'])
            if success:
                logger.info("Webhook retry succeeded: %s", item['webhook'].get('url'))
            else:
                if item['retry_count'] + 1 >= MAX_RETRIES:
                    _enqueue_to_dead_letter(
                        item['webhook'], item['event'], item['payload'],
                        f"Failed after {MAX_RETRIES} attempts"
                    )
                else:
                    _enqueue_for_retry(
                        item['webhook'], item['event'], item['payload'],
                        item['retry_count'] + 1
                    )

            _retry_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logger.error("Error processing retry queue: %s", e)


def _process_dispatch_queue():
    """Background thread to process main dispatch queue."""
    while _thread_running:
        try:
            item = _dispatch_queue.get(timeout=1)
            webhook = item['webhook']
            event = item['event']
            payload = item['payload']

            success = _dispatch_single(webhook, event, payload)
            if not success:
                _enqueue_for_retry(webhook, event, payload, 0)

            _dispatch_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logger.error("Error processing dispatch queue: %s", e)


def _start_background_threads():
    """Start background processing threads."""
    global _thread_running, _processing_thread
    with _thread_lock:
        if _thread_running:
            return
        _thread_running = True

        _processing_thread = threading.Thread(target=_process_dispatch_queue, daemon=True)
        _processing_thread.start()

        retry_thread = threading.Thread(target=_process_retry_queue, daemon=True)
        retry_thread.start()

        logger.info("Webhook service background threads started")


def _stop_background_threads():
    """Stop background processing threads."""
    global _thread_running, _processing_thread
    with _thread_lock:
        _thread_running = False
        if _processing_thread:
            _processing_thread.join(timeout=5)
            _processing_thread = None
        logger.info("Webhook service background threads stopped")


def dispatch_webhook(event: str, data: dict = None):
    """Fire all webhooks registered for the given event with retry support."""
    if event not in SUPPORTED_EVENTS:
        logger.warning("Unknown webhook event: %s", event)
        return

    webhooks = _load_webhooks()
    if not webhooks:
        return

    payload = {
        'event': event,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data': data or {},
    }

    for wh in webhooks:
        wh_events = wh.get('events', '').strip()
        if wh_events and wh_events != '*':
            matched = False
            for e in wh_events.replace(',', ' ').split():
                if e.strip() == event:
                    matched = True
                    break
            if not matched:
                continue

        _dispatch_queue.put({'webhook': wh, 'event': event, 'payload': payload})

    logger.debug("Enqueued %d webhooks for event %s", len(webhooks), event)


def get_queue_stats():
    """Get current queue statistics for monitoring."""
    return {
        'dispatch_queue_size': _dispatch_queue.qsize(),
        'retry_queue_size': _retry_queue.qsize(),
        'dead_letter_queue_size': _dead_letter_queue.qsize(),
    }


def init_webhook_service():
    """Initialize webhook service with background threads."""
    _start_background_threads()
    logger.info("Webhook service initialized")


def shutdown_webhook_service():
    """Shutdown webhook service and background threads."""
    _stop_background_threads()
    logger.info("Webhook service shutdown")