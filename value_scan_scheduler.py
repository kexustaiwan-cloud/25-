"""
scan_cache.py — 掃描結果共享快取層

目的：讓「背景排程掃描」寫入的最新結果，能被所有訪客的網頁請求讀取，
      不需要每個訪客各自觸發一次掃描。

用 SQLite（Python 內建，不需額外套件）存放：
- 'latest' : 最新一次成功掃描的完整結果（results / etf_results / regime / stats / params）
- 'status' : 目前排程狀態（running / idle / error）＋錯誤訊息

注意：Render 免費方案的磁碟是「非持久化」的（重新部署/重啟會清空），
      所以 DB 檔案只是拿來在「同一個運行中的 process」內共享資料，
      不是拿來長期保存歷史記錄用的。
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
import pytz

TW_TZ = pytz.timezone('Asia/Taipei')

_DB_PATH = os.environ.get(
    'SCAN_CACHE_DB', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scan_cache.db')
)
_LOCK = threading.Lock()


def _get_conn():
    conn = sqlite3.connect(_DB_PATH, timeout=10, check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scan_cache (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    ''')
    return conn


def _upsert(key, value_dict):
    value = json.dumps(value_dict, ensure_ascii=False)
    now = datetime.now(TW_TZ).isoformat()
    with _LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                'INSERT INTO scan_cache(key, value, updated_at) VALUES (?, ?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
                (key, value, now)
            )
            conn.commit()
        finally:
            conn.close()


def _select(key):
    with _LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                'SELECT value, updated_at FROM scan_cache WHERE key = ?', (key,)
            ).fetchone()
        finally:
            conn.close()
    return row


def save_scan(results, etf_results, regime, stats, params, status='ok', error=None):
    """寫入最新一次掃描結果（覆蓋式，只保留最新一筆）。"""
    payload = {
        'results':     results,
        'etf_results': etf_results,
        'regime':      regime,
        'stats':       stats,
        'params':      params,
        'status':      status,
        'error':       error,
        'scan_time':   datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S'),
    }
    _upsert('latest', payload)


def load_scan():
    """讀取最新一次掃描結果；若尚無任何資料回傳 None。"""
    row = _select('latest')
    if not row:
        return None
    value, updated_at = row
    try:
        payload = json.loads(value)
    except Exception:
        return None
    payload['_cache_updated_at'] = updated_at
    return payload


def save_scan_status(status, message=None):
    """更新排程執行狀態（'running' / 'idle' / 'error'），不動掃描結果本體。"""
    _upsert('status', {'status': status, 'message': message})


def load_scan_status():
    row = _select('status')
    if not row:
        return {'status': 'idle', 'message': None}
    try:
        return json.loads(row[0])
    except Exception:
        return {'status': 'idle', 'message': None}
