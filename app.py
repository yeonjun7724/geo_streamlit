import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(
    page_title="하남시 MAT 기반 아파트 네비게이션",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바
with st.sidebar:
    st.header("📍 연구지역 설정")
    
    # 아파트 단지 선택
    apartment_complex = st.selectbox(
        "아파트 단지 선택",
        [
            "미사강변 한강센트럴파크",
            "미사강변 신리마을",
            "고덕 래미안",
            "고덕 그라시움"
        ]
    )
    
    # 목적지 선택
    destination_type = st.selectbox(
        "목적지 유형",
        ["동 출입구", "소화전", "관리사무소", "지하주차장", "놀이터"]
    )
    
    # 시나리오 선택
    scenario = st.radio(
        "비교 시나리오",
        ["일반 상황", "긴급 상황 (소방)", "긴급 상황 (구급)"]
    )
    
    st.divider()
    
    # 현재 통계
    st.subheader("📊 현재 성과")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("서비스 지역", "하남시", "1개 시")
        st.metric("등록 단지", "342개", "+12개")
    
    with col2:
        st.metric("평균 시간단축", "23%", "+2.1%")
        st.metric("정확도", "97.8%", "+0.5%")

# 메인 영역
st.title("🏢 하남시 MAT 기반 아파트 네비게이션")
st.markdown("벡터 중축 변환(MAT) 알고리즘을 활용한 아파트 단지 내 정밀 네비게이션")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["🔄 AS IS vs TO BE", "📊 효과 분석", "🗺️ 실시간 시뮬레이션"])

# 하남시 아파트 단지 데이터
hanam_apartments = {
    "미사강변 한강센트럴파크": {
        "center": [37.5621, 127.1734],
        "entrance": [37.5619, 127.1732],
        "buildings": [
            {"name": "101동", "lat": 37.5623, "lon": 127.1736},
            {"name": "102동", "lat": 37.5625, "lon": 127.1738},
            {"name": "103동", "lat": 37.5627, "lon": 127.1740}
        ],
        "facilities": [
            {"name": "소화전 #1", "lat": 37.5622, "lon": 127.1735, "type": "hydrant"},
            {"name": "관리사무소", "lat": 37.5620, "lon": 127.1733, "type": "office"}
        ]
    },
    "미사강변 신리마을": {
        "center": [37.5645, 127.1689],
        "entrance": [37.5643, 127.1687],
        "buildings": [
            {"name": "201동", "lat": 37.5647, "lon": 127.1691},
            {"name": "202동", "lat": 37.5649, "lon": 127.1693}
        ],
        "facilities": [
            {"name": "소화전 #2", "lat": 37.5646, "lon": 127.1690, "type": "hydrant"}
        ]
    },
    "고덕 래미안": {
        "center": [37.5498, 127.1542],
        "entrance": [37.5496, 127.1540],
        "buildings": [
            {"name": "301동", "lat": 37.5500, "lon": 127.1544},
            {"name": "302동", "lat": 37.5502, "lon": 127.1546}
        ],
        "facilities": [
            {"name": "소화전 #3", "lat": 37.5499, "lon": 127.1543, "type": "hydrant"}
        ]
    },
    "고덕 그라시움": {
        "center": [37.5521, 127.1578],
        "entrance": [37.5519, 127.1576],
        "buildings": [
            {"name": "401동", "lat": 37.5523, "lon": 127.1580}
        ],
        "facilities": [
            {"name": "관리사무소", "lat": 37.5520, "lon": 127.1577, "type": "office"}
        ]
    }
}

with tab1:
    st.subheader("🔄 기존 네비게이션 vs MAT 기반 네비게이션")
    
    col1, col2 = st.columns(2)
    
    # 선택된 아파트 단지 데이터
    selected_apt = hanam_apartments[apartment_complex]
    
    with col1:
        st.markdown("#### ❌ AS IS - 기존 네비게이션")
        
        # AS IS 지도 (정문까지만)
        m_as_is = folium.Map(
            location=selected_apt["center"],
            zoom_start=17,
            tiles="OpenStreetMap"
        )
        
        # 정문 마커만 표시
        folium.Marker(
            location=selected_apt["entrance"],
            popup="아파트 정문 (기존 네비 종료 지점)",
            icon=folium.Icon(color="red", icon="stop")
        ).add_to(m_as_is)
        
        # 기존 경로 (정문까지)
        folium.PolyLine(
            locations=[
                [37.5600, 127.1700],  # 출발지 (임의)
                selected_apt["entrance"]
            ],
            color="red",
            weight=3,
            opacity=0.7,
            popup="기존 네비 경로"
        ).add_to(m_as_is)
        
        st_folium(m_as_is, width=350, height=300)
        
        st.error("🚫 정문까지만 안내 가능")
        st.markdown("""
        - 목적지: 아파트 정문
        - 단지 내 길찾기: 불가능
        - 추가 도보시간: 3-5분
        - 긴급상황 대응: 제한적
        """)
    
    with col2:
        st.markdown("#### ✅ TO BE - MAT 기반 네비게이션")
        
        # TO BE 지도 (동 출입구까지)
        m_to_be = folium.Map(
            location=selected_apt["center"],
            zoom_start=17,
            tiles="OpenStreetMap"
        )
        
        # 모든 건물과 시설 표시
        for building in selected_apt["buildings"]:
            folium.Marker(
                location=[building["lat"], building["lon"]],
                popup=f"{building['name']} 출입구",
                icon=folium.Icon(color="blue", icon="home")
            ).add_to(m_to_be)
        
        for facility in selected_apt["facilities"]:
            color = "red" if facility["type"] == "hydrant" else "green"
            icon = "tint" if facility["type"] == "hydrant" else "info-sign"
            folium.Marker(
                location=[facility["lat"], facility["lon"]],
                popup=facility["name"],
                icon=folium.Icon(color=color, icon=icon)
            ).add_to(m_to_be)
        
        # MAT 기반 경로 (동 출입구까지)
        if selected_apt["buildings"]:
            target_building = selected_apt["buildings"][0]
            folium.PolyLine(
                locations=[
                    [37.5600, 127.1700],  # 출발지 (임의)
                    selected_apt["entrance"],
                    [target_building["lat"], target_building["lon"]]
                ],
                color="blue",
                weight=4,
                opacity=0.8,
                popup="MAT 기반 정밀 경로"
            ).add_to(m_to_be)
        
        st_folium(m_to_be, width=350, height=300)
        
        st.success("✅ 동 출입구까지 정확한 안내")
        st.markdown("""
        - 목적지: 101동 출입구
        - 단지 내 상세 안내: 가능
        - 시간 단축: 평균 23%
        - 긴급상황 대응: 최적화
        """)
    
    # 비교 통계
    st.divider()
    st.subheader("📈 성능 비교")
    
    comparison_data = pd.DataFrame({
        "구분": ["도달시간", "정확도", "사용자 만족도", "긴급대응"],
        "AS IS": [5.2, 75.3, 3.2, 6.8],
        "TO BE": [4.0, 97.8, 4.8, 4.4],
        "개선율": [23, 30, 50, 35]
    })
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("평균 도달시간", "4.0분", "-1.2분 (23%↓)")
    with col2:
        st.metric("목적지 정확도", "97.8%", "+22.5%p")
    with col3:
        st.metric("사용자 만족도", "4.8/5.0", "+1.6점")
    with col4:
        st.metric("긴급대응시간", "4.4분", "-2.4분 (35%↓)")

with tab2:
    st.subheader("📊 MAT 알고리즘 효과 분석")
    
    # 시간대별 효과 차트
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 시간대별 네비게이션 성능")
        
        time_data = pd.DataFrame({
            "시간대": ["06-09", "09-12", "12-15", "15-18", "18-21", "21-24"],
            "AS IS": [5.8, 4.9, 4.7, 6.2, 5.5, 4.3],
            "TO BE": [4.2, 3.8, 3.6, 4.8, 4.1, 3.4]
        })
        
        fig = px.line(
            time_data, 
            x="시간대", 
            y=["AS IS", "TO BE"],
            title="평균 도달시간 (분)",
            markers=True
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### 아파트 단지별 개선 효과")
        
        apt_data = pd.DataFrame({
            "아파트": ["한강센트럴", "신리마을", "고덕래미안", "고덕그라시움"],
            "시간단축률": [25, 23, 28, 19],
            "정확도개선": [22, 28, 24, 26]
        })
        
        fig2 = px.bar(
            apt_data,
            x="아파트",
            y=["시간단축률", "정확도개선"],
            title="단지별 개선 효과 (%)",
            barmode="group"
        )
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)
    
    # 긴급상황 시나리오
    st.divider()
    st.markdown("#### 🚨 긴급상황 대응 효과")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**화재 상황**")
        st.metric("소방차 도달시간", "3.2분", "-2.1분")
        st.metric("소화전 접근시간", "45초", "-1.3분")
    
    with col2:
        st.markdown("**응급의료 상황**")
        st.metric("구급차 도달시간", "3.8분", "-1.8분")
        st.metric("환자 이송시간", "2.1분", "-0.9분")
    
    with col3:
        st.markdown("**치안 상황**")
        st.metric("경찰차 도달시간", "4.1분", "-1.5분")
        st.metric("현장 접근시간", "1.2분", "-0.7분")

with tab3:
    st.subheader("🗺️ 실시간 네비게이션 시뮬레이션")
    
    # 시뮬레이션 컨트롤
    col1, col2, col3 = st.columns(3)
    
    with col1:
        simulation_mode = st.selectbox(
            "시뮬레이션 모드",
            ["일반 주행", "긴급 출동", "야간 운행"]
        )
    
    with col2:
        vehicle_type = st.selectbox(
            "차량 유형",
            ["일반 승용차", "소방차", "구급차", "경찰차"]
        )
    
    with col3:
        if st.button("▶️ 시뮬레이션 시작", type="primary"):
            st.success("시뮬레이션이 시작되었습니다!")
    
    # 통합 지도
    st.markdown("#### 📍 하남시 전체 아파트 단지 현황")
    
    # 하남시 전체 지도
    m_total = folium.Map(
        location=[37.5539, 127.1650],  # 하남시 중심
        zoom_start=14,
        tiles="OpenStreetMap"
    )
    
    # 모든 아파트 단지 표시
    colors = ["blue", "green", "red", "purple"]
    for i, (apt_name, apt_data) in enumerate(hanam_apartments.items()):
        color = colors[i % len(colors)]
        
        # 아파트 단지 중심점
        folium.Marker(
            location=apt_data["center"],
            popup=f"{apt_name}<br>등록 동수: {len(apt_data['buildings'])}개",
            icon=folium.Icon(color=color, icon="home")
        ).add_to(m_total)
        
        # MAT 도로 중심선 (샘플)
        if apt_data["buildings"]:
            route = [apt_data["entrance"]]
            for building in apt_data["buildings"]:
                route.append([building["lat"], building["lon"]])
            
            folium.PolyLine(
                locations=route,
                color=color,
                weight=2,
                opacity=0.6,
                popup=f"{apt_name} MAT 경로"
            ).add_to(m_total)
    
    # 범례 정보
    legend_html = '''
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 200px; height: 120px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>아파트 단지</b></p>
    <p><i class="fa fa-circle" style="color:blue"></i> 한강센트럴파크</p>
    <p><i class="fa fa-circle" style="color:green"></i> 신리마을</p>
    <p><i class="fa fa-circle" style="color:red"></i> 고덕래미안</p>
    <p><i class="fa fa-circle" style="color:purple"></i> 고덕그라시움</p>
    </div>
    '''
    m_total.get_root().html.add_child(folium.Element(legend_html))
    
    st_folium(m_total, width=700, height=500)
    
    # 실시간 통계
    st.divider()
    st.markdown("#### 📈 실시간 서비스 현황")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("활성 사용자", "1,247명", "+156")
    with col2:
        st.metric("오늘 경로 안내", "3,482건", "+234")
    with col3:
        st.metric("평균 응답시간", "0.23초", "-0.02초")
    with col4:
        st.metric("시스템 가동률", "99.8%", "+0.1%")
    with col5:
        st.metric("긴급 출동 건수", "12건", "+3")

# 하단 정보
st.divider()
st.markdown("""
#### 📋 연구 정보
- **연구지역**: 경기도 하남시 (미사강변도시, 고덕신도시)
- **적용 기술**: 벡터 중축 변환(MAT) 알고리즘
- **데이터 출처**: 국토지리정보원, 하남시청, 주소정보기본도
- **업데이트**: 2024년 8월 기준
""")
