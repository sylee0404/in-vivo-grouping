import io
import numpy as np
import pandas as pd
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="실험동물 균등 그룹핑 도구", layout="wide")

st.title("🧪 In Vivo 실험동물 체중 & von Frey 균등 분배 도구")
st.markdown("엑셀 데이터를 업로드하면 **Z-Score 가중치**와 **스네이크 분배 알고리즘**을 통해 12개 그룹의 평균이 균등해지도록 자동 배정합니다.")

# 1. 파일 업로더
uploaded_file = st.file_uploader("실험 데이터 엑셀 파일(.xlsx, .xls)을 올려주세요", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 시트 목록 확인 및 선택
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        # 'bodyweight'가 포함된 시트가 있으면 기본값으로 자동 선택
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
        
        # 컬럼 이름 자동 매칭 (대소문자 무관 탐색)
        vf_default = next((c for c in cols if "von" in c.lower() or "vf" in c.lower() or "frey" in c.lower()), cols[0])
        bw_default = next((c for c in cols if "weight" in c.lower() or "bw" in c.lower() or "몸무게" in c.lower() or "체중" in c.lower()), cols[1] if len(cols) > 1 else cols[0])
        
        st.markdown("#### ⚙️ 분석 지표 컬럼 매칭")
        c1, c2 = st.columns(2)
        with c1:
            vf_col = st.selectbox("1순위: von Frey (통증 역치) 컬럼", cols, index=cols.index(vf_default))
        with c2:
            bw_col = st.selectbox("2순위: Bodyweight (체중) 컬럼", cols, index=cols.index(bw_default))
            
        group_names = [
            'Vehicle', 'Librela(시판)', 'Librela(BN)', '19-5(histidine)', 
            '19-5(PBS)', '19-5(hybridoma)', '128-2(histidine)', '128-2(PBS)', 
            '128-2(hybridoma)', '9-1(histidine)', '9-1(PBS)', 'Normal'
        ]
        num_groups = len(group_names)

        if st.button("🚀 최적 그룹핑(Stratified Randomization) 실행", type="primary"):
            # 결측치 처리 및 숫자형 변환
            work_df = df.dropna(subset=[vf_col, bw_col]).copy()
            work_df[vf_col] = pd.to_numeric(work_df[vf_col], errors='coerce')
            work_df[bw_col] = pd.to_numeric(work_df[bw_col], errors='coerce')
            work_df = work_df.dropna(subset=[vf_col, bw_col])
            
            if len(work_df) < num_groups:
                st.error(f"유효 데이터 수({len(work_df)}개)가 배정할 그룹 수({num_groups}개)보다 적습니다.")
            else:
                # Z-Score 정규화 및 통합 점수 계산
                work_df['VF_Z'] = (work_df[vf_col] - work_df[vf_col].mean()) / work_df[vf_col].std()
                work_df['BW_Z'] = (work_df[bw_col] - work_df[bw_col].mean()) / work_df[bw_col].std()
                work_df['Combined_Score'] = work_df['VF_Z'] + work_df['BW_Z']
                
                # 통합 점수 기준 내림차순 정렬
                df_sorted = work_df.sort_values(by='Combined_Score', ascending=False).reset_index(drop=True)
                
                # 스네이크 분배 알고리즘 적용
                groups = {i: [] for i in range(1, num_groups + 1)}
                for i, row in df_sorted.iterrows():
                    round_num = i // num_groups
                    if round_num % 2 == 0:
                        group_idx = (i % num_groups) + 1
                    else:
                        group_idx = num_groups - (i % num_groups)
                    groups[group_idx].append(row)
                
                final_rows = []
                summary_data = []
                
                for i in range(1, num_groups + 1):
                    g_df = pd.DataFrame(groups[i])
                    g_name = group_names[i - 1]
                    g_df['Assigned_Group'] = g_name
                    final_rows.append(g_df)
                    
                    summary_data.append({
                        'Group Name': g_name,
                        '개체수(N)': len(g_df),
                        'von Frey 평균': round(g_df[vf_col].mean(), 2),
                        'von Frey 표준편차': round(g_df[vf_col].std(), 2),
                        '체중 평균': round(g_df[bw_col].mean(), 2),
                        '체중 표준편차': round(g_df[bw_col].std(), 2)
                    })
                    
                final_df = pd.concat(final_rows, ignore_index=True)
                summary_df = pd.DataFrame(summary_data)
                
                st.success("✅ 그룹 배정이 성공적으로 완료되었습니다!")
                
                # 요약 통계 테이블
                st.subheader("📊 12개 그룹별 평균값 비교 (요약)")
                st.dataframe(summary_df, use_container_width=True)
                
                # 발표용 비교 그래프
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    st.markdown("**그룹별 von Frey 평균 비교**")
                    st.bar_chart(summary_df.set_index('Group Name')['von Frey 평균'])
                with chart_col2:
                    st.markdown("**그룹별 체중 평균 비교**")
                    st.bar_chart(summary_df.set_index('Group Name')['체중 평균'])
                
                # 전체 배정 결과 테이블
                st.subheader("📋 개체별 그룹 배정 전체 결과")
                st.dataframe(final_df, use_container_width=True)
                
                # 엑셀 다운로드 생성 (메모리 버퍼 활용)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, sheet_name='그룹별_통계요약', index=False)
                    final_df.to_excel(writer, sheet_name='개체별_배정결과', index=False)
                excel_bytes = output.getvalue()
                
                st.download_button(
                    label="📥 최적화된 결과 엑셀 다운로드 (.xlsx)",
                    data=excel_bytes,
                    file_name="Optimized_Grouping_Result.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    except Exception as e:
        st.error(f"파일을 처리하는 중 오류가 발생했습니다: {e}")
