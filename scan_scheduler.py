"""
scan_scheduler.py — 背景排程掃描器

核心概念：把「掃描」跟「使用者看網頁」這兩件事拆開。
- 這裡的背景執行緒會照排程（預設每 SCAN_INTERVAL_MIN 分鐘）自己跑一次掃描，
  跑完寫進 scan_cache。
- 網頁那邊（stock_logic.run()）永遠只是讀 scan_cache 裡最新的結果來顯示，
  不會因為訪客同時進站而觸發運算，所以幾百人同時看網頁都不會卡住。

環境變數：
- SCAN_INTERVAL_MIN  : 幾分鐘掃描一次（預設 15）
- ONLY_MARKET_HOURS   : '1' 代表只在台股盤中時間掃描（預設開啟，省資源）
"""
import os
import threading
import time
from datetime import datetime
import pytz

import scan_cache

TW_TZ = pytz.timezone('Asia/Taipei')

SCAN_INTERVAL_MIN  = int(os.environ.get('SCAN_INTERVAL_MIN', '15'))
ONLY_MARKET_HOURS  = os.environ.get('ONLY_MARKET_HOURS', '1') == '1'

_scan_lock       = threading.Lock()   # 確保同一時間只有一次掃描在跑
_start_lock      = threading.Lock()   # 確保背景執行緒只會被啟動一次
_scheduler_started = False


def _in_market_window(dt=None):
    """台股盤中時間（含開盤前後緩衝）：週一到週五 08:30-14:00"""
    dt = dt or datetime.now(TW_TZ)
    if dt.weekday() >= 5:  # 週六日
        return False
    hm = dt.strftime('%H:%M')
    return '08:30' <= hm <= '14:00'


def run_scan_once(params, run_scan_core_fn):
    """
    執行一次掃描並寫入快取。
    run_scan_core_fn(params, log_fn) -> (results, etf_results, regime, stats)
    通常直接傳入 stock_logic._run_scan_core。

    若已經有掃描在跑（例如管理者手動觸發即時掃描），本次排程會直接略過，
    不會搶著跑、也不會把資料寫壞。
    回傳 True 代表本次真的有執行掃描，False 代表被跳過。
    """
    if not _scan_lock.acquire(blocking=False):
        print('[scan_scheduler] 已有掃描在進行中，本輪排程略過')
        return False
    try:
        scan_cache.save_scan_status('running')

        def _log(msg, pct=None):
            print(f'[scan_scheduler] {msg}')

        try:
            results, etf_results, regime, stats = run_scan_core_fn(params, _log)
            scan_cache.save_scan(results, etf_results, regime, stats, params, status='ok')
            scan_cache.save_scan_status('idle')
            print('[scan_scheduler] 本輪排程掃描完成，已更新快取')
        except Exception as e:
            scan_cache.save_scan_status('error', message=str(e))
            print(f'[scan_scheduler] 掃描失敗：{e}')
        return True
    finally:
        _scan_lock.release()


def _loop(default_params, run_scan_core_fn):
    # 啟動時先跑一次，避免剛部署時網頁完全沒有資料可顯示
    try:
        run_scan_once(default_params, run_scan_core_fn)
    except Exception as e:
        print(f'[scan_scheduler] 啟動時第一次掃描失敗：{e}')

    while True:
        time.sleep(max(60, SCAN_INTERVAL_MIN * 60))
        try:
            if (not ONLY_MARKET_HOURS) or _in_market_window():
                run_scan_once(default_params, run_scan_core_fn)
            else:
                print('[scan_scheduler] 非盤中時間，略過本輪掃描')
        except Exception as e:
            print(f'[scan_scheduler] loop 例外：{e}')


def start_background_scheduler(default_params, run_scan_core_fn):
    """啟動背景排程執行緒。整個 process 生命週期內只會真正啟動一次
    （由呼叫端搭配 st.cache_resource 之類的機制，確保多個 session 不會重複啟動）。"""
    global _scheduler_started
    with _start_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
        t = threading.Thread(
            target=_loop, args=(default_params, run_scan_core_fn), daemon=True)
        t.start()
        print(f'[scan_scheduler] 背景排程已啟動，每 {SCAN_INTERVAL_MIN} 分鐘掃描一次'
              f'（{"僅盤中" if ONLY_MARKET_HOURS else "全天候"}）')
