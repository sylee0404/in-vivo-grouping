import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="In Vivo 균등 배정 (연구실 맞춤형)", layout="wide")

st.title("🧪 In Vivo 실험동물 그룹핑 (VonFrey & Bodyweight 자동 매칭)")
st.markdown(
    """
    **연구실 맞춤형 코드 적용 완료:** 
    업로드하신 엑셀 파일의 **`Vonfrey SY정리`** 시트(격자형 averavge 표)와 **`Bodyweight SY정리`** 시트를 
    단번에 스캔하여 72마리의 데이터를 정확히 뽑아내고 배정합니다.
    """
)

uploaded_file = st.file_uploader("실험 데이터 엑셀 파일(.xlsx)을 올려주세요", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 엑셀 시트 이름 자동 인식 (공백 무시)
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names
        
        vf_sheet = next((s for s in sheet_names if 'vonfrey' in s.lower() and 'sy' in s.lower()), None)
        bw_sheet = next((s for s in sheet_names if 'bodyweight' in s.lower() and 'sy' in s.lower()), None)
        
        if not vf_sheet or not bw_sheet:
            st.error("엑셀 파일에 'Vonfrey SY정리' 또는 'Bodyweight SY정리' 시트가 없습니다. 시트 이름을 확인해 주세요.")
            st.stop()

        # 2. VonFrey SY정리 (72마리 averavge 자동 추출)
        raw_vf_df = pd.read_excel(uploaded_file, sheet_name=vf_sheet, header=None)
        extracted = []
        
        for r in range(raw_vf_df.shape[0]):
            for c in range(raw_vf_df.shape[1]):
                val = str(raw_vf_df.iloc[r, c]).strip().lower()
                # 오타(averavge) 및 평균(average, avg) 텍스트 자동 탐지
                if val in ['averavge', 'average', 'avg']:
                    try:
                        vf_val = float(raw_vf_df.iloc[r, c+1])
                        if r - 3 >= 0:
                            animal_id = raw_vf_df.iloc[r-3, c]
                            if pd.notna(animal_id):
                                # 동물 ID 소수점 제거 및 문자열 통일
                                if isinstance(animal_id, (int, float)):
                                    animal_id = str(int(animal_id)) if float(animal_id).is_integer() else str(animal_id)
                                else:
                                    animal_id = str(animal_id).strip()
                                extracted.append({'Animal_ID': animal_id, 'VonFrey': vf_val})
                    except Exception:
                        pass
                        
        vf_parsed_df = pd.DataFrame(extracted)

        # 3. Bodyweight SY정리 추출 (1열=ID, 2열=체중)
        raw_bw_df = pd.read_excel(uploaded_file, sheet_name=bw_sheet)
        raw_bw_df = raw_bw_df.iloc[:, [0, 1]] # 첫 두 컬럼만 강제 선택
        raw_bw_df.columns = ['Animal_ID', 'BodyWeight']
        
        raw_bw_df['Animal_ID'] = raw_bw_df['Animal_ID'].apply(lambda x: str(int(x)) if isinstance(x, (int, float)) and float(x).is_integer() else str(x).strip())
        raw_bw_df['BodyWeight'] = pd.to_numeric(raw_bw_df['BodyWeight'], errors='coerce')

        # 4. 데이터 완벽 병합 (ID 기준)
        work_df = pd.merge(vf_parsed_df, raw_bw_df, on='Animal_ID', how='inner')
        work_df = work_df.dropna(subset=['VonFrey', 'BodyWeight'])

        if not work_df.empty:
            st.success(f"✅ 데이터 인식 완료! 총 **{len(work_df)}마리**의 통증 역치(VonFrey)와 체중(Bodyweight) 데이터가 정확히 결합되었습니다.")
        else:
            st.error("데이터 매칭에 실패했습니다. 파일 양식이 변경되었는지 확인해 주세요.")
            st.stop()

        # 5. 균등 배정 설정
        st.markdown("---")
        st.header("⚙️ 배정 조건 설정")
        
        g_col1, g_col2 = st.columns([1, 3])
        with g_col1:
            # 72마리는 6개, 8개, 9개, 12개 그룹으로 나눌 때 딱 떨어집니다. 기본값을 6으로 설정합니다.
            num_groups = st.number_input("나눌 그룹 수 (예: 6)", min_value=2, max_value=30, value=6, step=1)
            
        with g_col2:
            default_names = ["Vehicle"] + [f"Drug_{chr(65+i)}" for i in range(num_groups - 2)] + ["Normal"] if num_groups >= 2 else ["Group 1", "Group 2"]
            default_names_str = ", ".join(default_names[:num_groups])
            group_names_input = st.text_input("그룹 이름 (쉼표 ','로 구분하여 입력)", value=default_names_str)

        parsed_names = [name.strip() for name in group_names_input.split(",") if name.strip()]
        group_names = [parsed_names[i] if i < len(parsed_names) else f"Group {i+1}" for i in range(num_groups)]

        if st.button("🚀 72마리 최적 균등 배정 실행", type="primary"):
            total_n = len(work_df)
            target_n = total_n // num_groups
            usable_total = target_n * num_groups
            remainder = total_n - usable_total
            
            # VonFrey 순으로 줄세우기 (오름차순)
            work_df = work_df.sort_values(by='VonFrey', ascending=True).reset_index(drop=True)
            
            if remainder > 0:
                trim_low = remainder // 2
                trim_high = remainder - trim_low
                spare_indices = list(range(trim_low)) + list(range(total_n - trim_high, total_n))
                spare_df = work_df.iloc[spare_indices].copy()
                spare_df['비고'] = '예비군(Spare) - N수 동일 배정을 위한 제외'
                usable_df = work_df.drop(index=spare_indices).reset_index(drop=True)
                st.warning(f"⚠️ 총 {total_n}마리 중 그룹당 {target_n}마리씩 배정하여 {usable_total}마리가 배정됩니다. (나머지 {remainder}마리는 엑셀 '예비군_Spare'로 분리됨)")
            else:
                usable_df = work_df.copy()
                spare_df = pd.DataFrame()
            
            # High / Mid / Low 쿼터 산정
            k_low = target_n // 3
            k_mid = target_n // 3
            k_high = target_n // 3
            rem = target_n % 3
            if rem == 1: k_mid += 1
            elif rem == 2: k_high += 1; k_low += 1

            n_low = num_groups * k_low
            n_mid = num_groups * k_mid
            
            usable_df['VF_Tier'] = ''
            usable_df.loc[:n_low - 1, 'VF_Tier'] = 'Low'
            usable_df.loc[n_low : n_low + n_mid - 1, 'VF_Tier'] = 'Middle'
            usable_df.loc[n_low + n_mid :, 'VF_Tier'] = 'High'

            tier_ranges = {
                'Low': f"{usable_df[usable_df['VF_Tier'] == 'Low']['VonFrey'].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Low']['VonFrey'].max():.2f}",
                'Middle': f"{usable_df[usable_df['VF_Tier'] == 'Middle']['VonFrey'].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Middle']['VonFrey'].max():.2f}",
                'High': f"{usable_df[usable_df['VF_Tier'] == 'High']['VonFrey'].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'High']['VonFrey'].max():.2f}",
            }

            # 쿼터 기반 체중 균등화 (Greedy Algorithm)
            target_quota = {'Low': k_low, 'Middle': k_mid, 'High': k_high}
            group_members = {g: [] for g in range(num_groups)}
            group_tier_counts = {g: {'Low': 0, 'Middle': 0, 'High': 0} for g in range(num_groups)}
            group_bw_sum = {g: 0.0 for g in range(num_groups)}

            for tier in ['High', 'Middle', 'Low']:
                tier_df = usable_df[usable_df['VF_Tier'] == tier].sort_values(by='BodyWeight', ascending=False)
                for _, animal in tier_df.iterrows():
                    candidate_groups = [g for g in range(num_groups) if group_tier_counts[g][tier] < target_quota[tier]]
                    chosen_group = min(candidate_groups, key=lambda g: group_bw_sum[g])

                    animal_dict = animal.to_dict()
                    animal_dict['Assigned_Group'] = group_names[chosen_group]
                    group_members[chosen_group].append(animal_dict)
                    group_tier_counts[chosen_group][tier] += 1
                    group_bw_sum[chosen_group] += animal['BodyWeight']

            final_rows, summary_data = [], []
            for i in range(num_groups):
                g_df = pd.DataFrame(group_members[i])
                final_rows.append(g_df)
                summary_data.append({
                    'Group Name': group_names[i],
                    'N수': len(g_df),
                    'Low (VF)': group_tier_counts[i]['Low'],
                    'Middle (VF)': group_tier_counts[i]['Middle'],
                    'High (VF)': group_tier_counts[i]['High'],
                    '체중 평균(g)': round(g_df['BodyWeight'].mean(), 2),
                    '체중 SD': round(g_df['BodyWeight'].std(), 2) if len(g_df) > 1 else 0.0,
                    'VonFrey 평균': round(g_df['VonFrey'].mean(), 2),
                    'VonFrey SD': round(g_df['VonFrey'].std(), 2) if len(g_df) > 1 else 0.0
                })

            final_df = pd.concat(final_rows, ignore_index=True)
            summary_df = pd.DataFrame(summary_data)

            st.info(f"💡 **VonFrey 분류 기준:** Low ({tier_ranges['Low']}) | Middle ({tier_ranges['Middle']}) | High ({tier_ranges['High']})")

            st.subheader(f"📊 {num_groups}개 그룹별 배정 요약 (그룹당 N={target_n} 동일)")
            st.dataframe(summary_df, use_container_width=True)

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("##### ⚖️ 체중 평균 (균등화 검증)")
                st.bar_chart(summary_df.set_index('Group Name')['체중 평균(g)'])
            with col_chart2:
                st.markdown("##### 🎯 VonFrey 등급 구성 비율")
                st.bar_chart(summary_df.set_index('Group Name')[['Low (VF)', 'Middle (VF)', 'High (VF)']])

            st.subheader("📋 전체 배정 상세 결과")
            display_cols = ['Assigned_Group', 'VF_Tier', 'Animal_ID', 'VonFrey', 'BodyWeight']
            st.dataframe(final_df[display_cols], use_container_width=True)

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
                file_name=f"InVivo_Grouping_{num_groups}Groups.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
    except Exception as e:
        st.error(f"파일 처리 오류가 발생했습니다: {e}")
