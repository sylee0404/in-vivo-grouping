import io
import numpy as np
import pandas as pd
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="실험동물 von Frey 층화 & 체중 균등 배정 도구", layout="wide")

st.title("🧪 In Vivo 실험동물 그룹핑 도구 (von Frey 3단계 층화 & 체중 균등화)")
st.markdown(
    """
    **배정 방식 안내:**
    * **von Frey:** 전체 개체를 **Low / Middle / High** 3개 구간으로 균등 분할하여 각 시험군에 고르게 분배합니다.
    * **체중(Body Weight):** 각 등급별로 체중 편차를 상쇄하도록 교차 배정하여 **최종 체중 평균을 균일하게** 맞춥니다.
    """
)

# 1. 파일 업로더
uploaded_file = st.file_uploader("실험 데이터 엑셀 파일(.xlsx, .xls)을 올려주세요", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # 'bodyweight' 시트 자동 선택
        default_sheet_idx = 0
        for i, s_name in enumerate(sheet_names):
            if "bodyweight" in s_name.lower():
                default_sheet_idx = i
                break
                
        selected_sheet = st.selectbox("분석할 시트를 선택하세요", sheet_names, index=default_sheet_idx)
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        
        st.subheader("📂 업로드된 데이터 미리보기 (상위 5행)")
        st.dataframe(df.head(5), use_container_width=True)
        
        cols = list(df.columns)
        
        # 컬럼 자동 매칭
        vf_default = next((c for c in cols if "von" in c.lower() or "vf" in c.lower() or "frey" in c.lower()), cols[0])
        bw_default = next((c for c in cols if "weight" in c.lower() or "bw" in c.lower() or "몸무게" in c.lower() or "체중" in c.lower()), cols[1] if len(cols) > 1 else cols[0])
        
        st.markdown("#### ⚙️ 분석 지표 컬럼 매칭")
        c1, c2 = st.columns(2)
        with c1:
            vf_col = st.selectbox("von Frey (통증 역치 - Low/Mid/High 분할) 컬럼", cols, index=cols.index(vf_default))
        with c2:
            bw_col = st.selectbox("Bodyweight (체중 - 평균 균등화) 컬럼", cols, index=cols.index(bw_default))
            
        st.markdown("#### 👥 그룹 설정")
        g_col1, g_col2 = st.columns([1, 3])
        
        with g_col1:
            num_groups = st.number_input("나눌 그룹 수", min_value=2, max_value=30, value=7, step=1)
            
        with g_col2:
            default_names = ["Vehicle"] + [f"Drug_{chr(65+i)}" for i in range(num_groups - 2)] + ["Normal"] if num_groups >= 2 else ["Group 1", "Group 2"]
            default_names_str = ", ".join(default_names[:num_groups])
            
            group_names_input = st.text_input(
                "그룹 이름 (쉼표 ','로 구분하여 입력)",
                value=default_names_str,
                help="원하는 그룹명을 쉼표로 구분해 입력하세요."
            )

        parsed_names = [name.strip() for name in group_names_input.split(",") if name.strip()]
        group_names = []
        for i in range(num_groups):
            if i < len(parsed_names):
                group_names.append(parsed_names[i])
            else:
                group_names.append(f"Group {i+1}")

        st.caption(f"📌 최종 적용 그룹 목록 ({num_groups}개): {' | '.join(group_names)}")

        if st.button("🚀 von Frey 층화 & 체중 균등 배정 실행", type="primary"):
            # 데이터 정제
            work_df = df.dropna(subset=[vf_col, bw_col]).copy()
            work_df[vf_col] = pd.to_numeric(work_df[vf_col], errors='coerce')
            work_df[bw_col] = pd.to_numeric(work_df[bw_col], errors='coerce')
            work_df = work_df.dropna(subset=[vf_col, bw_col])
            
            total_n = len(work_df)
            if total_n < num_groups:
                st.error(f"유효 데이터 수({total_n}개)가 설정한 그룹 수({num_groups}개)보다 적습니다.")
            else:
                # 1. von Frey 순위 기준 Low / Middle / High 3분할
                ranks = work_df[vf_col].rank(method='first', ascending=True)
                work_df['VF_Tier'] = pd.qcut(ranks, q=3, labels=['Low', 'Middle', 'High'])
                
                # 티어별 기준 수치 확인
                tier_ranges = {}
                for tier in ['Low', 'Middle', 'High']:
                    sub = work_df[work_df['VF_Tier'] == tier][vf_col]
                    tier_ranges[tier] = f"{sub.min():.2f} ~ {sub.max():.2f}"
                
                # 2. 동적 체중 균등 배정 (Stratified Greedy Allocation)
                group_members = {i: [] for i in range(num_groups)}
                group_tier_counts = {i: {'Low': 0, 'Middle': 0, 'High': 0} for i in range(num_groups)}
                group_bw_sum = {i: 0.0 for i in range(num_groups)}
                
                # 각 티어별(High -> Middle -> Low)로 순차 배정
                for tier in ['High', 'Middle', 'Low']:
                    tier_df = work_df[work_df['VF_Tier'] == tier].sort_values(by=bw_col, ascending=False)
                    
                    for _, animal in tier_df.iterrows():
                        # 현재 해당 티어를 가장 적게 받은 그룹들 추출
                        min_tier_count = min(group_tier_counts[g][tier] for g in range(num_groups))
                        candidate_groups = [g for g in range(num_groups) if group_tier_counts[g][tier] == min_tier_count]
                        
                        # 후보 그룹 중 현재 누적 체중이 가장 낮은 그룹에 배정
                        chosen_group = min(candidate_groups, key=lambda g: group_bw_sum[g])
                        
                        # 할당 및 상태 업데이트
                        animal_dict = animal.to_dict()
                        animal_dict['Assigned_Group'] = group_names[chosen_group]
                        group_members[chosen_group].append(animal_dict)
                        group_tier_counts[chosen_group][tier] += 1
                        group_bw_sum[chosen_group] += animal[bw_col]
                
                # 3. 결과 테이블 생성
                final_rows = []
                summary_data = []
                
                for i in range(num_groups):
                    g_list = group_members[i]
                    g_df = pd.DataFrame(g_list)
                    final_rows.append(g_df)
                    
                    g_name = group_names[i]
                    summary_data.append({
                        'Group Name': g_name,
                        '총 개체수(N)': len(g_df),
                        'Low (VF)': group_tier_counts[i]['Low'],
                        'Middle (VF)': group_tier_counts[i]['Middle'],
                        'High (VF)': group_tier_counts[i]['High'],
                        '체중 평균 (g)': round(g_df[bw_col].mean(), 2),
                        '체중 표준편차': round(g_df[bw_col].std(), 2) if len(g_df) > 1 else 0.0,
                        'von Frey 평균': round(g_df[vf_col].mean(), 2),
                        'von Frey 표준편차': round(g_df[vf_col].std(), 2) if len(g_df) > 1 else 0.0
                    })
                    
                final_df = pd.concat(final_rows, ignore_index=True)
                summary_df = pd.DataFrame(summary_data)
                
                st.success("✅ von Frey 3등급 분할 및 체중 균등 배정이 완료되었습니다!")
                
                # von Frey 등급 기준 안내 카드
                st.info(
                    f"💡 **von Frey 등급 기준 범위:** "
                    f"Low ({tier_ranges['Low']}) | Middle ({tier_ranges['Middle']}) | High ({tier_ranges['High']})"
                )
                
                # 요약 통계 테이블
                st.subheader(f"📊 {num_groups}개 그룹별 요약 통계")
                st.dataframe(summary_df, use_container_width=True)
                
                # 시각화 그래프
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.markdown("##### ⚖️ 그룹별 체중 평균 (균등화 검증)")
                    st.bar_chart(summary_df.set_index('Group Name')['체중 평균 (g)'])
                
                with col_chart2:
                    st.markdown("##### 🎯 그룹별 von Frey 등급 분포 (Low / Mid / High)")
                    chart_df = summary_df.set_index('Group Name')[['Low (VF)', 'Middle (VF)', 'High (VF)']]
                    st.bar_chart(chart_df)
                
                # 개체별 전체 배정 상세 테이블
                st.subheader("📋 개체별 배정 상세 결과")
                # 컬럼 순서 정리
                display_cols = ['Assigned_Group', 'VF_Tier', vf_col, bw_col] + [c for c in final_df.columns if c not in ['Assigned_Group', 'VF_Tier', vf_col, bw_col]]
                st.dataframe(final_df[display_cols], use_container_width=True)
                
                # 엑셀 다운로드 파일 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, sheet_name='그룹별_통계요약', index=False)
                    final_df[display_cols].to_excel(writer, sheet_name='개체별_배정결과', index=False)
                excel_bytes = output.getvalue()
                
                st.download_button(
                    label="📥 최적화 배정 결과 엑셀 다운로드 (.xlsx)",
                    data=excel_bytes,
                    file_name=f"Stratified_Grouping_Result_{num_groups}Groups.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"파일을 처리하는 중 오류가 발생했습니다: {e}")
