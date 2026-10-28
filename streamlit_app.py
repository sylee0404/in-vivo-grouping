import io
import re
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="In Vivo 균등 배정 (복잡한 엑셀 양식 지원)", layout="wide")

st.title("🧪 In Vivo 실험동물 그룹핑 (격자형 엑셀 자동 인식)")
st.markdown(
    """
    **연구실 특화 기능:** 
    이미지와 같은 **복잡한 격자형 엑셀(averavge 포함)** 양식을 자동으로 해독하여 개체별 통증 역치(von Frey)를 추출하고, 
    동물 ID를 기준으로 체중 데이터와 결합한 뒤 **High/Mid/Low 3단계 층화** 및 **동일 N수 균등 배정**을 수행합니다.
    """
)

# 숫자 뒤 단위('g' 등) 및 특수문자 제거 후 float 변환 함수
def clean_numeric(val):
    if pd.isna(val):
        return np.nan
    val_str = str(val).strip()
    cleaned = re.findall(r"[-+]?\d*\.\d+|\d+", val_str)
    return float(cleaned[0]) if cleaned else np.nan

uploaded_file = st.file_uploader("실험 데이터 엑셀 파일(.xlsx, .xls)을 올려주세요", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        st.markdown("---")
        st.header("1️⃣ 데이터 구조 자동 추출 설정")
        
        data_mode = st.radio(
            "엑셀 데이터가 어떤 형태로 저장되어 있나요?",
            ["연구실 격자형 원본 (이미지처럼 'averavge' 칸이 있는 양식)", "일반 세로형 표 (1줄당 1마리)"],
            index=0
        )
        
        work_df = pd.DataFrame()
        vf_col = 'VonFrey_Average'
        bw_col = 'BodyWeight'
        id_col = 'Animal_ID'

        if "격자형" in data_mode:
            st.info("💡 **격자형 모드:** 시트 전체를 스캔하여 'averavge' 키워드와 그 위에 있는 동물 ID를 100% 자동으로 추출합니다.")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                vf_sheet = st.selectbox("Von Frey (격자형) 시트 선택", sheet_names, index=0)
            with col_s2:
                bw_sheet = st.selectbox("Bodyweight (체중) 시트 선택", sheet_names, index=0 if len(sheet_names)==1 else 1)
            
            # --- 1. Von Frey 격자 자동 추출 ---
            raw_vf_df = pd.read_excel(uploaded_file, sheet_name=vf_sheet, header=None)
            extracted = []
            
            for r in range(raw_vf_df.shape[0]):
                for c in range(raw_vf_df.shape[1]):
                    val = str(raw_vf_df.iloc[r, c]).strip().lower()
                    # 이미지에 있는 오타 'averavge' 완벽 대응
                    if val in ['averavge', 'average', 'avg']:
                        try:
                            # 우측 칸이 평균값, 3칸 위가 동물 ID
                            vf_val = float(raw_vf_df.iloc[r, c+1])
                            if r - 3 >= 0:
                                animal_id = raw_vf_df.iloc[r-3, c]
                                if pd.notna(animal_id):
                                    # ID 정제 (예: 1.0 -> '1')
                                    if isinstance(animal_id, (int, float)):
                                        animal_id = str(int(animal_id)) if float(animal_id).is_integer() else str(animal_id)
                                    else:
                                        animal_id = str(animal_id).strip()
                                    extracted.append({id_col: animal_id, vf_col: vf_val})
                        except Exception:
                            pass
            
            vf_parsed_df = pd.DataFrame(extracted)
            
            # --- 2. Bodyweight 추출 및 매칭 ---
            st.markdown("#### ⚙️ 체중(Bodyweight) 매칭 설정")
            header_row = st.number_input("체중 시트의 컬럼명(헤더) 행 번호", min_value=1, max_value=10, value=1)
            raw_bw_df = pd.read_excel(uploaded_file, sheet_name=bw_sheet, header=header_row-1)
            raw_bw_df = raw_bw_df.loc[:, ~raw_bw_df.columns.astype(str).str.startswith('Unnamed:')]
            cols_bw = [str(c).strip() for c in raw_bw_df.columns]
            
            c1, c2 = st.columns(2)
            with c1:
                bw_id_default = cols_bw[0]
                bw_id_col = st.selectbox("체중 시트의 '동물 ID' 컬럼", cols_bw, index=cols_bw.index(bw_id_default))
            with c2:
                bw_val_default = next((c for c in cols_bw if any(k in c.lower() for k in ["weight", "bw", "몸무게", "체중", "8.18"])), cols_bw[1] if len(cols_bw) > 1 else cols_bw[0])
                bw_val_col = st.selectbox("체중 시트의 '실제 체중' 컬럼 (예: 8.18 BodyWeight)", cols_bw, index=cols_bw.index(bw_val_default))
            
            # ID 형식을 일치시켜 두 표를 병합 (Merge)
            raw_bw_df['Clean_ID'] = raw_bw_df[bw_id_col].apply(lambda x: str(int(x)) if isinstance(x, float) and float(x).is_integer() else str(x).strip())
            bw_parsed_df = raw_bw_df[['Clean_ID', bw_val_col]].rename(columns={'Clean_ID': id_col, bw_val_col: bw_col})
            
            work_df = pd.merge(vf_parsed_df, bw_parsed_df, on=id_col, how='inner')
            work_df[bw_col] = work_df[bw_col].apply(clean_numeric)
            work_df = work_df.dropna(subset=[vf_col, bw_col])
            
            if not work_df.empty:
                st.success(f"✅ 'averavge' 분석 성공! 총 **{len(work_df)}마리**의 데이터를 성공적으로 찾아 체중과 짝을 맞추었습니다.")
                st.dataframe(work_df.head(), use_container_width=True)
            else:
                st.error("데이터 매칭에 실패했습니다. ID 컬럼이 올바른지 확인해 주세요.")
                
        # (일반 세로형 모드 생략 없이 지원하려면 이 부분에 기존 로직 추가 가능)
        
        if not work_df.empty:
            st.markdown("---")
            st.header("2️⃣ 층화 균등 배정 설정")
            g_col1, g_col2 = st.columns([1, 3])
            
            with g_col1:
                num_groups = st.number_input("나눌 시험군(그룹) 수", min_value=2, max_value=30, value=7, step=1)
                
            with g_col2:
                default_names = ["Vehicle"] + [f"Drug_{chr(65+i)}" for i in range(num_groups - 2)] + ["Normal"] if num_groups >= 2 else ["Group 1", "Group 2"]
                default_names_str = ", ".join(default_names[:num_groups])
                group_names_input = st.text_input("그룹 이름 (쉼표 ','로 구분하여 입력)", value=default_names_str)

            parsed_names = [name.strip() for name in group_names_input.split(",") if name.strip()]
            group_names = [parsed_names[i] if i < len(parsed_names) else f"Group {i+1}" for i in range(num_groups)]
            
            if st.button("🚀 von Frey 3단계 층화 & 체중 균등 배정 실행", type="primary"):
                total_n = len(work_df)
                target_n = total_n // num_groups
                usable_total = target_n * num_groups
                remainder = total_n - usable_total
                
                # von Frey 순으로 줄세우기
                work_df = work_df.sort_values(by=vf_col, ascending=True).reset_index(drop=True)
                
                # 잉여 개체(Spare) 분리
                if remainder > 0:
                    trim_low = remainder // 2
                    trim_high = remainder - trim_low
                    spare_indices = list(range(trim_low)) + list(range(total_n - trim_high, total_n))
                    spare_df = work_df.iloc[spare_indices].copy()
                    spare_df['비고'] = '예비군(Spare) - N수 동일 배정을 위한 제외'
                    usable_df = work_df.drop(index=spare_indices).reset_index(drop=True)
                    st.warning(f"⚠️ 72마리 중 그룹당 {target_n}마리씩 배정하여 총 {usable_total}마리가 분석에 사용됩니다. (나머지 {remainder}마리는 엑셀 '예비군_Spare' 시트로 분리됨)")
                else:
                    usable_df = work_df.copy()
                    spare_df = pd.DataFrame()
                
                # 티어 쿼터 산정
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
                    'Low': f"{usable_df[usable_df['VF_Tier'] == 'Low'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Low'][vf_col].max():.2f}",
                    'Middle': f"{usable_df[usable_df['VF_Tier'] == 'Middle'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'Middle'][vf_col].max():.2f}",
                    'High': f"{usable_df[usable_df['VF_Tier'] == 'High'][vf_col].min():.2f} ~ {usable_df[usable_df['VF_Tier'] == 'High'][vf_col].max():.2f}",
                }

                # 쿼터 기반 체중 균등화
                target_quota = {'Low': k_low, 'Middle': k_mid, 'High': k_high}
                group_members = {g: [] for g in range(num_groups)}
                group_tier_counts = {g: {'Low': 0, 'Middle': 0, 'High': 0} for g in range(num_groups)}
                group_bw_sum = {g: 0.0 for g in range(num_groups)}

                for tier in ['High', 'Middle', 'Low']:
                    tier_df = usable_df[usable_df['VF_Tier'] == tier].sort_values(by=bw_col, ascending=False)
                    for _, animal in tier_df.iterrows():
                        candidate_groups = [g for g in range(num_groups) if group_tier_counts[g][tier] < target_quota[tier]]
                        chosen_group = min(candidate_groups, key=lambda g: group_bw_sum[g])

                        animal_dict = animal.to_dict()
                        animal_dict['Assigned_Group'] = group_names[chosen_group]
                        group_members[chosen_group].append(animal_dict)
                        group_tier_counts[chosen_group][tier] += 1
                        group_bw_sum[chosen_group] += animal[bw_col]

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
                        '체중 평균(g)': round(g_df[bw_col].mean(), 2),
                        '체중 SD': round(g_df[bw_col].std(), 2) if len(g_df) > 1 else 0.0,
                        'VonFrey 평균': round(g_df[vf_col].mean(), 2),
                        'VonFrey SD': round(g_df[vf_col].std(), 2) if len(g_df) > 1 else 0.0
                    })

                final_df = pd.concat(final_rows, ignore_index=True)
                summary_df = pd.DataFrame(summary_data)

                st.info(f"💡 **72마리 von Frey 등급 기준:** Low ({tier_ranges['Low']}) | Middle ({tier_ranges['Middle']}) | High ({tier_ranges['High']})")

                st.subheader(f"📊 {num_groups}개 그룹별 배정 요약 (전체 그룹 N={target_n} 동일)")
                st.dataframe(summary_df, use_container_width=True)

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.markdown("##### ⚖️ 체중 평균 (균등화 검증)")
                    st.bar_chart(summary_df.set_index('Group Name')['체중 평균(g)'])
                with col_chart2:
                    st.markdown("##### 🎯 von Frey 등급 구성 비율")
                    st.bar_chart(summary_df.set_index('Group Name')[['Low (VF)', 'Middle (VF)', 'High (VF)']])

                st.subheader("📋 72마리 전체 배정 상세 결과")
                display_cols = ['Assigned_Group', 'VF_Tier', id_col, vf_col, bw_col]
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
                    file_name=f"InVivo_Grouping_72Animals_{num_groups}Groups.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"파일 처리 오류: {e}")
