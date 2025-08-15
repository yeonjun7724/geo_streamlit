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
html, body, [data-testid="stAppViewContainer"] { color: var(--text) !important; }
[data-testid="stHeader"] { background: transparent !important; }
.main > div { padding-top: 0.6rem !important; }

/* 전체 레이아웃 */
.block-container {
    max-width: 100%;
    padding-left: 2rem;
    padding-right: 2rem;
    margin: 0 auto;
}

/* 큰 제목 */
.app-title {
    font-size: 3.2rem; font-weight: 900; letter-spacing: -0.02em;
    margin: 0.2rem 0 0.8rem 0; text-align: center;
}

/* 섹션 간 여백 */
.section { margin: 1.8rem 0; }

/* 셀렉트박스 가로폭 100% */
.stSelectbox, .stSelectbox > div { width: 100% !important; }
.stSelectbox div[role="combobox"] { width: 100% !important; }

/* KPI 기본: 블랙 */
[data-testid="stMetric"] { text-align: center; }
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-weight: 600; }
[data-testid="stMetricValue"]  { color: var(--text) !important; }

/* 커스텀 KPI (블랙) : AS-IS 차량, AS-IS 도보, TO-BE 차량 공통 */
.metric-plain { text-align:center; }
.metric-plain .label { color: var(--muted); font-weight: 600; margin-bottom: 4px; }
.metric-plain .value { font-size: 2rem; font-weight: 700; line-height: 1.1; color: var(--text); }

/* 커스텀 KPI (파랑) : 총 개선 */
.metric-wrap { text-align:center; }
.metric-wrap .label { color: var(--muted); font-weight: 600; margin-bottom: 4px; }
.metric-wrap .value { font-size: 2rem; font-weight: 700; line-height: 1.1; color: var(--blue); }
.metric-wrap .delta {
    display:inline-block; margin-top: 6px; padding: 2px 8px; font-size: 0.85rem;
    background: var(--blue-weak); color: var(--blue); border-radius: 999px;
}

/* 지도 섹션 제목 */
h4 { text-align: left; margin-bottom: 0.6rem; }

/* 지도 attribution/스케일바 숨김 */
.leaflet-control-attribution { display: none; }
.leaflet-control-scale { display: none !important; }

/* 구분선 */
.divider { height: 1px; background: #e5e7eb; margin: 1.4rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Mapbox 토큰 ─────────────────────────────────────────────────────────────────
MAPBOX_TOKEN = st.secrets.get("MAPBOX_TOKEN") or os.getenv("MAPBOX_TOKEN", "")

# ── 데이터 (출발지 + 아파트 + 경로 인근 하드코딩 안전시설) ──────────────────────
ORIGINS = {
    "하남소방서": [37.539826, 127.220661],
    "미사강변119안전센터": [37.566902, 127.185298],
}

# 각 단지: gate↔front(도보 경로)와 front 인근에 30m 내외로 배치한 좌표들
APARTMENTS = {
    "미사강변센트럴풍경채": {
        "center": [37.556591, 127.183081],
        "gate":   [37.556844, 127.181887],
        "front":  [37.557088, 127.183036],
        "hydrants": [  # 소화전(3~4)
            [37.55695, 127.18220],
            [37.55702, 127.18255],
            [37.55706, 127.18285],
            [37.55710, 127.18305],
        ],
        "fire_lanes": [  # 소방차 전용구역(3)
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

# ── 라우팅 함수 ─────────────────────────────────────────────────────────────────
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

# ── CARTO 타일 ──────────────────────────────────────────────────────────────────
def add_carto_tile(m: folium.Map, theme="positron"):
    if theme == "dark_matter":
        folium.TileLayer(tiles="CartoDB Dark_Matter", control=False).add_to(m)
    else:
        folium.TileLayer(tiles="CartoDB Positron", control=False).add_to(m)
    return m

# ── 범례(원 아이콘) ────────────────────────────────────────────────────────────
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

# ── 안전시설 표시 (하드코딩 좌표 사용) ──────────────────────────────────────────
def add_fixed_safety(m: folium.Map, apt_info: dict):
    # 소화전
    for i, (lat, lon) in enumerate(apt_info.get("hydrants", []), 1):
        folium.Marker(
            [lat, lon],
            tooltip=f"소화전 #{i}",
            icon=folium.Icon(color="red", icon="fire-extinguisher", prefix="fa")
        ).add_to(m)
    # 소방차 전용구역
    for i, (lat, lon) in enumerate(apt_info.get("fire_lanes", []), 1):
        folium.Marker(
            [lat, lon],
            tooltip=f"소방차 전용구역 #{i}",
            icon=folium.Icon(color="orange", icon="truck", prefix="fa")
        ).add_to(m)

# ── 제목 ───────────────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">🏢 하남시 벡터 중축 변환(MAT) 기반 아파트 경로 안내 서비스</div>', unsafe_allow_html=True)

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

drv1_coords, drv1_km, drv1_min, _ = mapbox_route([origin, apt_gate], profile="driving")
walk1_coords, walk1_km, walk1_min, _ = mapbox_route([apt_gate, apt_front], profile="walking")
drv2_coords, drv2_km, drv2_min, _ = mapbox_route([origin, apt_front], profile="driving")

asis_total = (drv1_min or 0) + (walk1_min or 0)
improvement_min = asis_total - (drv2_min or 0)
improvement_pct = (improvement_min / asis_total * 100) if asis_total > 0 else 0

# ── KPI: 세 개 모두 커스텀(블랙), "총 개선"만 파랑 ────────────────────────────
k1, k2, k3, k4 = st.columns(4)

k1.markdown(
    f"""
    <div class="metric-plain">
      <div class="label">AS-IS 차량</div>
      <div class="value">{(drv1_min or 0):.2f}분</div>
    </div>
    """,
    unsafe_allow_html=True
)

k2.markdown(
    f"""
    <div class="metric-plain">
      <div class="label">AS-IS 도보</div>
      <div class="value">{(walk1_min or 0):.2f}분</div>
    </div>
    """,
    unsafe_allow_html=True
)

k3.markdown(
    f"""
    <div class="metric-plain">
      <div class="label">TO-BE 차량</div>
      <div class="value">{(drv2_min or 0):.2f}분</div>
    </div>
    """,
    unsafe_allow_html=True
)

impr_min_txt = f"{(improvement_min):.2f}분"
impr_pct_txt = f"{(improvement_pct):.1f}%"
k4.markdown(
    f"""
    <div class="metric-wrap">
      <div class="label">총 개선</div>
      <div class="value">{impr_min_txt}</div>
      <div class="delta">+ {impr_pct_txt}</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── 지도(2분할) ────────────────────────────────────────────────────────────────
map_height = 640
left, right = st.columns(2)

with left:
    st.markdown("#### AS-IS — 정문에서 차량 하차 + 잔여 도보")
    m1 = folium.Map(location=center_hint, zoom_start=17, control_scale=False, zoom_control=True)
    add_carto_tile(m1, theme="positron")
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m1)
    folium.Marker(apt_gate, popup="정문", icon=folium.Icon(color="red", icon="flag")).add_to(m1)
    folium.Marker(apt_front, popup="아파트 동 앞", icon=folium.Icon(color="green", icon="home")).add_to(m1)
    if drv1_coords:
        AntPath(drv1_coords, color="#1f77b4", weight=5, opacity=0.9, delay=800).add_to(m1)
    if walk1_coords:
        AntPath(walk1_coords, color="#2ca02c", weight=5, opacity=0.9, dash_array=[6, 8], delay=900).add_to(m1)
    add_fixed_safety(m1, apt)   # 경로 인근으로 하드코딩해둔 좌표
    add_legend(m1)
    st_folium(m1, use_container_width=True, height=map_height)

with right:
    st.markdown("#### TO-BE — 아파트 동 앞에서 차량 하차")
    m2 = folium.Map(location=center_hint, zoom_start=17, control_scale=False, zoom_control=True)
    add_carto_tile(m2, theme="positron")
    folium.Marker(origin, popup="출발지", icon=folium.Icon(color="gray", icon="car")).add_to(m2)
    folium.Marker(apt_front, popup="아파트 앞", icon=folium.Icon(color="green", icon="home")).add_to(m2)
    if drv2_coords:
        AntPath(drv2_coords, color="#9467bd", weight=6, opacity=0.95, delay=800).add_to(m2)
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

# 레퍼런스 추가
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





