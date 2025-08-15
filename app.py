import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime
from folium.plugins import AntPath

# ── 페이지 기본 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="하남시 MAT 기반 아파트 네비게이션", page_icon="🏢", layout="wide")

# ── 전역 스타일 (카드 X, 미니멀/정렬만) ───────────────────────────────────────────
st.markdown("""
<style>
:root { --muted:#6b7280; --text:#111827; }
html, body, [data-testid="stAppViewContainer"] { color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main > div { padding-top: 0.6rem !important; }

/* 전체 레이아웃: 화면을 넓게 쓰되 과도하게 길지 않게 */
.block-container {
    max-width: 1600px;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    margin: 0 auto;
}

/* 제목 크게, 중앙 정렬 */
.app-title {
    font-size: 3.2rem; font-weight: 900; letter-spacing: -0.02em;
    margin: 0.2rem 0 0.8rem 0; text-align: center;
}
.app-sub {
    color: var(--muted); font-size: 1.05rem; margin-bottom: 1.6rem;
    text-align: center;
}

/* 섹션 간 여백 */
.section { margin: 1.8rem 0; }

/* KPI 정렬 */
[data-testid="stMetric"] {
    text-align: center;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-weight: 600; }
[data-testid="stMetricValue"]  { color: var(--text) !important; }

/* 소제목 정렬 */
h4 { text-align: center; margin-bottom: 0.6rem; }

/* 지도 attribution 간소화 */
.leaflet-control-attribution { display: none; }

/* 얇은 구분선 */
.divider {
    height: 1px; background: #e5e7eb; margin: 1.4rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Mapbox 토큰(미사용, 기존 코드 호환만) ────────────────────────────────────────
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")

# ── 데이터 ──────────────────────────────────────────────────────────────────────
ORIGINS = {
    "하남소방서": [37.539826, 127.220661],
    "미사강변119안전센터": [37.566902, 127.185298],
}
APARTMENTS = {
    "미사강변센트럴풍경채": {
        "center": [37.556591, 127.183081],
        "gate":   [37.556844, 127.181887],
        "front":  [37.557088, 127.183036],
    },
    "미사강변 푸르지오": {
        "center": [37.564925, 127.184055],
        "gate":   [37.565196, 127.182840],
        "front":  [37.566168, 127.182795],
    },
}

# ── 라우팅 함수 (기능 로직 그대로) ───────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def mapbox_route(points_latlon, profile="driving"):
    if not MAPBOX_TOKEN:
        return [], None, None, None
    coords = ";".join([f"{lon},{lat}" for lat, lon in points_latlon])
    url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coords}"
    params = {"geometries": "geojson", "overview": "full", "access_token": MAPBOX_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("routes"):
            return [], None, None, None
        route = data["routes"][0]
        line = route["geometry"]["coordinates"]
        coords_latlon = [[lat, lon] for lon, lat in line]
        end_latlon = coords_latlon[-1] if coords_latlon else None
        distance_km = route.get("distance", 0) / 1000.0
        duration_min = route.get("duration", 0) / 60.0
        return coords_latlon, distance_km, duration_min, end_latlon
    except Exception:
        return [], None, None, None

# ── CARTO 타일 적용 ─────────────────────────────────────────────────────────────
def add_carto_tile(m: folium.Map, theme="positron"):
    """
    theme: 'positron' | 'dark_matter'
    """
    if theme == "dark_matter":
        folium.TileLayer(tiles="CartoDB Dark_Matter", control=False).add_to(m)
    else:
        folium.TileLayer(tiles="CartoDB Positron", control=False).add_to(m)
    return m

def add_legend(m: folium.Map):
    legend_html = """
    <div style="
        position: fixed; bottom: 28px; left: 28px; width: 190px;
        background: rgba(255,255,255,0.95); z-index:9999; font-size:14px;
        border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px;">
      <div style="font-weight:700; margin-bottom:6px;">경로 범례</div>
      <div><span style="color:#1f77b4;">━</span> AS-IS 차량</div>
      <div><span style="color:#2ca02c;">━</span> AS-IS 도보</div>
      <div><span style="color:#9467bd;">━</span> TO-BE 차량</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

# ── 제목 ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">🏢 하남시 MAT 기반 아파트 네비게이션</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">출발지와 단지를 선택하면 AS-IS/TO-BE 경로와 소요시간을 비교합니다.</div>', unsafe_allow_html=True)

# ── 컨트롤(가운데 정렬, 균형 배치) ──────────────────────────────────────────────
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    origin_name = st.selectbox("출발지", list(ORIGINS.keys()), index=0)
with c2:
    apartment_name = st.selectbox("아파트 단지", list(APARTMENTS.keys()), index=0)
with c3:
    st.write("")  # 균형용 공간

# ── 경로 계산 ────────────────────────────────────────────────────────────────────
origin = ORIGINS[origin_name]
apt = APARTMENTS[apartment_name]
apt_gate, apt_front, center_hint = apt["gate"], apt["front"], apt["center"]

drv1_coords, drv1_km, drv1_min, _ = mapbox_route([origin, apt_gate], profile="driving")
walk1_coords, walk1_km, walk1_min, _ = mapbox_route([apt_gate, apt_front], profile="walking")
drv2_coords, drv2_km, drv2_min, _ = mapbox_route([origin, apt_front], profile="driving")

asis_total = (drv1_min or 0) + (walk1_min or 0)
improvement_min = asis_total - (drv2_min or 0)
improvement_pct = (improvement_min / asis_total * 100) if asis_total > 0 else 0

# ── KPI (가운데 정렬, 균형) ─────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
k1.metric("AS-IS 차량", f"{(drv1_min or 0):.2f}분")
k2.metric("AS-IS 도보", f"{(walk1_min or 0):.2f}분")
k3.metric("TO-BE 차량", f"{(drv2_min or 0):.2f}분")
k4.metric("총 개선", f"{improvement_min:.2f}분", f"{improvement_pct:.1f}%")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 지도(2분할, CARTO 타일, 부드러운 경로) ─────────────────────────────────────
map_height = 640  # 화면 비율 고려 적정 높이
left, right = st.columns([1, 1])

with left:
    st.markdown("#### 🚗 AS-IS — 정문까지 차량 + 잔여 도보")
    m1 = folium.Map(location=center_hint, zoom_start=17, control_scale=True, zoom_control=True)
    add_carto_tile(m1, theme="positron")
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
    folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m1)
    if drv1_coords:
        AntPath(drv1_coords, color="#1f77b4", weight=5, opacity=0.9, delay=800).add_to(m1)
    if walk1_coords:
        AntPath(walk1_coords, color="#2ca02c", weight=5, opacity=0.9, dash_array=[6, 8], delay=900).add_to(m1)
    add_legend(m1)
    st_folium(m1, use_container_width=True, height=map_height)

with right:
    st.markdown("#### ✅ TO-BE — 아파트 앞까지 차량")
    m2 = folium.Map(location=center_hint, zoom_start=17, control_scale=True, zoom_control=True)
    add_carto_tile(m2, theme="positron")
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m2)
    if drv2_coords:
        AntPath(drv2_coords, color="#9467bd", weight=6, opacity=0.95, delay=800).add_to(m2)
    add_legend(m2)
    st_folium(m2, use_container_width=True, height=map_height)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 결과 표 (중앙, 가독성 중심) ─────────────────────────────────────────────────
result_df = pd.DataFrame([
    {"구분": "AS-IS 차량", "거리(km)": round(drv1_km or 0, 2), "시간(분)": round(drv1_min or 0, 2)},
    {"구분": "AS-IS 도보", "거리(km)": round(walk1_km or 0, 2), "시간(분)": round(walk1_min or 0, 2)},
    {"구분": "TO-BE 차량", "거리(km)": round(drv2_km or 0, 2), "시간(분)": round(drv2_min or 0, 2)},
])
st.dataframe(result_df, use_container_width=True, hide_index=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 골든타임·생존 인원 분석 (입력 가능) ─────────────────────────────────────────
st.markdown("### 🚑 골든타임 영향 및 생존 인원 추정")
colA, colB, colC = st.columns([1, 1, 1])
with colA:
    golden_time = st.number_input("골든타임 기준(분)", min_value=1.0, max_value=15.0, value=4.0, step=0.5)
with colB:
    survival_gain_per_min = st.number_input("1분 단축 시 생존율 개선(%p)", min_value=0.0, max_value=20.0, value=8.0, step=0.5) / 100.0
with colC:
    annual_cases = st.number_input("연간 관련 출동 건수(건)", min_value=0, max_value=200000, value=12000, step=100)

time_ratio = (improvement_min / golden_time) if golden_time > 0 else 0
survival_increase_rate = survival_gain_per_min * max(improvement_min, 0)
saved_people = int(annual_cases * survival_increase_rate)

st.markdown(
    f"개선된 경로로 평균 이동 시간이 **{improvement_min:.2f}분** 단축되었다. "
    f"골든타임 **{golden_time:.1f}분** 대비 단축 비율은 **{(time_ratio*100):.1f}%**이다. "
    f"1분 단축당 생존율 개선을 **{survival_gain_per_min*100:.1f}%p**로 보았을 때, "
    f"연간 출동 **{annual_cases:,}건** 기준으로 추가 생존 가능 인원은 약 **{saved_people:,}명**으로 추정된다."
)

# ── 푸터 ─────────────────────────────────────────────────────────────────────────
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d')} · 지도: CARTO (Positron) · 경로: Mapbox Directions API, Folium AntPath")
