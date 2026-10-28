import io
import numpy as np
import pandas as pd
import streamlit as st

# 페이지 설정
st.set_page_config(page_title="실험동물 von Frey 층화 & 체중 균등 배정 도구", layout="wide")

st.title("🧪 In Vivo 실험동물 그룹핑 도구 (동일 N수 보장 & von Frey 층화)")
st.markdown(
    """
    **배정 알고리즘 원칙:**
    1. **동일 개체수($N$) 보장:** 모든 그룹에 정확히 동일한 수의 개체를 균등 배분합니다.
    2. **von Frey 3단계 균등 쿼터제:** 각 그룹마다 Low / Middle / High 개체가 동일한 비율로 들어갑니다.
    3. **체중(Body Weight) 평균 균일화:** 각 티어 내에서 체중 합이 낮은 그룹에 우선 배정하여 최종 평균을 맞춥니다.
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

        if st.button("🚀 동일 N수 그룹핑 실행", type="primary"):
            # 결측치 처리 및 수치형 변환
            work_df = df.dropna(subset=[vf_col, bw_col]).copy()
            work_df[vf_col] = pd.to_numeric(work_df[vf_col], errors='coerce')
            work_df[bw_col] = pd.to_numeric(work_df[bw_col], errors='coerce')
            work_df = work_df.dropna(subset=[vf_col, bw_col])
            
            total_n = len(work_df)
            if total_n < num_groups:
                st.error(f"유효 데이터 수({total_n}개)가 설정한 그룹 수({num_groups}개)보다 적습니다.")
            else:
                # 1. 그룹별 동일 N수 계산
                target_n = total_n // num_groups
                usable_total = target_n * num_groups
                remainder = total_n - usable_total
                
                # von Frey 기준으로 정렬
                work_df = work_df.sort_values(by=vf_col, ascending=True).reset_index(drop=True)
                
                # 잉여 개체(Spare) 처리: 극단치 위주로 제외하여 실험 정밀도 확보
                if remainder > 0:
                    trim_low = remainder // 2
                    trim_high = remainder - trim_low
                    spare_indices = list(range(trim_low)) + list(range(total_n - trim_high, total_n))
                    spare_df = work_df.iloc[spare_indices].copy()
                    spare_df['비고'] = '예비군(Spare) - 개체수 균등화를 위한 극단치 분리'
                    usable_df = work_df.drop(index=spare_indices).reset_index(drop=True)
                    st.warning(f"⚠️ 총 {total_n}마리 중 그룹별 동일 N수({target_n}마리)를 맞추기 위해 {usable_total}마리가 배정되었습니다. (나머지 {remainder}마리는 엑셀 '예비군_Spare' 시트에 보존됩니다.)")
                else:
                    usable_df = work_df.copy()
                    spare_df = pd.DataFrame()
                    st.success(f"✅ 총 {total_n}마리가 {num_groups}개 그룹에 각 {target_n}마리씩 동일하게 배정됩니다.")

                # 2. 각 그룹별 Low / Middle / High 목표 쿼터 산정
                k_low = target_n // 3
                k_mid = target_n // 3
                k_high = target_n // 3
                rem = target_n % 3
                if rem == 1:
                    k_mid += 1
                elif rem == 2:
                    k_high += 1
                    k_low += 1

                # usable_df 전체를 정확한 비율로 Low / Middle / High 슬라이싱
                n_low = num_groups * k_low
                n_mid = num_groups * k_mid
                
                usable_df['VF_Tier'] = ''
                usable_df.loc[:n_low - 1, 'VF_Tier'] = 'Low'
                usable_df.loc[n_low : n_low + n_mid - 1, 'VF_Tier'] = 'Middle'
                usable_df.loc[n_low + n_mid :, 'VF_Tier'] = 'High'

                tier_ranges = {
                    'Low': f"{usable_df[usable_df['VF_Tier'] == 'Low'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Low'][vf_col].max():.2f}",
                    'Middle': f"{usable_df[usable_df['VF_Tier'] == 'Middle'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Middle'][vf_col].max():.2f}",
                    'High': f"{usable_df[usable_df['VF_Tier'] == 'High'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'High'][vf_col].max():.2f}",
                }

                # 3. 엄격한 쿼터 기반 동적 체중 균등 배정
                target_quota = {'Low': k_low, 'Middle': k_mid, 'High': k_high}
                group_members = {g: [] for g in range(num_groups)}
                group_tier_counts = {g: {'Low': 0, 'Middle': 0, 'High': 0} for g in range(num_groups)}
                group_bw_sum = {g: 0.0 for g in range(num_groups)}

                for tier in ['High', 'Middle', 'Low']:
                    tier_df = usable_df[usable_df['VF_Tier'] == tier].sort_values(by=bw_col, ascending=False)
                    for _, animal in tier_df.iterrows():
                        # 해당 티어 쿼터가 남아있는 그룹 탐색
                        candidate_groups = [g for g in range(num_groups) if group_tier_counts[g][tier] < target_quota[tier]]
                        # 누적 체중이 가장 적은 그룹 선택
                        chosen_group = min(candidate_groups, key=lambda g: group_bw_sum[g])

                        animal_dict = animal.to_dict()
                        animal_dict['Assigned_Group'] = group_names[chosen_group]
                        group_members[chosen_group].append(animal_dict)
                        group_tier_counts[chosen_group][tier] += 1
                        group_bw_sum[chosen_group] += animal[bw_col]

                # 4. 결과 집계 및 요약 테이블 생성
                final_rows = []
                summary_data = []

                for i in range(num_groups):
                    g_list = group_members[i]
                    g_df = pd.DataFrame(g_list)
                    final_rows.append(g_df)

                    g_name = group_names[i]
                    summary_data.append({
                        'Group Name': g_name,
                        '개체수(N)': len(g_df),
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

                st.info(
                    f"💡 **von Frey 등급 기준 범위:** "
                    f"Low ({tier_ranges['Low']}) | Middle ({tier_ranges['Middle']}) | High ({tier_ranges['High']})"
                )

                # 요약 통계 테이블
                st.subheader(f"📊 {num_groups}개 그룹별 배정 요약 (전체 그룹 N={target_n} 동일)")
                st.dataframe(summary_df, use_container_width=True)

                # 발표용 시각화 차트
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.markdown("##### ⚖️ 그룹별 체중 평균 (균등화 검증)")
                    st.bar_chart(summary_df.set_index('Group Name')['체중 평균 (g)'])

                with col_chart2:
                    st.markdown("##### 🎯 그룹별 von Frey 등급 구성 (Low / Mid / High)")
                    chart_df = summary_df.set_index('Group Name')[['Low (VF)', 'Middle (VF)', 'High (VF)']]
                    st.bar_chart(chart_df)

                # 개체별 전체 배정 상세 테이블
                st.subheader("📋 개체별 배정 상세 결과")
                display_cols = ['Assigned_Group', 'VF_Tier', vf_col, bw_col] + [c for c in final_df.columns if c not in ['Assigned_Group', 'VF_Tier', vf_col, bw_col]]
                st.dataframe(final_df[display_cols], use_container_width=True)

                # 엑셀 파일 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, sheet_name='그룹별_통계요약', index=False)
                    final_df[display_cols].to_excel(writer, sheet_name='개체별_배정결과', index=False)
                    if not spare_df.empty:
                        spare_df.to_excel(writer, sheet_name='예비군_Spare', index=False)
                excel_bytes = output.getvalue()

                st.download_button(
                    label="📥 최적화 배정 결과 엑셀 다운로드 (.xlsx)",
                    data=excel_bytes,
                    file_name=f"Stratified_Equal_N_{num_groups}Groups.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"파일을 처리하는 중 오류가 발생했습니다: {e}")
