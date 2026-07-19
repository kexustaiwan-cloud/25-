"""
scan_scheduler.py — 背景排程掃描器（含自我修復機制）

核心概念：把「掃描」跟「使用者看網頁」這兩件事拆開。
- 這裡的背景執行緒會照排程（預設每 SCAN_INTERVAL_MIN 分鐘）自己跑一次掃描，
  跑完寫進 scan_cache。
- 網頁那邊（value_scan_logic.run()）永遠只是讀 scan_cache 裡最新的結果來顯示，
  不會因為訪客同時進站而觸發運算，所以幾百人同時看網頁都不會卡住。

自我修復設計（避免「網頁還活著、但背景排程默默停掉」的狀況）：
- _loop 內每一輪都包在 try/except 裡，任何例外都只會記錄、不會讓迴圈中斷，
  下一輪照樣會繼續跑，不會因為單次掃描出錯就整個排程停擺。
- ensure_scheduler_alive() 會在「每一次有人載入網頁」時被呼叫，檢查背景執行緒
  是否還活著（thread.is_alive()），如果因為某種未預期的狀況死掉了，
  會立刻重新啟動一份新的，不需要等 Render 重新部署或重啟服務。
- 剛啟動或重啟時，如果第一次掃描失敗，會用較短的間隔（INITIAL_RETRY_SEC）
  反覆重試，直到成功為止，才會切回正常的 SCAN_INTERVAL_MIN 排程間隔，
  讓網頁盡快有資料可以顯示，不會一直空白。

注意（無法用程式碼解決的平台限制）：
Render 免費方案的 Web Service 只要 15 分鐘沒有 HTTP 連線進來，
Render 會直接把整個 process 關掉「睡眠」，這是平台層級的行為，
process 一旦被關掉，這支程式（包含這個背景執行緒）也會跟著完全停止，
不是程式碼能攔截或防止的。要做到「網站/掃描永遠不停」，
需要下列其中一種方式（詳見 render.yaml 內的說明）：
  1) 搭配外部喚醒服務（UptimeRobot / cron-job.org）每 10 分鐘 ping 一次網址，
     讓 Render 誤以為一直有人連線，不會觸發睡眠。
  2) 升級到 Render 付費方案並開啟「Always On」。

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

SCAN_INTERVAL_MIN   = int(os.environ.get('SCAN_INTERVAL_MIN', '15'))
ONLY_MARKET_HOURS    = os.environ.get('ONLY_MARKET_HOURS', '1') == '1'
INITIAL_RETRY_SEC    = 60   # 啟動時若第一次掃描失敗，多久後重試（秒）

_scan_lock         = threading.Lock()   # 確保同一時間只有一次掃描在跑
_start_lock        = threading.Lock()   # 保護「啟動/檢查存活」這段邏輯的執行緒安全
_scheduler_thread  = None                # 目前這一份背景執行緒的參考，用來檢查是否還活著


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
    通常直接傳入 value_scan_logic._run_scan_core。

    若已經有掃描在跑（例如管理者手動觸發即時掃描），本次排程會直接略過，
    不會搶著跑、也不會把資料寫壞。
    回傳 True 代表本次真的有執行掃描並成功寫入快取；
    回傳 False 代表被跳過（已有掃描在跑）或本次執行失敗（但不會拋出例外）。
    """
    if not _scan_lock.acquire(blocking=False):
        print('[scan_scheduler] 已有掃描在進行中，本輪排程略過')
        return False
    try:
        scan_cache.save_scan_status('running', pct=0)

        def _log(msg, pct=None):
            print(f'[scan_scheduler] {msg}')
            # 把即時進度寫進共用快取，讓任何人看網頁時都能看到目前掃描到哪裡，
            # 不用等整個掃描跑完才有畫面反應。
            scan_cache.save_scan_status('running', message=msg, pct=pct)

        try:
            results, etf_results, regime, stats = run_scan_core_fn(params, _log)
            scan_cache.save_scan(results, etf_results, regime, stats, params, status='ok')
            scan_cache.save_scan_status('idle', pct=100)
            # 這組參數（不論是排程預設或管理者手動調整）成功跑完，
            # 就把它記錄成「目前生效參數」，下一輪排程會沿用這組，不會被寫死的預設值蓋掉。
            scan_cache.save_active_params(params)
            print('[scan_scheduler] 本輪排程掃描完成，已更新快取')
            return True
        except Exception as e:
            # 掃描失敗只記錄錯誤狀態，故意「不」覆蓋掉舊的快取結果，
            # 這樣網頁會繼續顯示上一次成功掃描的資料，不會突然變成空白。
            scan_cache.save_scan_status('error', message=str(e))
            print(f'[scan_scheduler] 掃描失敗（保留舊快取，不清空）：{e}')
            return False
    finally:
        _scan_lock.release()


def _current_params(default_params):
    """
    決定「這一輪」該用哪組參數掃描：
    - 如果曾經有人（管理者手動觸發，或先前的排程）成功跑完一次掃描，
      優先沿用那組「目前生效參數」。
    - 只有在完全沒有任何生效參數紀錄時（例如剛部署、第一次啟動），
      才會退回使用寫死的 default_params。
    這樣管理者手動調整過的參數，會一直持續生效到下次管理者再改，
    不會被排程用舊的預設值蓋掉。
    """
    active = scan_cache.load_active_params()
    return active if active else default_params


def _loop(default_params, run_scan_core_fn):
    """
    背景排程主迴圈。設計成「幾乎打不死」：
    - 最外層 while True 加上 try/except 包住整輪內容，
      任何未預期例外都只會被記錄下來，迴圈本身絕不會因此中斷。
    - 啟動時第一次掃描如果失敗，會用較短的 INITIAL_RETRY_SEC 反覆重試，
      而不是傻等一整個 SCAN_INTERVAL_MIN，讓網站盡快有資料可看。
    """
    # ── 啟動時先跑一次，並且失敗就快速重試，直到成功 ──────────────────
    while True:
        try:
            ok = run_scan_once(_current_params(default_params), run_scan_core_fn)
        except Exception as e:
            ok = False
            print(f'[scan_scheduler] 啟動時掃描發生未攔截例外：{e}')
        if ok:
            break
        print(f'[scan_scheduler] 啟動掃描尚未成功，{INITIAL_RETRY_SEC} 秒後重試...')
        time.sleep(INITIAL_RETRY_SEC)

    # ── 進入正常排程週期 ──────────────────────────────────────────────
    while True:
        try:
            time.sleep(max(60, SCAN_INTERVAL_MIN * 60))
            if (not ONLY_MARKET_HOURS) or _in_market_window():
                run_scan_once(_current_params(default_params), run_scan_core_fn)
            else:
                print('[scan_scheduler] 非盤中時間，略過本輪掃描')
        except Exception as e:
            # 任何未預期例外都只記錄，絕不讓 while True 迴圈跳出，
            # 下一輪會繼續正常運作。
            print(f'[scan_scheduler] loop 例外（已忽略，排程繼續運作）：{e}')


def _spawn_thread(default_params, run_scan_core_fn):
    global _scheduler_thread
    t = threading.Thread(
        target=_loop, args=(default_params, run_scan_core_fn), daemon=True)
    t.start()
    _scheduler_thread = t
    print(f'[scan_scheduler] 背景排程執行緒已啟動，每 {SCAN_INTERVAL_MIN} 分鐘掃描一次'
          f'（{"僅盤中" if ONLY_MARKET_HOURS else "全天候"}）')


def start_background_scheduler(default_params, run_scan_core_fn):
    """啟動背景排程執行緒（若尚未啟動）。"""
    with _start_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return
        _spawn_thread(default_params, run_scan_core_fn)


def ensure_scheduler_alive(default_params, run_scan_core_fn):
    """
    看門狗：確認背景排程執行緒還活著，若不在或已死掉（理論上因為 _loop 已經
    設計成打不死，這應該極少發生），立刻重新啟動一份，讓掃描不會無聲無息地
    永久停止。建議在每次網頁請求（value_scan_logic.run() 開頭）都呼叫一次，
    成本很低（多半只是檢查一個 boolean），可以放心每次都呼叫。
    """
    with _start_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            print('[scan_scheduler] 偵測到背景排程未啟動或已停止，重新啟動中...')
            _spawn_thread(default_params, run_scan_core_fn)
