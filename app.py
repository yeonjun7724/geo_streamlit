import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="하남시 MAT 기반 아파트 네비게이션",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# Secrets / Tokens
# ──────────────────────────────────────────────────────────────────────────────
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")
if not MAPBOX_TOKEN:
    st.warning("Mapbox 토큰(MAPBOX_TOKEN)이 설정되지 않았습니다. Settings → Secrets 또는 환경변수로 설정하세요.")

# ──────────────────────────────────────────────────────────────────────────────
# 하드코딩 좌표 (실사용을 위한 안정 버전)
#  - ORIGINS: 출발지(예: 소방서/안전센터)
#  - APARTMENTS: 각 아파트의 정문(gate), 건물 앞(front), 센터(center) 좌표
#  좌표는 WGS84 (lat, lon)
# ──────────────────────────────────────────────────────────────────────────────
ORIGINS = {
    "하남소방서": [37.539233, 127.214076],           # 하남시 신장로 53 인근
    "미사강변119안전센터": [37.563741, 127.191403],  # 미사강변동로 95 인근
}

APARTMENTS = {
    "미사강변 한강센트럴파크": {
        "center": [37.562100, 127.173400],
        "gate":   [37.561900, 127.173200],   # 단지 정문 근사값
        "front":  [37.562650, 127.173900],   # 101동 전면 근사값
    },
    "미사강변 신리마을": {
        "center": [37.564500, 127.168900],
        "gate":   [37.564300, 127.168700],
        "front":  [37.564800, 127.169200],   # 201동 전면 근사값
    },
    "고덕 래미안": {
        "center": [37.549800, 127.154200],
        "gate":   [37.549600, 127.154000],
        "front":  [37.550050, 127.154500],   # 301동 전면 근사값
    },
    "고덕 그라시움": {
        "center": [37.552100, 127.157800],
        "gate":   [37.551900, 127.157600],
        "front":  [37.552300, 127.158050],   # 401동 전면 근사값
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers (routing)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def mapbox_route(points_latlon, profile="driving"):
    """Mapbox Directions API → (경로좌표, 거리(km), 시간(분), 마지막노드(lat,lon))"""
    if not MAPBOX_TOKEN:
        return [], None, None, None
    coords = ";".join([f"{lon},{lat}" for lat, lon in points_latlon])
    url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coords}"
    params = {
        "geometries": "geojson",
        "overview": "full",
        "access_token": MAPBOX_TOKEN,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("routes"):
            return [], None, None, None
        route = data["routes"][0]
        line = route["geometry"]["coordinates"]  # [[lon,lat],...]
        coords_latlon = [[lat, lon] for lon, lat in line]
        end_latlon = coords_latlon[-1] if coords_latlon else None
        distance_km = route.get("distance", 0) / 1000.0
        duration_min = route.get("duration", 0) / 60.0
        return coords_latlon, distance_km, duration_min, end_latlon
    except Exception:
        return [], None, None, None


def add_mapbox_tile(m: folium.Map, style="mapbox/streets-v12"):
    if not MAPBOX_TOKEN:
        return m
    tile_url = f"https://api.mapbox.com/styles/v1/{style}/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={MAPBOX_TOKEN}"
    folium.TileLayer(tiles=tile_url, attr="Mapbox", name="Mapbox", control=False).add_to(m)
    return m

# ──────────────────────────────────────────────────────────────────────────────
# Header & Controls (상단 심플 레이아웃)
# ──────────────────────────────────────────────────────────────────────────────
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")

ctrl = st.container()
with ctrl:
    c1, c2, c3 = st.columns([2, 2, 1])
    origin_name = c1.selectbox("출발지", list(ORIGINS.keys()), index=0)
    apartment_name = c2.selectbox("아파트 단지", list(APARTMENTS.keys()), index=0)
    refresh = c3.button("경로 갱신", use_container_width=True)

# 데이터 해석
origin = ORIGINS[origin_name]
apt = APARTMENTS[apartment_name]
apt_gate = apt["gate"]
apt_front = apt["front"]
center_hint = apt["center"]

# 경로 계산 (AS-IS & TO-BE)
# AS-IS: 차량(출발지→정문) + 도보(정문→아파트 앞)
drv1_coords, drv1_km, drv1_min, _ = mapbox_route([origin, apt_gate], profile="driving")
walk1_coords, walk1_km, walk1_min, _ = mapbox_route([apt_gate, apt_front], profile="walking")
# TO-BE: 차량(출발지→아파트 앞)
drv2_coords, drv2_km, drv2_min, _ = mapbox_route([origin, apt_front], profile="driving")

# KPI Row (상단)
kpi = st.container()
with kpi:
    k1, k2, k3, k4 = st.columns(4)
    # 안전 처리
    asis_drive = (drv1_min or 0)
    asis_walk = (walk1_min or 0)
    tobe_drive = (drv2_min or 0)
    asis_total = asis_drive + asis_walk
    improvement_min = asis_total - tobe_drive
    improvement_pct = (improvement_min / asis_total * 100) if asis_total > 0 else 0

    k1.metric("AS-IS 차량", f"{asis_drive:.2f}분", help="출발지→정문, driving")
    k2.metric("AS-IS 도보", f"{asis_walk:.2f}분", help="정문→아파트 앞, walking")
    k3.metric("TO-BE 차량", f"{tobe_drive:.2f}분", help="출발지→아파트 앞, driving")
    k4.metric("총 개선", f"{improvement_min:.2f}분", f"{improvement_pct:.1f}%", help="AS-IS(차+도보) 대비 TO-BE(차량)")

# 지도 (하단 하나의 심플 지도에 모든 경로 오버레이)
map_area = st.container()
with map_area:
    m = folium.Map(location=center_hint, zoom_start=16)
    add_mapbox_tile(m)

    # 마커
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m)
    folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m)

    # 경로: AS-IS(차량: 파랑, 도보: 초록 점선) / TO-BE(차량: 보라)
    if drv1_coords:
        folium.PolyLine(drv1_coords, color="#1f77b4", weight=4, opacity=0.9, popup="AS-IS 차량").add_to(m)
    if walk1_coords:
        folium.PolyLine(walk1_coords, color="#2ca02c", weight=4, opacity=0.9, dash_array="6,8", popup="AS-IS 도보").add_to(m)
    if drv2_coords:
        folium.PolyLine(drv2_coords, color="#9467bd", weight=5, opacity=0.95, popup="TO-BE 차량").add_to(m)

    # 간단한 범례
    legend_html = """
    <div style="position: fixed; bottom: 18px; left: 18px; background: white; border:1px solid #ddd; padding:8px 10px; z-index:9999; font-size:13px;">
      <div><span style='display:inline-block;width:12px;height:3px;background:#1f77b4;margin-right:6px'></span>AS-IS 차량</div>
      <div><span style='display:inline-block;width:12px;height:3px;background:#2ca02c;margin-right:6px;border-bottom:2px dashed #2ca02c'></span>AS-IS 도보</div>
      <div><span style='display:inline-block;width:12px;height:3px;background:#9467bd;margin-right:6px'></span>TO-BE 차량</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, use_container_width=True, height=520)

# 하단 테이블(선택)
result_df = pd.DataFrame([
    {"구분": "AS-IS 차량", "거리(km)": round(drv1_km or 0, 2), "시간(분)": round(drv1_min or 0, 2)},
    {"구분": "AS-IS 도보", "거리(km)": round(walk1_km or 0, 2), "시간(분)": round(walk1_min or 0, 2)},
    {"구분": "TO-BE 차량", "거리(km)": round(drv2_km or 0, 2), "시간(분)": round(drv2_min or 0, 2)},
])
st.dataframe(result_df, use_container_width=True)

st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d')} | 데이터 소스: Mapbox Directions API (driving + walking)")
