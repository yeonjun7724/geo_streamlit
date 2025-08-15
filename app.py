import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="하남시 MAT 기반 아파트 네비게이션",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# Secrets / Tokens
# ──────────────────────────────────────────────────────────────────────────────
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")
if not MAPBOX_TOKEN:
    st.warning("Mapbox 토큰(MAPBOX_TOKEN)이 설정되지 않았습니다. Settings → Secrets 또는 환경변수로 설정하세요.")

# ──────────────────────────────────────────────────────────────────────────────
# Data (각 단지 기준 외부 기준점 포함)
# ──────────────────────────────────────────────────────────────────────────────
# external_origin: 단지 외부의 대표 진입로 좌표 (lat, lon)
HANAM_APARTMENTS = {
    "미사강변 한강센트럴파크": {
        "center": [37.5621, 127.1734],
        "entrance": [37.5619, 127.1732],
        "external_origin": [37.5600, 127.1700],
        "buildings": [
            {"name": "101동", "lat": 37.5623, "lon": 127.1736},
            {"name": "102동", "lat": 37.5625, "lon": 127.1738},
            {"name": "103동", "lat": 37.5627, "lon": 127.1740},
        ],
        "facilities": [
            {"name": "소화전 #1", "lat": 37.5622, "lon": 127.1735, "type": "hydrant"},
            {"name": "관리사무소", "lat": 37.5620, "lon": 127.1733, "type": "office"},
        ],
    },
    "미사강변 신리마을": {
        "center": [37.5645, 127.1689],
        "entrance": [37.5643, 127.1687],
        "external_origin": [37.5636, 127.1668],
        "buildings": [
            {"name": "201동", "lat": 37.5647, "lon": 127.1691},
            {"name": "202동", "lat": 37.5649, "lon": 127.1693},
        ],
        "facilities": [
            {"name": "소화전 #2", "lat": 37.5646, "lon": 127.1690, "type": "hydrant"},
        ],
    },
    "고덕 래미안": {
        "center": [37.5498, 127.1542],
        "entrance": [37.5496, 127.1540],
        "external_origin": [37.5487, 127.1518],
        "buildings": [
            {"name": "301동", "lat": 37.5500, "lon": 127.1544},
            {"name": "302동", "lat": 37.5502, "lon": 127.1546},
        ],
        "facilities": [
            {"name": "소화전 #3", "lat": 37.5499, "lon": 127.1543, "type": "hydrant"},
        ],
    },
    "고덕 그라시움": {
        "center": [37.5521, 127.1578],
        "entrance": [37.5519, 127.1576],
        "external_origin": [37.5510, 127.1556],
        "buildings": [
            {"name": "401동", "lat": 37.5523, "lon": 127.1580},
        ],
        "facilities": [
            {"name": "관리사무소", "lat": 37.5520, "lon": 127.1577, "type": "office"},
        ],
    },
}

SCENARIO_STYLES = {
    "일반 상황": {"route_color": "blue", "icon_color": "blue", "profile": "driving"},
    "긴급 상황 (소방)": {"route_color": "red", "icon_color": "red", "profile": "driving"},
    "긴급 상황 (구급)": {"route_color": "green", "icon_color": "green", "profile": "driving"},
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers (routing)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def mapbox_route(points_latlon, profile="driving"):
    """Mapbox Directions API → 경로 좌표([[lat,lon],...]), 거리(km), 시간(분)"""
    if not MAPBOX_TOKEN:
        return [], None, None
    coords = ";".join([f"{lon},{lat}" for lat, lon in points_latlon])
    url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coords}"
    params = {"geometries": "geojson", "overview": "full", "access_token": MAPBOX_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("routes"):
            return [], None, None
        route = data["routes"][0]
        line = route["geometry"]["coordinates"]  # [[lon,lat],...]
        coords_latlon = [[lat, lon] for lon, lat in line]
        distance_km = route.get("distance", 0) / 1000.0
        duration_min = route.get("duration", 0) / 60.0
        return coords_latlon, distance_km, duration_min
    except Exception:
        return [], None, None


def add_mapbox_tile(m: folium.Map, style="mapbox/streets-v12"):
    if not MAPBOX_TOKEN:
        return m
    tile_url = f"https://api.mapbox.com/styles/v1/{style}/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={MAPBOX_TOKEN}"
    folium.TileLayer(tiles=tile_url, attr="Mapbox", name="Mapbox", control=False).add_to(m)
    return m


def pick_destination(apt: dict, destination_type: str):
    if destination_type == "동 출입구" and apt.get("buildings"):
        b = apt["buildings"][0]
        return [b["lat"], b["lon"]], f"{b['name']} 출입구"
    if destination_type == "소화전":
        for f in apt.get("facilities", []):
            if f.get("type") == "hydrant":
                return [f["lat"], f["lon"]], f["name"]
    if destination_type == "관리사무소":
        for f in apt.get("facilities", []):
            if f.get("type") == "office":
                return [f["lat"], f["lon"]], f["name"]
    # fallback
    if apt.get("buildings"):
        b = apt["buildings"][0]
        return [b["lat"], b["lon"]], f"{b['name']} 출입구(대체)"
    return apt["entrance"], "아파트 정문(대체)"

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar (간소화: 선택만 남김)
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    apartment_complex = st.selectbox("아파트 단지", list(HANAM_APARTMENTS.keys()), index=0)
    destination_type = st.selectbox("목적지", ["동 출입구", "소화전", "관리사무소"], index=0)
    scenario = st.radio("시나리오", list(SCENARIO_STYLES.keys()), index=0)

# ──────────────────────────────────────────────────────────────────────────────
# Main Title
# ──────────────────────────────────────────────────────────────────────────────
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")
st.caption("Mapbox Directions API를 이용해 AS-IS(정문) vs TO-BE(단지 내부 목적지) 실측 거리·시간을 산출합니다.")

as_is_tab, effect_tab, sim_tab = st.tabs(["🔄 AS IS vs TO BE", "📊 효과 분석", "🗺️ 단지별 지도"])

selected = HANAM_APARTMENTS[apartment_complex]
style = SCENARIO_STYLES[scenario]
origin = selected["external_origin"]

dest_point, dest_label = pick_destination(selected, destination_type)

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: AS-IS vs TO-BE (실데이터 기반 산출)
# ──────────────────────────────────────────────────────────────────────────────
with as_is_tab:
    left, right = st.columns(2)

    # AS-IS: 외부 기준점 → 정문
    as_is_coords, as_is_km, as_is_min = mapbox_route([origin, selected["entrance"]], profile=style["profile"])    
    # TO-BE: 외부 기준점 → 정문 → 내부 목적지
    to_be_coords, to_be_km, to_be_min = mapbox_route([origin, selected["entrance"], dest_point], profile=style["profile"]) 

    with left:
        st.markdown("#### ❌ AS IS — 정문까지")
        m1 = folium.Map(location=selected["center"], zoom_start=17)
        add_mapbox_tile(m1)
        folium.Marker(origin, popup="외부 기준점", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
        folium.Marker(selected["entrance"], popup="아파트 정문", icon=folium.Icon(color="red", icon="stop")).add_to(m1)
        if as_is_coords:
            folium.PolyLine(as_is_coords, color=style["route_color"], weight=4, opacity=0.9, popup="AS-IS 경로").add_to(m1)
        st_folium(m1, use_container_width=True, height=380)

    with right:
        st.markdown("#### ✅ TO BE — 단지 내부 목적지까지")
        m2 = folium.Map(location=selected["center"], zoom_start=17)
        add_mapbox_tile(m2)
        folium.Marker(origin, popup="외부 기준점", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
        folium.Marker(selected["entrance"], popup="정문", icon=folium.Icon(color="orange", icon="flag")).add_to(m2)
        folium.Marker(dest_point, popup=dest_label, icon=folium.Icon(color=style["icon_color"], icon="home")).add_to(m2)
        if to_be_coords:
            folium.PolyLine(to_be_coords, color=style["route_color"], weight=5, opacity=0.95, popup="TO-BE 경로").add_to(m2)
        st_folium(m2, use_container_width=True, height=380)

    st.markdown("---")
    if as_is_min is not None and to_be_min is not None:
        improv = (as_is_min - to_be_min) / as_is_min * 100 if as_is_min > 0 else 0
        df = pd.DataFrame({
            "구분": ["AS-IS", "TO-BE"],
            "거리(km)": [round(as_is_km, 2), round(to_be_km, 2)],
            "시간(분)": [round(as_is_min, 2), round(to_be_min, 2)],
        })
        st.dataframe(df, use_container_width=True)
        st.success(f"시간 단축률: **{improv:.1f}%**  |  AS-IS {as_is_min:.2f}분 → TO-BE {to_be_min:.2f}분")
    else:
        st.error("경로를 계산할 수 없습니다. MAPBOX_TOKEN 또는 네트워크를 확인하세요.")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: 효과 분석 (단지별 실측 비교)
# ──────────────────────────────────────────────────────────────────────────────
with effect_tab:
    rows = []
    for name, apt in HANAM_APARTMENTS.items():
        dest_pt, _ = pick_destination(apt, destination_type)
        c1, d1, t1 = mapbox_route([apt["external_origin"], apt["entrance"]], profile=style["profile"])  # AS-IS
        c2, d2, t2 = mapbox_route([apt["external_origin"], apt["entrance"], dest_pt], profile=style["profile"])  # TO-BE
        if d1 is None or t1 is None or d2 is None or t2 is None:
            continue
        rows.append({
            "아파트": name,
            "AS-IS 시간(분)": round(t1, 2),
            "TO-BE 시간(분)": round(t2, 2),
            "시간 단축률(%)": round((t1 - t2) / t1 * 100, 1) if t1 > 0 else 0,
            "AS-IS 거리(km)": round(d1, 2),
            "TO-BE 거리(km)": round(d2, 2),
        })

    if rows:
        result_df = pd.DataFrame(rows)
        st.dataframe(result_df, use_container_width=True)
        fig = px.bar(result_df, x="아파트", y=["AS-IS 시간(분)", "TO-BE 시간(분)"], barmode="group", title="단지별 평균 도달시간(분)")
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.bar(result_df, x="아파트", y="시간 단축률(%)", title="단지별 시간 단축률(%)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.error("분석할 경로 데이터가 없습니다.")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: 단지별 지도 (실경로 시각화)
# ──────────────────────────────────────────────────────────────────────────────
with sim_tab:
    m_total = folium.Map(location=[37.5539, 127.1650], zoom_start=14)
    add_mapbox_tile(m_total)

    colors = ["blue", "green", "red", "purple"]
    for i, (apt_name, apt) in enumerate(HANAM_APARTMENTS.items()):
        color = colors[i % len(colors)]
        folium.Marker(location=apt["center"], popup=f"{apt_name}", icon=folium.Icon(color=color, icon="home")).add_to(m_total)
        dest_pt, _ = pick_destination(apt, destination_type)
        coords, _, _ = mapbox_route([apt["external_origin"], apt["entrance"], dest_pt], profile="driving")
        if coords:
            folium.PolyLine(locations=coords, color=color, weight=3, opacity=0.8, popup=f"{apt_name} 경로").add_to(m_total)

    st_folium(m_total, use_container_width=True, height=520)

# ──────────────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d')} | 데이터 소스: Mapbox Directions API")
