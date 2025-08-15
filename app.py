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
    "일반 상황": {"route_color": "blue", "icon_color": "blue"},
    "긴급 상황 (소방)": {"route_color": "red", "icon_color": "red"},
    "긴급 상황 (구급)": {"route_color": "green", "icon_color": "green"},
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
    params = {"geometries": "geojson", "overview": "full", "access_token": MAPBOX_TOKEN}
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
# Sidebar (선택만 유지)
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    apartment_complex = st.selectbox("아파트 단지", list(HANAM_APARTMENTS.keys()), index=0)
    destination_type = st.selectbox("목적지", ["동 출입구", "소화전", "관리사무소"], index=0)

# ──────────────────────────────────────────────────────────────────────────────
# Main Title
# ──────────────────────────────────────────────────────────────────────────────
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")
st.caption("AS-IS: 정문까지 차량 + 내부 도보 / TO-BE: 건물 전면까지 차량 + 잔여 도보 (Mapbox 기준)")

as_is_tab, effect_tab, map_tab = st.tabs(["🔄 AS IS vs TO BE", "📊 효과 분석", "🗺️ 단지별 지도"])

selected = HANAM_APARTMENTS[apartment_complex]
origin = selected["external_origin"]

dest_point, dest_label = pick_destination(selected, destination_type)

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: 분해 계산 (차량+도보)
# ──────────────────────────────────────────────────────────────────────────────
with as_is_tab:
    left, right = st.columns(2)

    # AS-IS
    drv1_coords, drv1_km, drv1_min, drv1_end = mapbox_route([origin, selected["entrance"]], profile="driving")
    walk1_coords, walk1_km, walk1_min, _ = mapbox_route([selected["entrance"], dest_point], profile="walking")

    # TO-BE
    drv2_coords, drv2_km, drv2_min, drv2_end = mapbox_route([origin, dest_point], profile="driving")
    # 차량이 진입할 수 없는 내부 구간은 잔여 도보로 산정 (운전 경로의 최종 노드 → 정확 목적지)
    walk2_start = drv2_end if drv2_end else dest_point
    walk2_coords, walk2_km, walk2_min, _ = mapbox_route([walk2_start, dest_point], profile="walking")

    with left:
        st.markdown("#### ❌ AS IS — 정문까지 차량 + 내부 도보")
        m1 = folium.Map(location=selected["center"], zoom_start=17)
        add_mapbox_tile(m1)
        # markers
        folium.Marker(origin, popup="외부 기준점", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
        folium.Marker(selected["entrance"], popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
        folium.Marker(dest_point, popup=dest_label, icon=folium.Icon(color="blue", icon="home")).add_to(m1)
        # lines
        if drv1_coords:
            folium.PolyLine(drv1_coords, color="blue", weight=4, opacity=0.9, popup="차량(AS-IS)").add_to(m1)
        if walk1_coords:
            folium.PolyLine(walk1_coords, color="green", weight=4, opacity=0.9, popup="도보(AS-IS)", dash_array="5,7").add_to(m1)
        st_folium(m1, use_container_width=True, height=400)

        if drv1_min is not None and walk1_min is not None:
            total1 = (drv1_min or 0) + (walk1_min or 0)
            st.metric("총 시간(분)", f"{total1:.2f}")
            st.caption(f"차량 {drv1_min:.2f}분  •  도보 {walk1_min:.2f}분  •  거리 {((drv1_km or 0)+(walk1_km or 0)):.2f}km")

    with right:
        st.markdown("#### ✅ TO BE — 건물 전면까지 차량 + 잔여 도보")
        m2 = folium.Map(location=selected["center"], zoom_start=17)
        add_mapbox_tile(m2)
        folium.Marker(origin, popup="외부 기준점", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
        folium.Marker(dest_point, popup=dest_label, icon=folium.Icon(color="green", icon="home")).add_to(m2)
        if drv2_coords:
            folium.PolyLine(drv2_coords, color="blue", weight=5, opacity=0.95, popup="차량(TO-BE)").add_to(m2)
        if walk2_coords and (walk2_km or 0) > 0:
            folium.PolyLine(walk2_coords, color="green", weight=4, opacity=0.9, popup="도보(TO-BE)", dash_array="5,7").add_to(m2)
        st_folium(m2, use_container_width=True, height=400)

        if drv2_min is not None and walk2_min is not None:
            total2 = (drv2_min or 0) + (walk2_min or 0)
            st.metric("총 시간(분)", f"{total2:.2f}")
            st.caption(f"차량 {drv2_min:.2f}분  •  도보 {walk2_min:.2f}분  •  거리 {((drv2_km or 0)+(walk2_km or 0)):.2f}km")

    st.markdown("---")
    if None not in (drv1_min, walk1_min, drv2_min, walk2_min):
        total1 = (drv1_min or 0) + (walk1_min or 0)
        total2 = (drv2_min or 0) + (walk2_min or 0)
        walk_improv = ((walk1_min or 0) - (walk2_min or 0))
        total_improv_pct = (total1 - total2) / total1 * 100 if total1 > 0 else 0
        st.success(
            f"도보 시간 단축: **{walk_improv:.2f}분**  |  총 소요시간: {total1:.2f}분 → {total2:.2f}분 (**{total_improv_pct:.1f}% ↓**)"
        )
    else:
        st.error("경로 계산에 실패했습니다. 토큰 또는 네트워크 상태를 확인하세요.")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: 효과 분석 (단지별 차량/도보 분해)
# ──────────────────────────────────────────────────────────────────────────────
with effect_tab:
    rows = []
    for name, apt in HANAM_APARTMENTS.items():
        dest_pt, _ = pick_destination(apt, destination_type)
        # AS-IS
        _, ddrv1, tdrv1, _ = mapbox_route([apt["external_origin"], apt["entrance"]], profile="driving")
        _, dwalk1, twalk1, _ = mapbox_route([apt["entrance"], dest_pt], profile="walking")
        # TO-BE
        _, ddrv2, tdrv2, end2 = mapbox_route([apt["external_origin"], dest_pt], profile="driving")
        start_walk2 = end2 if end2 else dest_pt
        _, dwalk2, twalk2, _ = mapbox_route([start_walk2, dest_pt], profile="walking")

        if None in (tdrv1, twalk1, tdrv2, twalk2):
            continue
        total1 = (tdrv1 or 0) + (twalk1 or 0)
        total2 = (tdrv2 or 0) + (twalk2 or 0)
        rows.append({
            "아파트": name,
            "AS-IS 차량(분)": round(tdrv1, 2),
            "AS-IS 도보(분)": round(twalk1, 2),
            "TO-BE 차량(분)": round(tdrv2, 2),
            "TO-BE 도보(분)": round(twalk2, 2),
            "총시간 AS-IS(분)": round(total1, 2),
            "총시간 TO-BE(분)": round(total2, 2),
            "총시간 개선률(%)": round((total1 - total2) / total1 * 100, 1) if total1 > 0 else 0,
            "도보 절감(분)": round((twalk1 - twalk2), 2),
        })

    if rows:
        result_df = pd.DataFrame(rows)
        st.dataframe(result_df, use_container_width=True)
        fig = px.bar(result_df, x="아파트", y=["AS-IS 도보(분)", "TO-BE 도보(분)"], barmode="group", title="단지별 도보시간 비교")
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.bar(result_df, x="아파트", y="총시간 개선률(%)", title="단지별 총시간 개선률")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.error("분석할 경로 데이터가 없습니다.")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: 단지별 지도 (실경로 시각화)
# ──────────────────────────────────────────────────────────────────────────────
with map_tab:
    m_total = folium.Map(location=[37.5539, 127.1650], zoom_start=14)
    add_mapbox_tile(m_total)

    colors = ["blue", "green", "red", "purple"]
    for i, (apt_name, apt) in enumerate(HANAM_APARTMENTS.items()):
        color = colors[i % len(colors)]
        folium.Marker(location=apt["center"], popup=f"{apt_name}", icon=folium.Icon(color=color, icon="home")).add_to(m_total)
        dest_pt, _ = pick_destination(apt, destination_type)
        # 차량 경로(TO-BE)
        drv_coords, _, _, drv_end = mapbox_route([apt["external_origin"], dest_pt], profile="driving")
        if drv_coords:
            folium.PolyLine(locations=drv_coords, color=color, weight=3, opacity=0.85, popup=f"{apt_name} 차량경로").add_to(m_total)
        # 잔여 도보
        walk_start = drv_end if drv_end else dest_pt
        walk_coords, _, _, _ = mapbox_route([walk_start, dest_pt], profile="walking")
        if walk_coords:
            folium.PolyLine(locations=walk_coords, color="green", weight=3, opacity=0.9, dash_array="5,7", popup=f"{apt_name} 도보").add_to(m_total)

    st_folium(m_total, use_container_width=True, height=520)

# ──────────────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d')} | 데이터 소스: Mapbox Directions API (driving + walking)")
