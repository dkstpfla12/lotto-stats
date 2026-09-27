"""
로또 6/45 통계 대시보드 (Streamlit)

데이터: Google Sheets `LOTTO_DATA_API`의 "웹에 게시" CSV 3종
  - 매주 일 06:00 PC 수집 → 08:00 시트 반영 → 게시 CSV 자동 갱신 → 이 앱은 1시간 캐시
로컬 개발: 환경변수 LOTTO_LOCAL_DATA=<data 폴더 경로> 를 주면 CSV 파일을 직접 읽음
"""
import os
from math import comb, exp, pi, sqrt
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ───────────────────────── 설정 ─────────────────────────
BASE = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vRgvEYfl063X0XzTIi7IXNq-EiUGBY6CIOPGZz6bDtf46H4bHCL2q22gTHuaAueBmZob6MRkHIJOHOK"
        "/pub?single=true&output=csv&gid=")
SOURCES = {
    "draw": ("lotto_draws.csv", BASE + "1953774850"),
    "draw_stats": ("draw_stats.csv", BASE + "1009708128"),
    "number_status": ("number_status.csv", BASE + "1037086401"),
}
SUM_MEAN = 138.0
SUM_SD = sqrt(6 * (45 ** 2 - 1) / 12 * 39 / 44)  # ≈ 29.95 (1~45에서 6개 비복원추출)

BLUE = "#2a78d6"      # 주 시리즈
ORANGE = "#eb6834"    # 강조(최신 회차 등)
GRAY = "#8a8985"      # 기준선·이론값
BAND1 = "rgba(42,120,214,0.14)"
BAND2 = "rgba(42,120,214,0.06)"
# 동행복권 공 색상 (번호대별) - 공 표시에만 사용
BALL = [(10, "#fbc400"), (20, "#69c8f2"), (30, "#ff7272"), (40, "#aaaaaa"), (45, "#b0d840")]

st.set_page_config(page_title="로또 6/45 통계", page_icon="🎱", layout="wide")


# ───────────────────────── 데이터 ─────────────────────────
@st.cache_data(ttl=3600, show_spinner="데이터를 불러오는 중…")
def load(name: str) -> pd.DataFrame:
    fname, url = SOURCES[name]
    local = os.environ.get("LOTTO_LOCAL_DATA")
    src = Path(local) / fname if local else url
    return pd.read_csv(src, encoding="utf-8-sig")


try:
    draw, stats, status = load("draw"), load("draw_stats"), load("number_status")
except Exception as e:  # 게시 주소 문제 등
    st.error(f"데이터를 불러오지 못했습니다: {e}")
    st.stop()

draw = draw.sort_values("draw_no").reset_index(drop=True)
stats = stats.sort_values("draw_no").reset_index(drop=True)
NUMS = [f"n{i}" for i in range(1, 7)]
NUM_LABELS = {f"n{i}": f"번호{i}" for i in range(1, 7)}
latest = draw.iloc[-1]
latest_stats = stats.iloc[-1]


def ball_color(n: int) -> str:
    return next(c for hi, c in BALL if n <= hi)


def balls_html(nums, bonus=None, size=44) -> str:
    def one(n, extra=""):
        return (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:{size}px;height:{size}px;border-radius:50%;background:{ball_color(n)};'
                f'color:#fff;font-weight:700;font-size:{size*0.42:.0f}px;margin:2px 3px;'
                f'text-shadow:0 1px 2px rgba(0,0,0,.35);{extra}">{n}</span>')
    html = "".join(one(int(n)) for n in nums)
    if bonus is not None:
        html += f'<span style="margin:0 6px;font-size:{size*0.45:.0f}px;opacity:.6">+</span>' + one(int(bonus))
    return f'<div style="display:flex;flex-wrap:wrap;align-items:center">{html}</div>'


def base_layout(fig, height=360, y_title=None, x_title=None):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=24, b=8), hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      bargap=0.25)
    fig.update_xaxes(title=x_title, showgrid=False)
    fig.update_yaxes(title=y_title, gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def hyper(k: int, K: int, n: int = 6, N: int = 45) -> float:
    """초기하분포: N개 중 K개가 '해당'일 때, n개 추출에서 k개가 해당될 확률."""
    return comb(K, k) * comb(N - K, n - k) / comb(N, n)


# ───────────────────────── 헤더 ─────────────────────────
st.title("🎱 로또 6/45 통계")
st.caption(f"1회(2002-12-07) ~ {latest.draw_no}회({latest.draw_date}) · 총 {len(draw):,}회차 · "
           "매주 일요일 오전 자동 갱신")

c1, c2 = st.columns([3, 2])
with c1:
    st.markdown(f"**최신 {latest.draw_no}회 당첨번호** ({latest.draw_date})")
    st.markdown(balls_html(latest[NUMS], latest.bonus, 52), unsafe_allow_html=True)
with c2:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"번호 합계 · {latest_stats.sum_zone}", int(latest["sum"]))
    m2.metric("1등 당첨자", f"{int(latest.first_winners)}명")
    m3.metric("1등 1인당", f"{latest.first_prize_each / 1e8:.1f}억원")

st.info("과거 통계일 뿐, 다음 회차 당첨 확률과는 무관합니다. 매 회차 추첨은 서로 독립입니다.", icon="ℹ️")

tabs = st.tabs(["📈 합계 정상 범위", "🔢 번호 빈도", "⏳ 미출현 기간", "🧩 패턴", "🎯 내 번호로 과거 확인", "🔍 회차 조회"])

# ───────────────────────── 1. 합계 정상 범위 ─────────────────────────
with tabs[0]:
    st.subheader("당첨번호 합계는 종 모양(정규분포)에 가깝게 모입니다")
    in1 = (stats.sum_zone == "1σ 이내").mean()
    st.markdown(
        f"합계는 이론상 평균 **138**, 표준편차 **약 30**입니다. 이론상 약 68%가 108~168(±1σ)에 들어오고, "
        f"실제 비율은 **{in1:.1%}**. 다만 매 회차는 독립이라, 지난 합계로 다음 합계를 예측할 수는 없습니다.")

    n_recent = st.select_slider("표시할 최근 회차 수", options=[30, 52, 100, 200, 500, len(stats)],
                                value=100, format_func=lambda v: "전체" if v == len(stats) else f"{v}회")
    s = stats.tail(n_recent)
    x0, x1 = s.draw_no.min() - 0.5, s.draw_no.max() + 0.5
    fig = go.Figure()
    for lo, hi, col, name in [(SUM_MEAN - 2 * SUM_SD, SUM_MEAN + 2 * SUM_SD, BAND2, "±2σ (78~198)"),
                              (SUM_MEAN - SUM_SD, SUM_MEAN + SUM_SD, BAND1, "±1σ (108~168)")]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=lo, y1=hi, fillcolor=col, line_width=0, layer="below")
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=12, color=col, symbol="square"),
                                 name=name, hoverinfo="skip"))
    fig.add_hline(y=SUM_MEAN, line=dict(color=GRAY, width=1, dash="dot"))
    fig.add_trace(go.Scatter(x=s.draw_no, y=s["sum"], mode="lines+markers", name="회차별 합계",
                             line=dict(color=BLUE, width=2), marker=dict(size=5),
                             customdata=s[["draw_date", "sum_zone"]],
                             hovertemplate="%{x}회 (%{customdata[0]})<br>합계 %{y} · %{customdata[1]}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[latest.draw_no], y=[latest["sum"]], mode="markers", name=f"최신 {latest.draw_no}회",
                             marker=dict(size=11, color=ORANGE, line=dict(color="white", width=2)), hoverinfo="skip"))
    fig.update_layout(hovermode="closest")
    st.plotly_chart(base_layout(fig, 380, "합계", "회차"), use_container_width=True)

    # 이론 분포 vs 실제 히스토그램
    st.markdown("**전 회차 합계 분포: 실제(막대) vs 이론 정규분포(선)**")
    bw = 5
    edges = list(range(20, 261, bw))
    cnt = pd.cut(stats["sum"], edges, right=False).value_counts().sort_index()
    mids = [e + bw / 2 for e in edges[:-1]]
    pdf = [len(stats) * bw * exp(-((m - SUM_MEAN) ** 2) / (2 * SUM_SD ** 2)) / (SUM_SD * sqrt(2 * pi)) for m in mids]
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=mids, y=cnt.values, name="실제 회차 수", marker=dict(color=BLUE, cornerradius=4),
                          customdata=[f"{e}~{e + bw - 1}" for e in edges[:-1]],
                          hovertemplate="합계 %{customdata}: %{y}회<extra></extra>"))
    fig2.add_trace(go.Scatter(x=mids, y=pdf, name="이론값", mode="lines", line=dict(color=GRAY, width=2),
                              hovertemplate="이론 %{y:.1f}회<extra></extra>"))
    fig2.update_layout(bargap=0.08)
    st.plotly_chart(base_layout(fig2, 320, "회차 수", "번호 합계"), use_container_width=True)

    z1, z2, z3 = st.columns(3)
    for col, zone, label in [(z1, "1σ 이내", "108~168"), (z2, "1~2σ", "78~107 · 169~198"), (z3, "2σ 초과", "77 이하 · 199 이상")]:
        n = int((stats.sum_zone == zone).sum())
        col.metric(f"{zone} ({label})", f"{n:,}회 · {n / len(stats):.1%}")

# ───────────────────────── 2. 번호 빈도 ─────────────────────────
with tabs[1]:
    st.subheader("번호별 출현 횟수")
    period = st.radio("기간", ["전체", "최근 20회", "최근 10회", "최근 5회"], horizontal=True)
    col = {"전체": "total_count", "최근 20회": "recent20_count", "최근 10회": "recent10_count",
           "최근 5회": "recent5_count"}[period]
    w = {"전체": len(draw), "최근 20회": 20, "최근 10회": 10, "최근 5회": 5}[period]
    expected = w * 6 / 45
    fig = go.Figure(go.Bar(x=status.number, y=status[col], marker=dict(color=BLUE, cornerradius=4),
                           name="출현 횟수", hovertemplate="%{x}번: %{y}회<extra></extra>"))
    fig.add_hline(y=expected, line=dict(color=GRAY, width=1.5, dash="dash"),
                  annotation_text=f"기대값 {expected:.1f}회", annotation_position="top left")
    fig.update_xaxes(dtick=1)
    fig.update_layout(hovermode="closest")
    st.plotly_chart(base_layout(fig, 360, "출현 횟수", "번호"), use_container_width=True)

    top = status.sort_values([col, "number"], ascending=[False, True]).head(6)
    bot = status.sort_values([col, "number"], ascending=[True, True]).head(6)
    a, b = st.columns(2)
    a.markdown(f"**🔥 많이 나온 번호 ({period})**")
    a.markdown(balls_html(top.number), unsafe_allow_html=True)
    a.caption(" · ".join(f"{n}번 {c}회" for n, c in zip(top.number, top[col])))
    b.markdown(f"**🧊 적게 나온 번호 ({period})**")
    b.markdown(balls_html(bot.number), unsafe_allow_html=True)
    b.caption(" · ".join(f"{n}번 {c}회" for n, c in zip(bot.number, bot[col])))
    if w <= 20:
        st.caption(f"최근 {w}회는 번호 {w * 6}개뿐이라, 이 정도 차이는 대부분 우연으로 생깁니다.")

# ───────────────────────── 3. 미출현 기간 ─────────────────────────
with tabs[2]:
    st.subheader("각 번호가 몇 회째 나오지 않고 있는지")
    st.markdown("막대는 **마지막 출현 이후 지난 회차 수**, 점은 그 번호의 **평균 출현 간격**입니다. "
                "막대가 점보다 길면 평소보다 오래 쉬고 있는 번호입니다. 그렇다고 곧 나온다는 뜻은 아닙니다.")
    g = status.sort_values(["gap_now", "number"], ascending=[False, True])
    labels = [f"{n}번" for n in g.number]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=g.gap_now, name="현재 미출현 회차", marker=dict(color=BLUE, cornerradius=4),
                         customdata=g[["last_seen_draw", "max_gap"]],
                         hovertemplate="%{x}: %{y}회째 미출현<br>마지막 출현 %{customdata[0]}회 · 최장 %{customdata[1]}회<extra></extra>"))
    fig.add_trace(go.Scatter(x=labels, y=g.avg_gap, mode="markers", name="평균 출현 간격",
                             marker=dict(size=9, color=ORANGE, line=dict(color="white", width=1.5)),
                             hovertemplate="평균 간격 %{y:.1f}회<extra></extra>"))
    fig.update_layout(hovermode="closest")
    st.plotly_chart(base_layout(fig, 380, "회차 수"), use_container_width=True)
    lead = g.iloc[0]
    st.caption(f"현재 가장 오래 쉬고 있는 번호는 **{lead.number}번**으로 {lead.gap_now}회째입니다 "
               f"(평균 간격 {lead.avg_gap:.1f}회, 역대 최장 {int(lead.max_gap)}회).")

# ───────────────────────── 4. 패턴 ─────────────────────────
with tabs[3]:
    st.subheader("당첨번호 패턴: 실제 비율 vs 이론 확률")
    st.caption("이론 확률은 1~45에서 6개를 무작위로 뽑을 때의 값(초기하분포)입니다. 두 막대가 비슷하면 '무작위답게' 나오고 있다는 뜻입니다.")

    def compare_chart(series: pd.Series, theory: dict, x_title: str):
        actual = series.value_counts(normalize=True).reindex(list(theory), fill_value=0)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(theory), y=actual.values * 100, name="실제", marker=dict(color=BLUE, cornerradius=4),
                             hovertemplate="%{x}개: 실제 %{y:.1f}%<extra></extra>"))
        fig.add_trace(go.Bar(x=list(theory), y=[v * 100 for v in theory.values()], name="이론",
                             marker=dict(color=GRAY, cornerradius=4), hovertemplate="%{x}개: 이론 %{y:.1f}%<extra></extra>"))
        fig.update_layout(barmode="group", hovermode="closest")
        fig.update_xaxes(dtick=1)
        return base_layout(fig, 280, "비율(%)", x_title)

    p1, p2 = st.columns(2)
    with p1:
        st.markdown("**홀수 개수** (1~45 중 홀수 23개)")
        st.plotly_chart(compare_chart(stats.odd_cnt, {k: hyper(k, 23) for k in range(7)}, "홀수 개수"),
                        use_container_width=True)
    with p2:
        st.markdown("**저번호(1~22) 개수**")
        st.plotly_chart(compare_chart(stats.low_cnt, {k: hyper(k, 22) for k in range(7)}, "저번호 개수"),
                        use_container_width=True)
    p3, p4 = st.columns(2)
    with p3:
        st.markdown("**이월수: 직전 회차 번호가 다시 나온 개수**")
        st.plotly_chart(compare_chart(stats.carryover_cnt.dropna().astype(int), {k: hyper(k, 6) for k in range(4)},
                                      "이월 개수"), use_container_width=True)
    with p4:
        st.markdown("**연속번호 쌍 수** (예: 12·13 → 1쌍)")
        vc = stats.consecutive_pairs.value_counts(normalize=True).sort_index()
        fig = go.Figure(go.Bar(x=vc.index, y=vc.values * 100, marker=dict(color=BLUE, cornerradius=4), name="실제",
                               hovertemplate="%{x}쌍: %{y:.1f}%<extra></extra>"))
        fig.update_xaxes(dtick=1)
        fig.update_layout(hovermode="closest")
        st.plotly_chart(base_layout(fig, 280, "비율(%)", "연속 쌍 수"), use_container_width=True)
    no_consec = comb(40, 6) / comb(45, 6)
    st.caption(f"연속번호가 1쌍 이상 나온 회차: 실제 {(stats.consecutive_pairs > 0).mean():.1%} · 이론 {1 - no_consec:.1%}")

# ───────────────────────── 5. 내 번호로 과거 확인 ─────────────────────────
with tabs[4]:
    st.subheader("내 번호를 1회부터 매주 샀다면?")
    mine = st.multiselect("번호 6개를 고르세요", list(range(1, 46)), max_selections=6, placeholder="예: 3, 11, 19, 27, 34, 42")
    if len(mine) == 6:
        mine_set = set(mine)
        match = draw[NUMS].apply(lambda r: len(mine_set & set(r)), axis=1)
        bonus_hit = draw.bonus.isin(mine_set)
        rank = pd.Series("낙첨", index=draw.index)
        rank[match == 3] = "5등"
        rank[match == 4] = "4등"
        rank[match == 5] = "3등"
        rank[(match == 5) & bonus_hit] = "2등"
        rank[match == 6] = "1등"
        order = ["1등", "2등", "3등", "4등", "5등"]
        counts = rank.value_counts().reindex(order, fill_value=0)
        st.markdown(balls_html(sorted(mine)), unsafe_allow_html=True)
        cols = st.columns(5)
        for c, r in zip(cols, order):
            c.metric(r, f"{counts[r]}회")
        spent = len(draw) * 1000
        st.caption(f"{len(draw):,}회 × 1,000원 = {spent:,}원을 썼을 때의 결과입니다. "
                   "4·5등은 고정 금액, 1~3등은 회차마다 금액이 다릅니다.")
        hits = draw[rank.isin(order[:4])].assign(등수=rank[rank.isin(order[:4])])
        if len(hits):
            st.markdown("**4등 이상 당첨 회차**")
            st.dataframe(hits[["draw_no", "draw_date", "등수"] + NUMS + ["bonus"]].rename(
                columns={"draw_no": "회차", "draw_date": "추첨일", "bonus": "보너스", **NUM_LABELS}),
                hide_index=True, use_container_width=True)
    else:
        st.caption(f"{len(mine)}/6개 선택됨")

# ───────────────────────── 6. 회차 조회 ─────────────────────────
with tabs[5]:
    st.subheader("회차별 당첨번호")
    sel = st.number_input("회차", min_value=1, max_value=int(latest.draw_no), value=int(latest.draw_no), step=1)
    r = draw[draw.draw_no == sel].iloc[0]
    rs = stats[stats.draw_no == sel].iloc[0]
    st.markdown(f"**{r.draw_no}회** ({r.draw_date})")
    st.markdown(balls_html(r[NUMS], r.bonus), unsafe_allow_html=True)
    i1, i2, i3, i4 = st.columns(4)
    i1.metric(f"합계 · {rs.sum_zone}", int(r["sum"]))
    i2.metric("홀:짝", f"{rs.odd_cnt}:{rs.even_cnt}")
    i3.metric("1등 당첨자", f"{int(r.first_winners)}명")
    i4.metric("1등 1인당", f"{r.first_prize_each / 1e8:.1f}억원" if r.first_prize_each else "-")

    st.markdown("**최근 20회**")
    recent = draw.tail(20).iloc[::-1][["draw_no", "draw_date"] + NUMS + ["bonus", "sum", "first_winners"]]
    st.dataframe(recent.rename(columns={"draw_no": "회차", "draw_date": "추첨일", "bonus": "보너스", "sum": "합계",
                                        "first_winners": "1등(명)", **NUM_LABELS}), hide_index=True, use_container_width=True)

st.divider()
st.caption("데이터 출처: 동행복권 추첨결과 · 매주 일요일 자동 수집 · 본 페이지는 오락·통계 목적이며 구매를 권유하지 않습니다.")
