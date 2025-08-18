import os
import math
import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
from folium.plugins import AntPath

# ── 페이지 기본 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="하남시 벡터 중축 변환(MAT) 기반 아파트 경로 안내 서비스", page_icon="🏢", layout="wide")

# ── 전역 스타일 ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root { --muted:#6B7280; --text:#111827; --blue:#1d4ed8; --blue-weak:#e6efff; }

html, body, [data-testid="stAppViewContainer"] {
    color: var(--text) !important;
    font-size: 1.05rem !important;
    line-height: 1.55 !important;
}
[data-testid="stHeader"] { background: transparent !important; }
.main > div { padding-top: 0.6rem !important; }

.block-container { max-width: 100%; padding-left: 2rem; padding-right: 2rem; margin: 0 auto; }

.app-title { font-size: 3.6rem; font-weight: 900; letter-spacing: -0.02em; margin: 0.4rem 0 1.2rem 0; text-align: center; }

.section { margin: 2rem 0; }

.stSelectbox, .stSelectbox > div { width: 100% !important; font-size: 1.1rem !important; }

.metric-plain .label { color: var(--muted); font-weight: 600; margin-bottom: 6px; font-size: 1.1rem; }
.metric-plain .value { font-size: 2.4rem; font-weight: 700; line-height: 1.2; color: var(--text); }

.metric-wrap .label { color: var(--muted); font-weight: 600; margin-bottom: 6px; font-size: 1.1rem; }
.metric-wrap .value { font-size: 2.4rem; font-weight: 800; line-height: 1.2; color: var(--blue); }
.metric-wrap .delta {
    display:inline-block; margin-top: 8px; padding: 3px 10px; font-size: 1rem;
    background: var(--blue-weak); color: var(--blue); border-radius: 999px;
}

h4 { text-align: left; margin-bottom: 0.8rem; font-size: 1.3rem; font-weight: 700; }

p, li, .stMarkdown { font-size: 1.1rem !important; }

small { font-size: 0.95rem; }

.leaflet-control-attribution { display: none; }
.leaflet-control-scale { display: none !important; }

.divider { height: 1px; background: #e5e7eb; margin: 1.6rem 0; }

/* 상태 배지 */
.badge { display:inline-block; padding:4px 10px; border-radius:999px; font-size:0.9rem; border:1px solid #e5e7eb; background:#fff; }
.badge.ok { color:#065f46; border-color:#a7f3d0; background:#ecfdf5; }
.badge.err { color:#7f1d1d; border-color:#fecaca; background:#fef2f2; }
.badge.info { color:#1e3a8a; border-color:#bfdbfe; background:#eff6ff; }
</style>
""", unsafe_allow_html=True)

# ── Mapbox 토큰 ─────────────────────────────────────────────────────────────────
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")

# ── 데이터 (출발지 + 아파트 + 경로 인근 하드코딩 안전시설) ──────────────────────
ORIGINS = {
    "하남소방서": [37.539826, 127.220661],
    "미사강변119안전센터": [37.566902, 127.185298],
}

APARTMENTS = {
    "미사강변센트럴풍경채": {
        "center": [37.556591, 127.183081],
        "gate":   [37.556844, 127.181887],
        "front":  [37.557088, 127.183036],
        "hydrants": [
            [37.55695, 127.18220],
            [37.55702, 127.18255],
            [37.55706, 127.18285],
            [37.55710, 127.18305],
        ],
        "fire_lanes": [
            [37.55712, 127.18302],
            [37.55692, 127.18298],
            [37.55698, 127.18322],
        ],
    },
    "미사강변 푸르지오": {
        "center": [37.564925, 127.184055],
        "gate":   [37.565196, 127.182840],
        "front":  [37.566168, 127.182795],
        "hydrants": [
            [37.56530, 127.18310],
            [37.56560, 127.18305],
            [37.56590, 127.18295],
            [37.56610, 127.18285],
        ],
        "fire_lanes": [
            [37.56605, 127.18280],
            [37.56585, 127.18315],
            [37.56555, 127.18320],
        ],
    },
    "미사강변 리슈빌": {
        "center": [37.572842, 127.180515],
        "gate":   [37.573449, 127.181672],
        "front":  [37.573080, 127.180428],
        "hydrants": [
            [37.57320, 127.18110],
            [37.57318, 127.18085],
            [37.57312, 127.18065],
            [37.57308, 127.18050],
        ],
        "fire_lanes": [
            [37.57310, 127.18040],
            [37.57325, 127.18070],
            [37.57300, 127.18080],
        ],
    },
    "미사강변 센트리버": {
        "center": [37.573741, 127.183326],
        "gate":   [37.573164, 127.181960],
        "front":  [37.573263, 127.183110],
        "hydrants": [
            [37.57325, 127.18230],
            [37.57330, 127.18270],
            [37.57332, 127.18295],
            [37.57330, 127.18315],
        ],
        "fire_lanes": [
            [37.57327, 127.18308],
            [37.57315, 127.18285],
            [37.57340, 127.18290],
        ],
    },
    "미사강변 한신휴플리스": {
        "center": [37.573769, 127.191912],
        "gate":   [37.572975, 127.192083],
        "front":  [37.573456, 127.191935],
        "hydrants": [
            [37.57315, 127.19205],
            [37.57330, 127.19200],
            [37.57355, 127.19198],
            [37.57370, 127.19195],
        ],
        "fire_lanes": [
            [37.57346, 127.19190],
            [37.57332, 127.19182],
            [37.57362, 127.19188],
        ],
    },
}

# ── 라우팅 엔진 ─────────────────────────────────────────────────────────────────
def _coords_to_lonlat_str(points_latlon):
    return ";".join([f"{lon},{lat}" for lat, lon in points_latlon])

@st.cache_data(show_spinner=False, ttl=300)
def mapbox_route(points_latlon, profile="driving"):
    if not MAPBOX_TOKEN:
        return [], None, None, None, "NO_TOKEN"
    url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{_coords_to_lonlat_str(points_latlon)}"
    params = {"geometries": "geojson", "overview": "full", "access_token": MAPBOX_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=12)
        status = f"HTTP {r.status_code}"
        r.raise_for_status()
        data = r.json()
        if not data.get("routes"):
            return [], None, None, None, "NO_ROUTE"
        route = data["routes"][0]
        line = route["geometry"]["coordinates"]  # [ [lon,lat], ... ]
        coords_latlon = [[lat, lon] for lon, lat in line]
        end_latlon = coords_latlon[-1] if coords_latlon else None
        distance_km = route.get("distance", 0) / 1000.0
        duration_min = route.get("duration", 0) / 60.0
        return coords_latlon, distance_km, duration_min, end_latlon, status
    except Exception as e:
        return [], None, None, None, f"ERROR:{type(e).__name__}"

@st.cache_data(show_spinner=False, ttl=300)
def osrm_route(points_latlon, profile="driving"):
    # profile: 'driving'|'walking' -> OSRM는 'car'|'foot'이지만 public 서버는 /route/v1/{driving|walking}
    base = "https://router.project-osrm.org/route/v1"
    url = f"{base}/{profile}/{_coords_to_lonlat_str(points_latlon)}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        r = requests.get(url, params=params, timeout=12)
        status = f"HTTP {r.status_code}"
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return [], None, None, None, "NO_ROUTE"
        route = data["routes"][0]
        line = route["geometry"]["coordinates"]
        coords_latlon = [[lat, lon] for lon, lat in line]
        end_latlon = coords_latlon[-1] if coords_latlon else None
        distance_km = route.get("distance", 0) / 1000.0
        duration_min = route.get("duration", 0) / 60.0
        return coords_latlon, distance_km, duration_min, end_latlon, status
    except Exception as e:
        return [], None, None, None, f"ERROR:{type(e).__name__}"

def routed_polyline(points_latlon, profile="driving"):
    """
    1) Mapbox 시도 → 실패하면 2) OSRM 폴백.
    반환: (coords, km, min, engine, status)
    """
    coords, km, mins, _, status = mapbox_route(points_latlon, profile=profile)
    if coords:
        return coords, km, mins, "Mapbox", status
    # 폴백
    coords2, km2, mins2, _, status2 = osrm_route(points_latlon, profile=profile)
    return coords2, km2, mins2, "OSRM", status2

# ── 타일/범례/마커 유틸 ─────────────────────────────────────────────────────────
def add_carto_tile(m: folium.Map, theme="positron"):
    if theme == "dark_matter":
        folium.TileLayer(tiles="CartoDB Dark_Matter", control=False).add_to(m)
    else:
        folium.TileLayer(tiles="CartoDB Positron", control=False).add_to(m)
    return m

def add_legend(m: folium.Map):
    legend_html = """
    <div style="
        position: fixed; bottom: 28px; left: 28px; width: 210px;
        background: rgba(255,255,255,0.95); z-index:9999; font-size:14px;
        border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 12px;">
      <div style="font-weight:700; margin-bottom:6px;">경로 범례</div>
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#1f77b4;"></span>
        <span>AS-IS 차량</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#2ca02c;"></span>
        <span>AS-IS 도보</span>
      </div>
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:#9467bd;"></span>
        <span>TO-BE 차량</span>
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

def add_fixed_safety(m: folium.Map, apt_info: dict):
    for i, (lat, lon) in enumerate(apt_info.get("hydrants", []), 1):
        folium.Marker([lat, lon], tooltip=f"소화전 #{i}",
                      icon=folium.Icon(color="red", icon="fire-extinguisher", prefix="fa")).add_to(m)
    for i, (lat, lon) in enumerate(apt_info.get("fire_lanes", []), 1):
        folium.Marker([lat, lon], tooltip=f"소방차 전용구역 #{i}",
                      icon=folium.Icon(color="orange", icon="truck", prefix="fa")).add_to(m)

def draw_path(m: folium.Map, coords, color="#1f77b4", use_ant=True):
    if not coords:
        return
    # AntPath가 드물게 렌더링 안 될 때가 있어 PolyLine 백업을 함께 추가
    if use_ant:
        try:
            AntPath(coords, color=color, weight=5, opacity=0.95, delay=800).add_to(m)
        except Exception:
            pass
    folium.PolyLine(coords, weight=5, opacity=0.85, color=color).add_to(m)

# ── 제목 ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">🏢 하남시 벡터 중축 변환(MAT) 기반 아파트 경로 안내 서비스</div>', unsafe_allow_html=True)

# ── 상단 상태/옵션 ──────────────────────────────────────────────────────────────
opt_col1, opt_col2, opt_col3 = st.columns([1,1,2])
with opt_col1:
    st.markdown(f"<span class='badge {'ok' if MAPBOX_TOKEN else 'err'}'>MAPBOX_TOKEN: {'OK' if MAPBOX_TOKEN else 'MISSING'}</span>", unsafe_allow_html=True)
with opt_col2:
    route_only = st.checkbox("경로만 표시 (마커/범례 숨김)", value=True)
with opt_col3:
    st.markdown("<span class='badge info'>엔진은 자동 선택 (Mapbox→OSRM 폴백)</span>", unsafe_allow_html=True)

# ── 컨트롤 ──────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 1])
with c1:
    origin_name = st.selectbox("출발지", list(ORIGINS.keys()), index=0)
with c2:
    apartment_name = st.selectbox("아파트 단지", list(APARTMENTS.keys()), index=0)

# ── 경로 계산 ───────────────────────────────────────────────────────────────────
origin = ORIGINS[origin_name]
apt = APARTMENTS[apartment_name]
apt_gate, apt_front, center_hint = apt["gate"], apt["front"], apt["center"]

drv1_coords, drv1_km, drv1_min, drv1_engine, drv1_status = routed_polyline([origin, apt_gate], profile="driving")
walk1_coords, walk1_km, walk1_min, walk1_engine, walk1_status = routed_polyline([apt_gate, apt_front], profile="walking")
drv2_coords, drv2_km, drv2_min, drv2_engine, drv2_status = routed_polyline([origin, apt_front], profile="driving")

asis_total = (drv1_min or 0) + (walk1_min or 0)
improvement_min = asis_total - (drv2_min or 0)
improvement_pct = (improvement_min / asis_total * 100) if asis_total > 0 else 0

# ── KPI: 세 개 모두 커스텀(블랙), "총 개선"만 파랑 ────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.markdown(f"""<div class="metric-plain"><div class="label">AS-IS 차량</div><div class="value">{(drv1_min or 0):.2f}분</div></div>""", unsafe_allow_html=True)
k2.markdown(f"""<div class="metric-plain"><div class="label">AS-IS 도보</div><div class="value">{(walk1_min or 0):.2f}분</div></div>""", unsafe_allow_html=True)
k3.markdown(f"""<div class="metric-plain"><div class="label">TO-BE 차량</div><div class="value">{(drv2_min or 0):.2f}분</div></div>""", unsafe_allow_html=True)
k4.markdown(f"""<div class="metric-wrap"><div class="label">총 개선</div><div class="value">{improvement_min:.2f}분</div><div class="delta">+ {improvement_pct:.1f}%</div></div>""", unsafe_allow_html=True)

# 디버그(엔진/상태) 노출
with st.expander("경로 계산 디버그"):
    st.write({
        "AS-IS 차량": {"engine": drv1_engine, "status": drv1_status, "km": drv1_km, "min": drv1_min},
        "AS-IS 도보": {"engine": walk1_engine, "status": walk1_status, "km": walk1_km, "min": walk1_min},
        "TO-BE 차량": {"engine": drv2_engine, "status": drv2_status, "km": drv2_km, "min": drv2_min},
    })

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 지도(2분할) ────────────────────────────────────────────────────────────────
map_height = 640
left, right = st.columns(2)

with left:
    st.markdown("#### AS-IS — 정문에서 차량 하차 + 잔여 도보")
    m1 = folium.Map(location=center_hint, zoom_start=17, control_scale=False, zoom_control=True)
    add_carto_tile(m1, theme="positron")
    if not route_only:
        folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
        folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
        folium.Marker(apt_front, popup="아파트 동 앞", icon=folium.Icon(color="green", icon="home")).add_to(m1)
    draw_path(m1, drv1_coords, color="#1f77b4", use_ant=True)
    draw_path(m1, walk1_coords, color="#2ca02c", use_ant=True)
    if not route_only:
        add_fixed_safety(m1, apt)
        add_legend(m1)
    st_folium(m1, use_container_width=True, height=map_height)

with right:
    st.markdown("#### TO-BE — 아파트 동 앞에서 차량 하차")
    m2 = folium.Map(location=center_hint, zoom_start=17, control_scale=False, zoom_control=True)
    add_carto_tile(m2, theme="positron")
    if not route_only:
        folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
        folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m2)
    draw_path(m2, drv2_coords, color="#9467bd", use_ant=True)
    if not route_only:
        add_fixed_safety(m2, apt)
        add_legend(m2)
    st_folium(m2, use_container_width=True, height=map_height)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 골든타임·생존 인원 분석 ────────────────────────────────────────────────────
st.markdown("### 🚑 골든타임 감소 및 생존 인원 추정")
colA, colB, colC = st.columns(3)
with colA:
    golden_time = st.number_input("골든타임 기준(분)", min_value=1.0, max_value=15.0, value=4.0, step=0.5)
with colB:
    survival_gain_per_min = st.number_input("1분 단축 시 생존율 개선(%p)", min_value=0.0, max_value=20.0, value=8.0, step=0.5) / 100.0
with colC:
    annual_cases = st.number_input("연간 관련 출동 건수(건)", min_value=0, max_value=200000, value=7648, step=100)

time_ratio = (improvement_min / golden_time) if golden_time > 0 else 0
survival_increase_rate = survival_gain_per_min * max(improvement_min, 0)
saved_people = int(annual_cases * survival_increase_rate)

st.markdown(
    f"개선된 경로로 평균 이동 시간이 "
    f"<span style='color:var(--blue)'><strong>{improvement_min:.2f}분 단축</strong></span>되었다. "
    f"골든타임 <span style='color:var(--blue)'><strong>{golden_time:.1f}분 대비 단축 비율은 {(time_ratio*100):.1f}%</strong></span>이다. "
    f"1분 단축당 생존율 개선을 <span style='color:var(--blue)'><strong>{survival_increase_rate*100:.1f}%p</strong></span>로 보았을 때, "
    f"연간 출동 <span style='color:var(--blue)'><strong>{annual_cases:,}건 기준으로 추가 생존 가능 인원은 약 {saved_people:,}명으로 추정</strong></span>된다.",
    unsafe_allow_html=True
)

# 레퍼런스
st.markdown(
    """
    <small style='color:gray'>
    <strong>참고문헌</strong><br>
    1. American Heart Association (2020). <em>2020 American Heart Association Guidelines for Cardiopulmonary Resuscitation and Emergency Cardiovascular Care</em>. Circulation, 142(16_suppl_2), S337–S357.<br>
    2. Larsen, M. P., Eisenberg, M. S., Cummins, R. O., & Hallstrom, A. P. (1993). Predicting survival from out-of-hospital cardiac arrest: a graphic model. <em>Annals of Emergency Medicine</em>, 22(11), 1652–1658.<br>
    3. 소방청 (2024). <em>2023년 소방활동 통계연보</em>. 세종: 소방청.
    </small>
    """,
    unsafe_allow_html=True
)
