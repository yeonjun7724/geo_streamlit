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
# Data 소스(이름 기반, 좌표는 런타임에 Mapbox Geocoding으로 해석)
ORIGINS = {
    "하남소방서": "하남소방서",
    "미사강변119안전센터": "경기도 하남시 미사강변동로 95 미사강변119안전센터",
}

APARTMENTS = {
    # 정문 후보 쿼리와 건물(목표) 후보 쿼리를 분리해 더 현실적으로 접근
    "미사강변 한강센트럴파크": {
        "gate_query": "미사강변 한강센트럴파크 정문",
        "front_query": "미사강변 한강센트럴파크 101동",
        "center_hint": [37.5621, 127.1734],
    },
    "미사강변 신리마을": {
        "gate_query": "미사강변 신리마을 정문",
        "front_query": "미사강변 신리마을 201동",
        "center_hint": [37.5645, 127.1689],
    },
    "고덕 래미안": {
        "gate_query": "고덕 래미안 아파트 정문",
        "front_query": "고덕 래미안 301동",
        "center_hint": [37.5498, 127.1542],
    },
    "고덕 그라시움": {
        "gate_query": "고덕 그라시움 정문",
        "front_query": "고덕 그라시움 401동",
        "center_hint": [37.5521, 127.1578],
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


@st.cache_data(show_spinner=False, ttl=3600)
def mapbox_geocode(query: str, proximity: list | None = None):
    """Mapbox Geocoding API → (lat, lon). 실패 시 None 반환"""
    if not MAPBOX_TOKEN:
        return None
    url = "https://api.mapbox.com/geocoding/v5/mapbox.places/" + requests.utils.quote(query) + ".json"
    params = {"access_token": MAPBOX_TOKEN, "limit": 1, "language": "ko"}
    if proximity:
        params["proximity"] = f"{proximity[1]},{proximity[0]}"  # lon,lat
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("features"):
            lon, lat = data["features"][0]["center"]
            return [lat, lon]
        return None
    except Exception:
        return None


def resolve_apartment(name: str):
    """아파트명 → (gate_latlon, front_latlon, center_hint)"""
    info = APARTMENTS[name]
    hint = info.get("center_hint")
    gate = mapbox_geocode(info["gate_query"], proximity=hint)
    front = mapbox_geocode(info["front_query"], proximity=hint)
    # 게이트가 없으면 차량 경로의 마지막 노드를 게이트로 근사할 수 있으나,
    # 우선은 front로 폴백하여 경로 계산이 끊기지 않도록 처리
    if gate is None:
        gate = front
    return gate, front, hint or front


def resolve_origin(name: str):
    return mapbox_geocode(ORIGINS[name])

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar (선택만 유지)
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    origin_name = st.selectbox("출발지(기관)", list(ORIGINS.keys()), index=0)
    apartment_name = st.selectbox("아파트 단지", list(APARTMENTS.keys()), index=0)

# ──────────────────────────────────────────────────────────────────────────────
# Main Title
# ──────────────────────────────────────────────────────────────────────────────
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")
st.caption("AS-IS: 정문까지 차량 + 내부 도보 / TO-BE: 건물 전면까지 차량 + 잔여 도보 (Mapbox 기준)")

as_is_tab, effect_tab, map_tab = st.tabs(["🔄 AS IS vs TO BE", "📊 효과 분석", "🗺️ 단지별 지도"])

origin = resolve_origin(origin_name)
apt_gate, apt_front, center_hint = resolve_apartment(apartment_name)


# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: AS-IS(정문까지 차량+도보) vs TO-BE(아파트 앞까지 차량)
with as_is_tab:
    left, right = st.columns(2)

    if not origin or not apt_front:
        st.error("출발지 또는 목적지를 찾을 수 없습니다. 지오코딩 쿼리를 확인하세요.")
    else:
        # 1) AS-IS: 차량(출발지→정문) + 도보(정문→아파트 앞)
        #    정문 좌표가 없으면 차량 경로의 마지막 노드를 정문으로 근사
        if apt_gate:
            drv1_coords, drv1_km, drv1_min, drv1_end = mapbox_route([origin, apt_gate], profile="driving")
            walk1_coords, walk1_km, walk1_min, _ = mapbox_route([apt_gate, apt_front], profile="walking")
        else:
            # gate 미탐색 시: 차량을 아파트 앞까지, 그 지점을 gate로 간주하여 도보 0
            drv1_coords, drv1_km, drv1_min, drv1_end = mapbox_route([origin, apt_front], profile="driving")
            walk1_coords, walk1_km, walk1_min = [], 0.0, 0.0

        # 2) TO-BE: 차량(출발지→아파트 앞) — 도보 없음
        drv2_coords, drv2_km, drv2_min, _ = mapbox_route([origin, apt_front], profile="driving")

        # Left: AS-IS 시각화
        with left:
            st.markdown("#### ❌ AS IS — 정문까지 차량 + 내부 도보")
            m1 = folium.Map(location=center_hint or apt_front, zoom_start=17)
            add_mapbox_tile(m1)
            folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
            if apt_gate:
                folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
            folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="blue", icon="home")).add_to(m1)
            if drv1_coords:
                folium.PolyLine(drv1_coords, color="blue", weight=4, opacity=0.9, popup="차량(AS-IS)").add_to(m1)
            if walk1_coords:
                folium.PolyLine(walk1_coords, color="green", weight=4, opacity=0.9, popup="도보(AS-IS)", dash_array="5,7").add_to(m1)
            st_folium(m1, use_container_width=True, height=400)

            if drv1_min is not None and walk1_min is not None:
                total1 = (drv1_min or 0) + (walk1_min or 0)
                st.metric("총 시간(분)", f"{total1:.2f}")
                st.caption(f"차량 {drv1_min or 0:.2f}분  •  도보 {walk1_min or 0:.2f}분  •  거리 {((drv1_km or 0)+(walk1_km or 0)):.2f}km")

        # Right: TO-BE 시각화
        with right:
            st.markdown("#### ✅ TO BE — 아파트 앞까지 차량(도보 없음)")
            m2 = folium.Map(location=center_hint or apt_front, zoom_start=17)
            add_mapbox_tile(m2)
            folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
            folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m2)
            if drv2_coords:
                folium.PolyLine(drv2_coords, color="blue", weight=5, opacity=0.95, popup="차량(TO-BE)").add_to(m2)
            st_folium(m2, use_container_width=True, height=400)

            if drv2_min is not None:
                st.metric("총 시간(분)", f"{drv2_min:.2f}")
                st.caption(f"차량 {drv2_min:.2f}분  •  거리 {drv2_km or 0:.2f}km")

        st.markdown("---")
        if drv1_min is not None and walk1_min is not None and drv2_min is not None:
            total1 = (drv1_min or 0) + (walk1_min or 0)
            total2 = drv2_min or 0
            diff = total1 - total2
            pct = (diff / total1 * 100) if total1 > 0 else 0
            st.success(f"총 소요시간: AS-IS {total1:.2f}분 → TO-BE {total2:.2f}분  (Δ {diff:.2f}분, {pct:.1f}% ↓)")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: 효과 분석 (단지별 차량/도보 분해)
# ──────────────────────────────────────────────────────────────────────────────
with effect_tab:
    rows = []
    for apt_name in APARTMENTS.keys():
        origin_pt = resolve_origin(origin_name)
        gate_pt, front_pt, _ = resolve_apartment(apt_name)
        if not origin_pt or not front_pt:
            continue
        # AS-IS
        if gate_pt:
            _, ddrv1, tdrv1, _ = mapbox_route([origin_pt, gate_pt], profile="driving")
            _, dwalk1, twalk1, _ = mapbox_route([gate_pt, front_pt], profile="walking")
        else:
            _, ddrv1, tdrv1, _ = mapbox_route([origin_pt, front_pt], profile="driving")
            dwalk1, twalk1 = 0.0, 0.0
        # TO-BE (driving only)
        _, ddrv2, tdrv2, _ = mapbox_route([origin_pt, front_pt], profile="driving")

        if None in (tdrv1, tdrv2) or twalk1 is None:
            continue
        total1 = (tdrv1 or 0) + (twalk1 or 0)
        total2 = (tdrv2 or 0)
        rows.append({
            "아파트": apt_name,
            "AS-IS 차량(분)": round(tdrv1 or 0, 2),
            "AS-IS 도보(분)": round(twalk1 or 0, 2),
            "TO-BE 차량(분)": round(tdrv2 or 0, 2),
            "총시간 AS-IS(분)": round(total1, 2),
            "총시간 TO-BE(분)": round(total2, 2),
            "총시간 개선률(%)": round((total1 - total2) / total1 * 100, 1) if total1 > 0 else 0,
        })

    if rows:
        result_df = pd.DataFrame(rows)
        st.dataframe(result_df, use_container_width=True)
        fig = px.bar(result_df, x="아파트", y=["총시간 AS-IS(분)", "총시간 TO-BE(분)"], barmode="group", title="단지별 총 소요시간 비교")
        st.plotly_chart(fig, use_container_width=True)
        fig2 = px.bar(result_df, x="아파트", y="총시간 개선률(%)", title="단지별 총시간 개선률")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.error("분석할 경로 데이터가 없습니다.")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: 단지별 지도 (실경로 시각화)
# ──────────────────────────────────────────────────────────────────────────────
with map_tab:
    m_total = folium.Map(location=[37.5539, 127.1650], zoom_start=13)
    add_mapbox_tile(m_total)

    colors = ["blue", "green", "red", "purple"]
    for i, apt_name in enumerate(APARTMENTS.keys()):
        color = colors[i % len(colors)]
        gate_pt, front_pt, center_hint = resolve_apartment(apt_name)
        if center_hint:
            folium.Marker(location=center_hint, popup=f"{apt_name}", icon=folium.Icon(color=color, icon="home")).add_to(m_total)
        # TO-BE 차량 경로만 그려 비교
        origin_pt = resolve_origin(origin_name)
        if origin_pt and front_pt:
            drv_coords, _, _, _ = mapbox_route([origin_pt, front_pt], profile="driving")
            if drv_coords:
                folium.PolyLine(locations=drv_coords, color=color, weight=3, opacity=0.85, popup=f"{apt_name} 차량경로").add_to(m_total)
    st_folium(m_total, use_container_width=True, height=520)

# ──────────────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d')} | 데이터 소스: Mapbox Directions API (driving + walking)")
