import os
import json
from datetime import datetime
from src.resume_matcher import ResumeJobMatcher
import pandas as pd

#根据data文件夹下的简历表格和岗位表格，生成匹配结果
#匹配结果保存在output文件夹下的json文件中

def main():
    # 获取当前工作目录
    ROOT_DIR = os.getcwd()
    
    # 初始化ResumeJobMatcher
    matcher = ResumeJobMatcher(
        os.path.join(ROOT_DIR, "data/SZTU_2025_SPRING_POSITION_TABLE.xlsx"),
        os.path.join(ROOT_DIR, "data/generated_resumes_with_ids.json")
    )
    
    # 创建输出目录
    output_dir = os.path.join(ROOT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取简历数据
    with open(os.path.join(ROOT_DIR, "data/generated_resumes_with_ids.json"), 'r', encoding='utf-8') as f:
        resumes = json.load(f)
    
    # 存储所有匹配结果
    all_matching_results = {}
    
    # 为每个简历进行岗位匹配
    for resume_index, resume in enumerate(resumes):
        unique_id = resume['基本信息']['唯一标识']
        print(f"Processing resume {unique_id} ({resume_index + 1}/{len(resumes)})")
        
        try:
            # 获取匹配结果
            matched_jobs, resume_text = matcher.match_jobs(resume_index, top_k=10)
            
            # 保存匹配结果
            result = {
                "resume_id": unique_id,
                "resume_text": resume_text,
                "matched_jobs": matched_jobs,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            all_matching_results[unique_id] = result
            
        except Exception as e:
            print(f"Error processing resume {unique_id}: {str(e)}")
            continue
    
    # 保存所有结果到一个JSON文件
    output_file = os.path.join(output_dir, f"matching_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_matching_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nMatching results have been saved to {output_file}")

if __name__ == "__main__":
    main()
