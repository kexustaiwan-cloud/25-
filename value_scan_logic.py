import streamlit as st
import pandas as pd
import os
from datetime import datetime
import pytz

import scan_cache
import scan_scheduler

TW_TZ = pytz.timezone('Asia/Taipei')

# 管理者密碼（來自 render.yaml 的環境變數 ADMIN_PASSWORD）
# 只有輸入正確密碼的人，才能看到/使用「手動觸發即時掃描」功能，
# 其他所有訪客一律只能看背景排程寫進快取的公開結果（唯讀）。
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

# 公開頁面使用的「背景排程掃描」預設參數 —— 所有訪客共用同一份結果，
# 就是靠固定這組參數去掃描、寫入快取，大家看到的都是同一份。
DEFAULT_SCAN_PARAMS = {
    'k_threshold':       30,
    'k_interval':        '60m',
    'k_interval_label':  '60分K',
    'ma_custom_n':       20,
    'yoy_min':           15.0,
    'gross_margin_min':  25.0,
    'op_margin_min':     15.0,
    'fin_block':         True,
}


def _now_tw():
    return datetime.now(TW_TZ)


def _r2d(r):
    """result dict → 適合顯示/JSON 的乾淨 dict"""
    out = {}
    for k, v in r.items():
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat()
        elif hasattr(v, 'to_dict'):
            out[k] = str(v)
        elif isinstance(v, float) and v != v:  # NaN
            out[k] = None
        else:
            out[k] = v
    return out


def _run_scan_core(params, log_fn):
    """
    純核心掃描邏輯，不依賴 Streamlit UI，可以被：
    1) 背景排程執行緒（scan_scheduler）直接呼叫
    2) 管理者手動觸發即時掃描時透過 _run_scan() 包一層呼叫
    log_fn(msg, pct=None) 由呼叫端提供，只負責回報進度。
    回傳 (results, etf_results, regime, stats)
    """
    log_fn('載入掃描模組...', 2)
    try:
        import scanner_core as sc
    except Exception as e:
        raise RuntimeError(f'scanner_core 載入失敗：{e}')

    # 套用參數
    sc.K_THRESHOLD = params['k_threshold']
    sc.YOY_MIN_PCT = params['yoy_min']
    sc.GROSS_MARGIN_MIN = params['gross_margin_min']
    sc.OP_MARGIN_MIN = params['op_margin_min']
    sc.FIN_BLOCK_ON_FAIL = params['fin_block']
    k_interval  = params.get('k_interval', '60m')
    ma_custom_n = params.get('ma_custom_n')
    log_fn('掃描模組就緒', 5)

    # ── Step 1: 撿股讚基本面 ──────────────────────────────────────────
    log_fn('抓取撿股讚基本面資料...', 8)
    fund_df, html = sc.fetch_wespai_fundamental(force=True)
    if fund_df is None or fund_df.empty:
        raise RuntimeError('撿股讚基本面抓取失敗或空白，請確認 wespai.com 是否可連線')
    log_fn(f'撿股讚抓到 {len(fund_df)} 檔', 15)

    fund_set = sc.build_fundamental_filter(fund_df)
    stocks = sc.build_yoy_stocks(fund_df, fund_set)
    log_fn(f'YOY≥{params["yoy_min"]:.0f}% 達標：{len(stocks)} 檔', 22)

    # ── Step 2: 月增率 ────────────────────────────────────────────────
    log_fn('抓取月增率 (MoM) 資料...', 25)
    mom_dict = sc.fetch_mom_data(list(stocks.keys()), wespai_html=html, force=True)
    log_fn(f'MoM：{len(mom_dict)} 檔', 30)

    # ── Step 3: 財務品質 ──────────────────────────────────────────────
    log_fn('抓取財務品質資料...', 33)
    df_fin = sc.fetch_wespai_fin_quality(force=True)
    fin_dict = sc.fetch_fin_quality_batch(stocks, force=True, df_fin_wespai=df_fin)
    fin_set = sc.build_fin_quality_filter(fund_set, fin_dict)
    scan_st = ({c: n for c, n in stocks.items() if c in fin_set}
               if params['fin_block'] else stocks)
    log_fn(f'財務篩選後：{len(scan_st)} 檔（財務達標 {len(fin_set)}/{len(stocks)}）', 40)

    # ── Step 4: 大盤狀態 ──────────────────────────────────────────────
    log_fn('計算大盤狀態...', 43)
    try:
        regime = sc.calc_market_regime(force=True)
    except Exception as e:
        regime = {}
        log_fn(f'大盤狀態計算失敗（跳過）：{e}', 43)

    # ── Step 5: ETF 掃描 ──────────────────────────────────────────────
    log_fn('掃描主動式 ETF...', 46)
    etf_results = []
    etf_fail = 0
    try:
        active_etfs = sc.fetch_active_etf_list(force=True)
        active_params = sc.get_active_params(datetime.now(TW_TZ))
        for t, n in active_etfs.items():
            try:
                etf_results.append(_r2d(sc.analyze_etf(t, n, active_params)))
            except Exception as e:
                etf_fail += 1
                etf_results.append({'tid': t, 'name': n, 'error': str(e)})
    except Exception as e:
        log_fn(f'ETF 清單抓取失敗（跳過）：{e}', 48)
    log_fn(f'ETF 完成：{len(etf_results)} 檔' +
           (f'（{etf_fail} 失敗）' if etf_fail else ''), 50)

    # ── Step 6: 個股掃描 ────────────────────────────────────────────
    total = len(scan_st) or 1
    results = []
    fail_n = 0
    log_fn(f'開始個股分析，共 {len(scan_st)} 檔...', 53)
    active_params_stock = sc.get_active_params(datetime.now(TW_TZ))

    for i, (tid, name) in enumerate(scan_st.items()):
        try:
            r = sc.analyze_stock(
                tid, name, sc._guess_mtype(tid),
                entry_price=None,
                active_params=active_params_stock,
                mom_pct=sc.get_mom_pct(tid, fund_df, mom_dict),
                fin_quality=fin_dict.get(tid),
                k_interval=k_interval,
                ma_custom_n=ma_custom_n,
            )
            results.append(_r2d(r))
        except Exception as e:
            fail_n += 1
            results.append({'tid': tid, 'name': name, 'error': str(e)})

        pct = 53 + int((i + 1) / total * 44)
        if (i + 1) % 5 == 0 or (i + 1) == total:
            msg = f'個股進度 {i + 1}/{total}'
            if fail_n:
                msg += f'（{fail_n} 失敗跳過）'
            log_fn(msg, pct)

    fp = sum(1 for c in stocks if fin_dict.get(c, {}).get('fin_pass') is True)
    ff = sum(1 for c in stocks if fin_dict.get(c, {}).get('fin_pass') is False)

    stats = {
        'total_wespai': len(fund_df),
        'yoy_pass': len(stocks),
        'fin_pass': fp,
        'fin_fail': ff,
        'scan_count': len(scan_st),
        'etf_count': len(etf_results),
        'mom_count': len(mom_dict),
        'fail_count': fail_n,
    }

    log_fn(f'✅ 掃描完成！{len(results)} 檔個股 + {len(etf_results)} 檔ETF'
           + (f'，{fail_n} 檔失敗已跳過' if fail_n else ''), 100)

    return results, etf_results, regime, stats


def _run_scan(params, progress_bar, status_box):
    """Streamlit 顯示用的包裝，給管理者手動觸發即時掃描時使用（會即時更新進度條）"""
    def log_fn(msg, pct=None):
        status_box.write(msg)
        if pct is not None:
            progress_bar.progress(min(int(pct), 100))
    return _run_scan_core(params, log_fn)


def _admin_login_ui():
    """
    在側邊欄顯示管理者登入區塊。
    - 尚未登入：顯示密碼輸入框 + 登入按鈕。
    - 登入成功：st.session_state['is_admin'] = True，並顯示登出按鈕。
    - 這個登入狀態只存在單一瀏覽器分頁的 session 裡，不會影響其他訪客，
      也不會被寫進共用快取，所以不會有「一個人登入、全部人都變管理者」的問題。
    """
    if st.session_state.get('is_admin'):
        st.sidebar.success("🔑 已以管理者身分登入")
        if st.sidebar.button("登出管理者模式"):
            st.session_state['is_admin'] = False
            st.rerun()
        return

    with st.sidebar.expander("🔑 管理者登入"):
        if not ADMIN_PASSWORD:
            st.caption("尚未設定 ADMIN_PASSWORD 環境變數，管理者功能目前無法使用。")
            return
        pwd = st.text_input("管理者密碼", type="password", key="admin_pwd_input")
        if st.button("登入", key="admin_login_btn"):
            if pwd == ADMIN_PASSWORD:
                st.session_state['is_admin'] = True
                st.rerun()
            else:
                st.error("密碼錯誤")


@st.cache_resource
def _ensure_scheduler_started():
    """
    啟動背景排程掃描執行緒。
    用 st.cache_resource 包起來，是為了確保「同一個運行中的 process」
    不管有幾個瀏覽器分頁 / 幾個訪客連進來，背景執行緒都只會啟動一次，
    不會每個 session 各開一條，浪費資源、互搶運算。
    """
    scan_scheduler.start_background_scheduler(DEFAULT_SCAN_PARAMS, _run_scan_core)
    return True


def run():
    # 啟動背景排程掃描（整個 process 只會真正啟動一次）
    _ensure_scheduler_started()

    cache_status = scan_cache.load_scan_status()

    st.sidebar.markdown("### 🎛️ 掃描設定")
    st.sidebar.caption(
        f"公開頁面顯示的是背景自動掃描結果（固定參數），"
        f"每 {os.environ.get('SCAN_INTERVAL_MIN', '15')} 分鐘更新一次，"
        f"所有訪客共用同一份，不會互相卡住或搶資源。"
    )
    with st.sidebar.expander("目前使用的預設參數"):
        st.write(DEFAULT_SCAN_PARAMS)

    st.sidebar.markdown("---")
    _admin_login_ui()

    if st.session_state.get('is_admin'):
        with st.sidebar.expander("🔧 進階：手動觸發即時掃描（管理用途）"):
            st.caption("會暫時佔用運算資源跑一次即時掃描，完成後直接覆蓋公開快取，所有訪客都會看到新結果。")
            k_threshold = st.number_input("K值門檻（≤）", value=30, step=1, key='adv_k')
            k_interval_label = st.selectbox(
                "K值週期", ["60分K", "日K", "週K"], index=0, key='adv_ki')
            _K_INTERVAL_MAP = {"60分K": "60m", "日K": "day", "週K": "week"}
            ma_custom_n = st.number_input(
                "股價高於N日均線（1-600）", min_value=1, max_value=600, value=20, step=1, key='adv_ma')
            yoy_min = st.number_input("營收YOY最低(%)", value=15.0, step=1.0, key='adv_yoy')
            gross_margin_min = st.number_input("毛利率最低(%)", value=25.0, step=1.0, key='adv_gm')
            op_margin_min = st.number_input("營益率最低(%)", value=15.0, step=1.0, key='adv_om')
            fin_block = st.checkbox("財務不達標時排除", value=True, key='adv_fb')

            adv_params = {
                'k_threshold':      int(k_threshold),
                'k_interval':       _K_INTERVAL_MAP[k_interval_label],
                'k_interval_label': k_interval_label,
                'ma_custom_n':      int(ma_custom_n),
                'yoy_min':          float(yoy_min),
                'gross_margin_min': float(gross_margin_min),
                'op_margin_min':    float(op_margin_min),
                'fin_block':        bool(fin_block),
            }

            if st.button("🚀 立即執行即時掃描（會覆蓋公開快取）", type="primary"):
                progress_bar = st.progress(0)
                status_box = st.empty()
                try:
                    with st.spinner("掃描進行中，請稍候..."):
                        results, etf_results, regime, stats = _run_scan(
                            adv_params, progress_bar, status_box)
                    scan_cache.save_scan(results, etf_results, regime, stats, adv_params, status='ok')
                    st.success("掃描完成，已更新公開快取！")
                except Exception as e:
                    st.error(f"❌ 掃描失敗：{e}")
    else:
        st.sidebar.caption("🔒 手動即時掃描僅限管理者使用，請先於上方登入。")

    if st.sidebar.button("🔄 重新整理頁面"):
        st.rerun()

    # ── 讀取快取並顯示（所有訪客共用同一份，不會觸發運算） ─────────────
    cached = scan_cache.load_scan()
    if not cached:
        st.info("背景排程掃描尚未產生第一筆結果，請稍候幾分鐘後重新整理頁面。")
        return

    status_label = {
        'running': '🟡 掃描中...',
        'idle':    '🟢 待命中（顯示最新一次結果）',
        'error':   '🔴 上次排程掃描失敗（將於下次排程自動重試）',
    }.get(cache_status.get('status'), '─')
    st.caption(f"最後掃描時間：{cached.get('scan_time', '')}　|　排程狀態：{status_label}")

    if cache_status.get('status') == 'error' and cache_status.get('message'):
        st.warning(f"背景掃描錯誤訊息：{cache_status['message']}")

    stats = cached.get('stats', {})
    if stats:
        cols = st.columns(4)
        cols[0].metric("撿股讚總檔數", stats.get('total_wespai', 0))
        cols[1].metric("YOY達標", stats.get('yoy_pass', 0))
        cols[2].metric("財務達標", stats.get('fin_pass', 0))
        cols[3].metric("掃描檔數", stats.get('scan_count', 0))

    regime = cached.get('regime')
    if regime:
        st.markdown("#### 📊 大盤狀態")

        icon     = regime.get('icon', '')
        name_    = regime.get('name', '')
        score    = regime.get('score', 0)
        position = regime.get('position', '─')
        strategy = regime.get('strategy', '─')

        c1, c2, c3 = st.columns([1, 1, 2])
        c1.metric("大盤燈號", f"{icon} {name_}")
        c2.metric("綜合分數", f"{score} 分")
        with c3:
            st.markdown(f"**建議倉位：** {position}")
            st.markdown(f"**操作策略：** {strategy}")

        if regime.get('warn_2022') or regime.get('overheat'):
            warn_msg = regime.get('warn_msg') or '⚠️ 大盤出現警示訊號，請留意風險'
            st.warning(warn_msg)

        detail = regime.get('detail', {})
        if detail:
            st.markdown("###### 細項評分")
            for label, val in detail.items():
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    pts, desc = val[0], val[1]
                    st.markdown(f"- **{label}**：{pts} 分 — {desc}")
                else:
                    st.markdown(f"- **{label}**：{val}")

        tw_last = regime.get('tw_last')
        last_update = regime.get('last_update')
        if tw_last or last_update:
            c4, c5 = st.columns(2)
            if tw_last:
                c4.metric("加權指數", f"{tw_last:,.0f}")
            if last_update:
                try:
                    dt_str = datetime.fromtimestamp(
                        last_update, TW_TZ).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    dt_str = str(last_update)
                c5.metric("資料更新時間", dt_str)

    st.markdown("#### 📈 個股掃描結果")
    results = cached.get('results', [])
    if results:
        df = pd.DataFrame(results)
        ma_n = cached.get('params', {}).get('ma_custom_n', 20)
        if 'above_ma_custom' in df.columns:
            only_above = st.checkbox(f"只顯示股價高於 {ma_n} 日均線的股票", value=False)
            if only_above:
                df = df[df['above_ma_custom'] == True]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("本次掃描沒有符合條件的個股。")

    st.markdown("#### 🧺 ETF 掃描結果")
    etf_results = cached.get('etf_results', [])
    if etf_results:
        df_etf = pd.DataFrame(etf_results)
        st.dataframe(df_etf, use_container_width=True)
    else:
        st.info("本次掃描沒有 ETF 結果。")
