import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

TW_TZ = pytz.timezone('Asia/Taipei')


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


def _run_scan(params, progress_bar, status_box):
    """同步執行一次完整掃描，回傳 (results, etf_results, regime, stats)"""

    def _log(msg, pct=None):
        status_box.write(msg)
        if pct is not None:
            progress_bar.progress(min(int(pct), 100))

    _log('載入掃描模組...', 2)
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
    _log('掃描模組就緒', 5)

    # ── Step 1: 撿股讚基本面 ──────────────────────────────────────────
    _log('抓取撿股讚基本面資料...', 8)
    fund_df, html = sc.fetch_wespai_fundamental(force=True)
    if fund_df is None or fund_df.empty:
        raise RuntimeError('撿股讚基本面抓取失敗或空白，請確認 wespai.com 是否可連線')
    _log(f'撿股讚抓到 {len(fund_df)} 檔', 15)

    fund_set = sc.build_fundamental_filter(fund_df)
    stocks = sc.build_yoy_stocks(fund_df, fund_set)
    _log(f'YOY≥{params["yoy_min"]:.0f}% 達標：{len(stocks)} 檔', 22)

    # ── Step 2: 月增率 ────────────────────────────────────────────────
    _log('抓取月增率 (MoM) 資料...', 25)
    mom_dict = sc.fetch_mom_data(list(stocks.keys()), wespai_html=html, force=True)
    _log(f'MoM：{len(mom_dict)} 檔', 30)

    # ── Step 3: 財務品質 ──────────────────────────────────────────────
    _log('抓取財務品質資料...', 33)
    df_fin = sc.fetch_wespai_fin_quality(force=True)
    fin_dict = sc.fetch_fin_quality_batch(stocks, force=True, df_fin_wespai=df_fin)
    fin_set = sc.build_fin_quality_filter(fund_set, fin_dict)
    scan_st = ({c: n for c, n in stocks.items() if c in fin_set}
               if params['fin_block'] else stocks)
    _log(f'財務篩選後：{len(scan_st)} 檔（財務達標 {len(fin_set)}/{len(stocks)}）', 40)

    # ── Step 4: 大盤狀態 ──────────────────────────────────────────────
    _log('計算大盤狀態...', 43)
    try:
        regime = sc.calc_market_regime(force=True)
    except Exception as e:
        regime = {}
        _log(f'大盤狀態計算失敗（跳過）：{e}', 43)

    # ── Step 5: ETF 掃描 ──────────────────────────────────────────────
    _log('掃描主動式 ETF...', 46)
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
        _log(f'ETF 清單抓取失敗（跳過）：{e}', 48)
    _log(f'ETF 完成：{len(etf_results)} 檔' +
         (f'（{etf_fail} 失敗）' if etf_fail else ''), 50)

    # ── Step 6: 個股掃描 ────────────────────────────────────────────
    total = len(scan_st) or 1
    results = []
    fail_n = 0
    _log(f'開始個股分析，共 {len(scan_st)} 檔...', 53)
    active_params_stock = sc.get_active_params(datetime.now(TW_TZ))

    for i, (tid, name) in enumerate(scan_st.items()):
        try:
            r = sc.analyze_stock(
                tid, name, sc._guess_mtype(tid),
                entry_price=None,
                active_params=active_params_stock,
                mom_pct=sc.get_mom_pct(tid, fund_df, mom_dict),
                fin_quality=fin_dict.get(tid),
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
            _log(msg, pct)

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

    _log(f'✅ 掃描完成！{len(results)} 檔個股 + {len(etf_results)} 檔ETF'
         + (f'，{fail_n} 檔失敗已跳過' if fail_n else ''), 100)

    return results, etf_results, regime, stats


def run():
    # ── 篩選參數（側邊欄） ──────────────────────────────────────────
    st.sidebar.markdown("### 🎛️ 掃描參數")
    k_threshold = st.sidebar.number_input("K值門檻（≤）", value=30, step=1)
    yoy_min = st.sidebar.number_input("營收YOY最低(%)", value=15.0, step=1.0)
    gross_margin_min = st.sidebar.number_input("毛利率最低(%)", value=25.0, step=1.0)
    op_margin_min = st.sidebar.number_input("營益率最低(%)", value=15.0, step=1.0)
    fin_block = st.sidebar.checkbox("財務不達標時排除", value=True)

    params = {
        'k_threshold': int(k_threshold),
        'yoy_min': float(yoy_min),
        'gross_margin_min': float(gross_margin_min),
        'op_margin_min': float(op_margin_min),
        'fin_block': bool(fin_block),
    }

    # ── 觸發掃描 ──────────────────────────────────────────────────
    if st.button("🚀 開始掃描", type="primary"):
        progress_bar = st.progress(0)
        status_box = st.empty()
        try:
            with st.spinner("掃描進行中，請稍候..."):
                results, etf_results, regime, stats = _run_scan(params, progress_bar, status_box)
            st.session_state['scan_results'] = results
            st.session_state['scan_etf_results'] = etf_results
            st.session_state['scan_regime'] = regime
            st.session_state['scan_stats'] = stats
            st.session_state['scan_time'] = _now_tw().strftime('%Y-%m-%d %H:%M:%S')
            st.success("掃描完成！")
        except Exception as e:
            st.error(f"❌ 掃描失敗：{e}")

    # ── 顯示上次結果 ──────────────────────────────────────────────
    if 'scan_results' in st.session_state:
        st.caption(f"最後掃描時間：{st.session_state.get('scan_time', '')}")

        stats = st.session_state.get('scan_stats', {})
        if stats:
            cols = st.columns(4)
            cols[0].metric("撿股讚總檔數", stats.get('total_wespai', 0))
            cols[1].metric("YOY達標", stats.get('yoy_pass', 0))
            cols[2].metric("財務達標", stats.get('fin_pass', 0))
            cols[3].metric("掃描檔數", stats.get('scan_count', 0))

        regime = st.session_state.get('scan_regime')
        if regime:
            st.markdown("#### 📊 大盤狀態")
            st.json(regime)

        st.markdown("#### 📈 個股掃描結果")
        results = st.session_state.get('scan_results', [])
        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("本次掃描沒有符合條件的個股。")

        st.markdown("#### 🧺 ETF 掃描結果")
        etf_results = st.session_state.get('scan_etf_results', [])
        if etf_results:
            df_etf = pd.DataFrame(etf_results)
            st.dataframe(df_etf, use_container_width=True)
        else:
            st.info("本次掃描沒有 ETF 結果。")
    else:
        st.info("點選上方「開始掃描」按鈕以執行股票篩選。")
