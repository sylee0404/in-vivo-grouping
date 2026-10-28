import pandas as pd
import numpy as np

def stratified_randomization(input_data_path, num_groups=12):
    print("데이터를 분석하고 최적의 그룹핑을 계산 중입니다...")
    
    # 1. 가상의 통합 데이터 불러오기 (실제로는 raw data 엑셀을 불러오도록 수정)
    # 예시를 위해 ID, 몸무게(BW), Von Frey(VF) 데이터 프레임이 있다고 가정합니다.
    # df = pd.read_excel(input_data_path, sheet_name='RawData')
    
    # ------------------ (이하 알고리즘 핵심 로직) ------------------ #
    
    # 2. 결측치 제거 및 정렬 기준 설정
    # (von Frey는 통증 역치이므로 1순위, 몸무게는 2순위 지표로 설정)
    df = df.dropna(subset=['VonFrey', 'Bodyweight'])
    
    # 3. Z-Score 정규화를 통한 두 지표의 가중치 통합 (AI 기반 최적화 기법 적용)
    df['VF_Z'] = (df['VonFrey'] - df['VonFrey'].mean()) / df['VonFrey'].std()
    df['BW_Z'] = (df['Bodyweight'] - df['Bodyweight'].mean()) / df['Bodyweight'].std()
    
    # 통합 점수 (Combined Score) 계산: 두 지표가 동시에 고려되도록 합산
    df['Combined_Score'] = df['VF_Z'] + df['BW_Z']
    
    # 통합 점수를 기준으로 내림차순 정렬
    df_sorted = df.sort_values(by='Combined_Score', ascending=False).reset_index(drop=True)
    
    # 4. 스네이크 분배 (Serpentine Distribution) 알고리즘
    groups = {i: [] for i in range(1, num_groups + 1)}
    
    for i, row in df_sorted.iterrows():
        round_num = i // num_groups  # 몇 번째 바퀴인지 (0, 1, 2...)
        
        # 짝수 바퀴는 순방향 (1 -> 12), 홀수 바퀴는 역방향 (12 -> 1) 배정
        if round_num % 2 == 0:
            group_idx = (i % num_groups) + 1
        else:
            group_idx = num_groups - (i % num_groups)
            
        groups[group_idx].append(row)

    # 5. 결과 검증 및 데이터 프레임화
    group_names = [
        'Vehicle', 'Librela(시판)', 'Librela(BN)', '19-5(histidine)', 
        '19-5(PBS)', '19-5(hybridoma)', '128-2(histidine)', '128-2(PBS)', 
        '128-2(hybridoma)', '9-1(histidine)', '9-1(PBS)', 'Normal'
    ]
    
    final_rows = []
    print("\n✅ [Stratified Randomization 완료] 그룹별 배정 평균값:")
    print("-" * 50)
    print(f"{'Group Name':<18} | {'Von Frey 평균':<12} | {'Bodyweight 평균'}")
    print("-" * 50)
    
    for i in range(1, num_groups + 1):
        g_df = pd.DataFrame(groups[i])
        g_df['Assigned_Group'] = group_names[i-1]
        
        vf_mean = g_df['VonFrey'].mean()
        bw_mean = g_df['Bodyweight'].mean()
        print(f"{group_names[i-1]:<18} | {vf_mean:>12.2f} | {bw_mean:>12.2f}")
        
        final_rows.append(g_df)

    final_df = pd.concat(final_rows, ignore_index=True)
    
    # 6. 최종 엑셀 파일 저장
    output_filename = "Optimized_Grouping_Result.xlsx"
    final_df.to_excel(output_filename, index=False)
    print("-" * 50)
    print(f"결과 파일이 '{output_filename}'으로 저장되었습니다.")

# 실행 함수 (실제 사용 시 파일 경로 입력)
# stratified_randomization('동물rawdata.xlsx', num_groups=12)
