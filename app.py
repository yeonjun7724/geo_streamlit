import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import plotly.express as px
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
# Data
# ──────────────────────────────────────────────────────────────────────────────
HANAM_APARTMENTS = {
    "미사강변 한강센트럴파크": {
        "center": [37.5621, 127.1734],
        "entrance": [37.5619, 127.1732],
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
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📍 연구지역 설정")

    apartment_complex = st.selectbox(
        "아파트 단지 선택",
        list(HANAM_APARTMENTS.keys()),
        index=0,
    )

    destination_type = st.selectbox(
        "목적지 유형",
        ["동 출입구", "소화전", "관리사무소", "지하주차장", "놀이터"],
        index=0,
    )

    scenario = st.radio(
        "비교 시나리오",
        ["일반 상황", "긴급 상황 (소방)", "긴급 상황 (구급)"],
        index=0,
    )

    st.divider()

    st.subheader("📊 현재 성과")
    c1, c2 = st.columns(2)
    with c1:
        st.metric("서비스 지역", "하남시", "1개 시")
        st.metric("등록 단지", "342개", "+12개")
    with c2:
        st.metric("평균 시간단축", "23%", "+2.1%")
        st.metric("정확도", "97.8%", "+0.5%")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_as_is_map(apt: dict, route_color: str) -> folium.Map:
    m = folium.Map(location=apt["center"], zoom_start=17, tiles="OpenStreetMap")

    folium.Marker(
        location=apt["entrance"],
        popup="아파트 정문 (기존 네비 종료 지점)",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    folium.PolyLine(
        locations=[
            [37.5600, 127.1700],  # 샘플 출발지
            apt["entrance"],
        ],
        color=route_color,
        weight=3,
        opacity=0.7,
        popup="기존 네비 경로",
    ).add_to(m)

    return m


def make_to_be_map(apt: dict, route_color: str, icon_color: str) -> folium.Map:
    m = folium.Map(location=apt["center"], zoom_start=17, tiles="OpenStreetMap")

    # 건물 출입구
    for b in apt["buildings"]:
        folium.Marker(
            location=[b["lat"], b["lon"]],
            popup=f"{b['name']} 출입구",
            icon=folium.Icon(color=icon_color, icon="home"),
        ).add_to(m)

    # 시설물
    for f in apt["facilities"]:
        color = "red" if f["type"] == "hydrant" else "green"
        icon = "tint" if f["type"] == "hydrant" else "info-sign"
        folium.Marker(
            location=[f["lat"], f["lon"]],
            popup=f["name"],
            icon=folium.Icon(color=color, icon=icon),
        ).add_to(m)

    # MAT 기반 경로 (샘플 경로: 정문 → 첫 번째 동)
    if apt["buildings"]:
        target = apt["buildings"][0]
        folium.PolyLine(
            locations=[
                [37.5600, 127.1700],  # 샘플 출발지
                apt["entrance"],
                [target["lat"], target["lon"]],
            ],
            color=route_color,
            weight=4,
            opacity=0.85,
            popup="MAT 기반 정밀 경로",
        ).add_to(m)

    return m


# ──────────────────────────────────────────────────────────────────────────────
# Main Title
# ──────────────────────────────────────────────────────────────────────────────
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")
st.caption("벡터 중축 변환(MAT) 알고리즘을 활용한 아파트 단지 내 정밀 네비게이션")

# Tabs
as_is_tab, effect_tab, sim_tab = st.tabs(["🔄 AS IS vs TO BE", "📊 효과 분석", "🗺️ 실시간 시뮬레이션"])

# Selected apartment
selected = HANAM_APARTMENTS[apartment_complex]
style = SCENARIO_STYLES[scenario]

# ──────────────────────────────────────────────────────────────────────────────
# Tab 1: AS-IS vs TO-BE
# ──────────────────────────────────────────────────────────────────────────────
with as_is_tab:
    st.subheader("🔄 기존 네비게이션 vs MAT 기반 네비게이션")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### ❌ AS IS - 기존 네비게이션")
        m1 = make_as_is_map(selected, style["route_color"]) 
        st_folium(m1, use_container_width=True, height=320)
        st.error("정문까지만 안내 가능")
        st.markdown(
            """
            • 목적지: 아파트 정문  
            • 단지 내 길찾기: 불가능  
            • 추가 도보시간: 3–5분  
            • 긴급상황 대응: 제한적
            """
        )

    with c2:
        st.markdown("#### ✅ TO BE - MAT 기반 네비게이션")
        m2 = make_to_be_map(selected, style["route_color"], style["icon_color"]) 
        st_folium(m2, use_container_width=True, height=320)
        st.success("동 출입구까지 정확한 안내")
        # 목적지 유형 안내표시
        st.markdown(
            f"""
            • 선택된 목적지 유형: **{destination_type}**  
            • 목표: 첫 번째 동 출입구 기준 안내  
            • 시간 단축: 평균 23%  
            • 긴급상황 대응: 최적화
            """
        )

    st.divider()
    st.subheader("📈 성능 비교")

    comp_df = pd.DataFrame(
        {
            "구분": ["도달시간", "정확도", "사용자 만족도", "긴급대응"],
            "AS IS": [5.2, 75.3, 3.2, 6.8],
            "TO BE": [4.0, 97.8, 4.8, 4.4],
            "개선율": [23, 30, 50, 35],
        }
    )

    m_c1, m_c2, m_c3, m_c4 = st.columns(4)
    with m_c1:
        st.metric("평균 도달시간", "4.0분", "-1.2분 (23%↓)")
    with m_c2:
        st.metric("목적지 정확도", "97.8%", "+22.5%p")
    with m_c3:
        st.metric("사용자 만족도", "4.8/5.0", "+1.6점")
    with m_c4:
        st.metric("긴급대응시간", "4.4분", "-2.4분 (35%↓)")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 2: 효과 분석
# ──────────────────────────────────────────────────────────────────────────────
with effect_tab:
    st.subheader("📊 MAT 알고리즘 효과 분석")

    e1, e2 = st.columns(2)

    with e1:
        st.markdown("#### 시간대별 네비게이션 성능")
        time_df = pd.DataFrame(
            {
                "시간대": ["06-09", "09-12", "12-15", "15-18", "18-21", "21-24"],
                "AS IS": [5.8, 4.9, 4.7, 6.2, 5.5, 4.3],
                "TO BE": [4.2, 3.8, 3.6, 4.8, 4.1, 3.4],
            }
        )
        fig = px.line(time_df, x="시간대", y=["AS IS", "TO BE"], title="평균 도달시간 (분)", markers=True)
        fig.update_layout(height=320, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    with e2:
        st.markdown("#### 아파트 단지별 개선 효과")
        apt_df = pd.DataFrame(
            {
                "아파트": ["한강센트럴", "신리마을", "고덕래미안", "고덕그라시움"],
                "시간단축률": [25, 23, 28, 19],
                "정확도개선": [22, 28, 24, 26],
            }
        )
        fig2 = px.bar(apt_df, x="아파트", y=["시간단축률", "정확도개선"], title="단지별 개선 효과 (%)", barmode="group")
        fig2.update_layout(height=320, legend_title_text="")
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("#### 🚨 긴급상황 대응 효과")

    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown("**화재 상황**")
        st.metric("소방차 도달시간", "3.2분", "-2.1분")
        st.metric("소화전 접근시간", "45초", "-1.3분")
    with k2:
        st.markdown("**응급의료 상황**")
        st.metric("구급차 도달시간", "3.8분", "-1.8분")
        st.metric("환자 이송시간", "2.1분", "-0.9분")
    with k3:
        st.markdown("**치안 상황**")
        st.metric("경찰차 도달시간", "4.1분", "-1.5분")
        st.metric("현장 접근시간", "1.2분", "-0.7분")

# ──────────────────────────────────────────────────────────────────────────────
# Tab 3: 실시간 시뮬레이션
# ──────────────────────────────────────────────────────────────────────────────
with sim_tab:
    st.subheader("🗺️ 실시간 네비게이션 시뮬레이션")

    s1, s2, s3 = st.columns(3)
    with s1:
        simulation_mode = st.selectbox("시뮬레이션 모드", ["일반 주행", "긴급 출동", "야간 운행"], index=0)
    with s2:
        vehicle_type = st.selectbox("차량 유형", ["일반 승용차", "소방차", "구급차", "경찰차"], index=0)
    with s3:
        if st.button("▶️ 시뮬레이션 시작", type="primary"):
            st.success("시뮬레이션이 시작되었습니다!")

    st.markdown("#### 📍 하남시 전체 아파트 단지 현황")

    # 전체 지도
    m_total = folium.Map(location=[37.5539, 127.1650], zoom_start=14, tiles="OpenStreetMap")

    colors = ["blue", "green", "red", "purple"]
    for i, (apt_name, apt) in enumerate(HANAM_APARTMENTS.items()):
        color = colors[i % len(colors)]

        folium.Marker(
            location=apt["center"],
            popup=f"{apt_name}<br>등록 동수: {len(apt['buildings'])}개",
            icon=folium.Icon(color=color, icon="home"),
        ).add_to(m_total)

        if apt["buildings"]:
            route = [apt["entrance"]] + [[b["lat"], b["lon"]] for b in apt["buildings"]]
            folium.PolyLine(
                locations=route,
                color=color,
                weight=2,
                opacity=0.6,
                popup=f"{apt_name} MAT 경로",
            ).add_to(m_total)

    # 간단한 범례
    legend_html = (
        """
        <div style="position: fixed; top: 10px; right: 10px; width: 200px; 
                    background-color: white; border: 1px solid #AAA; 
                    z-index: 9999; font-size: 14px; padding: 10px;">
          <p><b>아파트 단지</b></p>
          <p style=\"margin:0\"><span style=\"color:blue\">●</span> 한강센트럴파크</p>
          <p style=\"margin:0\"><span style=\"color:green\">●</span> 신리마을</p>
          <p style=\"margin:0\"><span style=\"color:red\">●</span> 고덕래미안</p>
          <p style=\"margin:0\"><span style=\"color:purple\">●</span> 고덕그라시움</p>
        </div>
        """
    )
    m_total.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m_total, use_container_width=True, height=480)

    st.divider()
    st.markdown("#### 📈 실시간 서비스 현황")

    a, b, c, d, e = st.columns(5)
    with a:
        st.metric("활성 사용자", "1,247명", "+156")
    with b:
        st.metric("오늘 경로 안내", "3,482건", "+234")
    with c:
        st.metric("평균 응답시간", "0.23초", "-0.02초")
    with d:
        st.metric("시스템 가동률", "99.8%", "+0.1%")
    with e:
        st.metric("긴급 출동 건수", "12건", "+3")

# ──────────────────────────────────────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f"""
    #### 📋 연구 정보
    - **연구지역**: 경기도 하남시 (미사강변도시, 고덕신도시)  
    - **적용 기술**: 벡터 중축 변환(MAT) 알고리즘  
    - **데이터 출처**: 국토지리정보원, 하남시청, 주소정보기본도  
    - **업데이트**: {datetime.now().strftime('%Y-%m-%d')} 기준
    """
)
