import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="하남시 MAT 기반 아파트 네비게이션", page_icon="🏢", layout="wide")

MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")

# 출발지와 아파트 단지 좌표
ORIGINS = {
    "하남소방서": [37.539826, 127.220661],
    "미사강변119안전센터": [37.566902, 127.185298],
}

APARTMENTS = {
    "미사강변센트럴풍경채": {
        "center": [37.556591, 127.183081],
        "gate": [37.556844, 127.181887],
        "front": [37.557088, 127.183036],
    },
    "미사강변 푸르지오": {
        "center": [37.564925, 127.184055],
        "gate": [37.565196, 127.182840],
        "front": [37.566168, 127.182795],
    },
}

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

# Mapbox 대신 CARTO 타일 적용
def add_carto_tile(m: folium.Map, style="light_all"):
    tile_url = f"https://cartodb-basemaps-a.global.ssl.fastly.net/{style}/{{z}}/{{x}}/{{y}}.png"
    folium.TileLayer(tiles=tile_url, attr="CARTO", name="CARTO", control=False).add_to(m)
    return m

# 제목
st.markdown("<h1 style='text-align:center; font-size:50px; font-weight:bold;'>🏢 하남시 MAT 기반 아파트 네비게이션</h1>", unsafe_allow_html=True)

# 출발지, 아파트 단지 선택 (전체 폭)
col1, col2 = st.columns([1, 1])
with col1:
    origin_name = st.selectbox("출발지", list(ORIGINS.keys()), index=0)
with col2:
    apartment_name = st.selectbox("아파트 단지", list(APARTMENTS.keys()), index=0)

origin = ORIGINS[origin_name]
apt = APARTMENTS[apartment_name]
apt_gate, apt_front, center_hint = apt["gate"], apt["front"], apt["center"]

# 경로 계산
drv1_coords, drv1_km, drv1_min, _ = mapbox_route([origin, apt_gate], profile="driving")
walk1_coords, walk1_km, walk1_min, _ = mapbox_route([apt_gate, apt_front], profile="walking")
drv2_coords, drv2_km, drv2_min, _ = mapbox_route([origin, apt_front], profile="driving")

asis_total = (drv1_min or 0) + (walk1_min or 0)
improvement_min = asis_total - (drv2_min or 0)
improvement_pct = (improvement_min / asis_total * 100) if asis_total > 0 else 0

# 메트릭 표시
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)
k1.metric("AS-IS 차량", f"{(drv1_min or 0):.2f}분")
k2.metric("AS-IS 도보", f"{(walk1_min or 0):.2f}분")
k3.metric("TO-BE 차량", f"{(drv2_min or 0):.2f}분")
# 총 개선 빨간색 표시
impr_min_txt = f"{(improvement_min):.2f}분"
impr_pct_txt = f"{(improvement_pct):.1f}%"
k4.markdown(
    f"""
    <div style="text-align:center;">
        <div style="font-weight:bold; font-size:16px;">총 개선</div>
        <div style="color:#dc2626; font-size:24px; font-weight:bold;">{impr_min_txt}</div>
        <div style="color:green; font-size:14px;">▲ {impr_pct_txt}</div>
    </div>
    """,
    unsafe_allow_html=True
)

# 지도 레이아웃
left, right = st.columns(2)
with left:
    st.markdown("#### 🚗 AS-IS — 정문까지 차량 + 잔여 도보")
    m1 = folium.Map(location=center_hint, zoom_start=17, control_scale=False)
    add_carto_tile(m1)
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
    folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m1)
    if drv1_coords:
        folium.PolyLine(drv1_coords, color="#1f77b4", weight=5, opacity=0.9).add_to(m1)
    if walk1_coords:
        folium.PolyLine(walk1_coords, color="#2ca02c", weight=5, opacity=0.9, dash_array="6,8").add_to(m1)
    st_folium(m1, use_container_width=True, height=600)

with right:
    st.markdown("#### ✅ TO-BE — 아파트 앞까지 차량")
    m2 = folium.Map(location=center_hint, zoom_start=17, control_scale=False)
    add_carto_tile(m2)
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m2)
    if drv2_coords:
        folium.PolyLine(drv2_coords, color="#9467bd", weight=5, opacity=0.95).add_to(m2)
    st_folium(m2, use_container_width=True, height=600)

# 결과 테이블
result_df = pd.DataFrame([
    {"구분": "AS-IS 차량", "거리(km)": round(drv1_km or 0, 2), "시간(분)": round(drv1_min or 0, 2)},
    {"구분": "AS-IS 도보", "거리(km)": round(walk1_km or 0, 2), "시간(분)": round(walk1_min or 0, 2)},
    {"구분": "TO-BE 차량", "거리(km)": round(drv2_km or 0, 2), "시간(분)": round(drv2_min or 0, 2)},
])
st.dataframe(result_df, use_container_width=True)
