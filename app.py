# -*- coding: utf-8 -*-
"""
서울특별시 종로구 공공시설 태양광 설치현황 대시보드
Data source: 공공데이터포털 (기준일자 2021-04-23)
Run: streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="종로구 공공시설 태양광 설치현황",
    page_icon="☀️",
    layout="wide",
)

CSV_PATH = "서울특별시 종로구_공공시설_태양광_설치현황_20210423.csv"


# ------------------------------------------------------------------
# 데이터 로드 / 전처리
# ------------------------------------------------------------------
@st.cache_data
def load_data(path: str = CSV_PATH) -> pd.DataFrame:
    # 원본 인코딩이 utf-8 이지만 환경에 따라 cp949 도 대비
    for enc in ("utf-8", "utf-8-sig", "cp949"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    df = df.rename(columns={"설치용량(킬로와트)": "설치용량_kW"})
    df["설치년도"] = df["설치년도"].astype(int)

    def categorize(name: str) -> str:
        n = str(name)
        if "주민센터" in n or "자치회관" in n or "청사" in n:
            return "행정시설"
        if "복지관" in n or "경로당" in n or "복지센터" in n:
            return "복지시설"
        if "어린이집" in n or "육아" in n:
            return "보육시설"
        if "공원" in n or "화장실" in n:
            return "공원/편의시설"
        if "주차" in n:
            return "주차시설"
        if "문화" in n or "체육" in n or "구민회관" in n:
            return "문화·체육시설"
        return "기타 공공시설"

    df["시설유형"] = df["시설명"].apply(categorize)

    # 행정동(법정동) 추출: 도로명 주소의 괄호 안 → 실패 시 지번주소 첫 토큰
    df["행정동"] = df["도로명 주소"].str.extract(r"\(([^)]+)\)")
    fallback = df["지번 주소"].str.extract(r"종로구\s+([^\s]+)")[0]
    df["행정동"] = df["행정동"].fillna(fallback)
    return df


df = load_data()

# ------------------------------------------------------------------
# 사이드바 필터
# ------------------------------------------------------------------
st.sidebar.header("필터")
years = sorted(df["설치년도"].unique())
year_sel = st.sidebar.select_slider(
    "설치년도 범위",
    options=years,
    value=(min(years), max(years)),
)
types_all = sorted(df["시설유형"].unique())
type_sel = st.sidebar.multiselect("시설유형", types_all, default=types_all)

fdf = df[
    (df["설치년도"].between(year_sel[0], year_sel[1]))
    & (df["시설유형"].isin(type_sel))
].copy()

# ------------------------------------------------------------------
# 헤더
# ------------------------------------------------------------------
st.title("☀️ 종로구 공공시설 태양광 설치현황")
st.caption("기준일자 2021-04-23 · 출처: 서울특별시 종로구 공공데이터")

# KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 시설 수", f"{len(fdf):,} 개")
c2.metric("총 설치용량", f"{fdf['설치용량_kW'].sum():,.2f} kW")
c3.metric("평균 용량", f"{fdf['설치용량_kW'].mean():,.2f} kW" if len(fdf) else "-")
c4.metric("설치기간", f"{fdf['설치년도'].min()} ~ {fdf['설치년도'].max()}" if len(fdf) else "-")

st.divider()

# ------------------------------------------------------------------
# 1행: 시설유형별 / 연도별
# ------------------------------------------------------------------
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("시설유형별 설치용량")
    g = (
        fdf.groupby("시설유형")
        .agg(건수=("시설명", "count"), 총용량=("설치용량_kW", "sum"))
        .reset_index()
        .sort_values("총용량", ascending=True)
    )
    fig = px.bar(
        g,
        x="총용량",
        y="시설유형",
        orientation="h",
        text="총용량",
        hover_data={"건수": True, "총용량": ":.2f"},
        color="총용량",
        color_continuous_scale="Blues",
    )
    fig.update_traces(texttemplate="%{text:.1f} kW", textposition="outside")
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False, xaxis_title="설치용량 (kW)", yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.subheader("연도별 설치 추이")
    g = (
        fdf.groupby("설치년도")
        .agg(건수=("시설명", "count"), 총용량=("설치용량_kW", "sum"))
        .reset_index()
        .sort_values("설치년도")
    )
    g["누적용량"] = g["총용량"].cumsum()
    fig = go.Figure()
    fig.add_bar(x=g["설치년도"], y=g["총용량"], name="연도별 용량(kW)",
                marker_color="#60a5fa",
                text=g["건수"].astype(str) + "건", textposition="outside")
    fig.add_scatter(x=g["설치년도"], y=g["누적용량"], name="누적 용량(kW)",
                    mode="lines+markers", line=dict(color="#1d4ed8", width=3))
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="설치년도", yaxis_title="설치용량 (kW)",
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# 2행: 동별 / 용량 분포
# ------------------------------------------------------------------
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("행정동별 설치용량 Top")
    g = (
        fdf.groupby("행정동")
        .agg(건수=("시설명", "count"), 총용량=("설치용량_kW", "sum"))
        .reset_index()
        .sort_values("총용량", ascending=False)
        .head(12)
    )
    fig = px.bar(
        g.sort_values("총용량"),
        x="총용량", y="행정동", orientation="h",
        text="건수", color="총용량", color_continuous_scale="Teal",
        hover_data={"건수": True, "총용량": ":.2f"},
    )
    fig.update_traces(texttemplate="%{text}건", textposition="outside")
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=False, xaxis_title="설치용량 (kW)", yaxis_title="",
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.subheader("시설별 설치용량 분포")
    fig = px.box(
        fdf, x="시설유형", y="설치용량_kW", points="all",
        hover_data=["시설명", "설치년도", "행정동"],
        color="시설유형",
    )
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False, xaxis_title="", yaxis_title="설치용량 (kW)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# 3행: Top 시설 랭킹
# ------------------------------------------------------------------
st.subheader("설치용량 상위 시설 Top 10")
top = fdf.sort_values("설치용량_kW", ascending=False).head(10)
fig = px.bar(
    top.sort_values("설치용량_kW"),
    x="설치용량_kW", y="시설명", orientation="h",
    color="시설유형", text="설치용량_kW",
    hover_data=["설치년도", "행정동"],
)
fig.update_traces(texttemplate="%{text:.2f} kW", textposition="outside")
fig.update_layout(
    height=460, margin=dict(l=10, r=10, t=10, b=10),
    xaxis_title="설치용량 (kW)", yaxis_title="",
    legend=dict(orientation="h", y=-0.15),
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# 인사이트
# ------------------------------------------------------------------
st.divider()
st.subheader("데이터 인사이트")
total_cap = df["설치용량_kW"].sum()
top_type = df.groupby("시설유형")["설치용량_kW"].sum().idxmax()
top_type_cap = df.groupby("시설유형")["설치용량_kW"].sum().max()
top_year = df.groupby("설치년도")["설치용량_kW"].sum().idxmax()
top_year_cap = df.groupby("설치년도")["설치용량_kW"].sum().max()
top_dong = df.groupby("행정동")["설치용량_kW"].sum().idxmax()
top_facility = df.loc[df["설치용량_kW"].idxmax()]

st.markdown(
    f"""
- **총 22개 공공시설 · 누적 {total_cap:.2f} kW** 규모의 태양광이 종로구 관내에 설치되어 있습니다 (기준 2021-04-23).
- 시설유형 중 **{top_type}** 이 {top_type_cap:.2f} kW 로 가장 큰 비중을 차지합니다.
- 설치 피크 연도는 **{top_year}년 ({top_year_cap:.2f} kW)** 이며, 2009년(초기 보급)과 2015~2018년(2차 확대) 두 구간에 집중되어 있습니다.
- 행정동 기준으로는 **{top_dong}** 이 가장 많은 용량을 보유하고 있습니다.
- 개별 시설 최대 용량은 **{top_facility['시설명']} ({top_facility['설치용량_kW']:.2f} kW, {top_facility['설치년도']}년)** 입니다.
- 소규모(≤5 kW) 시설이 다수를 차지하지만, 복지관·주민센터급에서 20 kW 이상 중형 설비가 총 용량을 견인하고 있습니다.
"""
)

# ------------------------------------------------------------------
# 원본 테이블
# ------------------------------------------------------------------
with st.expander("원본 데이터 보기"):
    st.dataframe(fdf.reset_index(drop=True), use_container_width=True)
    st.download_button(
        "필터 결과 CSV 다운로드",
        data=fdf.to_csv(index=False).encode("utf-8-sig"),
        file_name="jongno_solar_filtered.csv",
        mime="text/csv",
    )
