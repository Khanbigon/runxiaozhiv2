import json
import os
import sys

# 添加项目根目录到Python路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

# 现在可以直接从utils导入
from utils.deepseek_helper import DeepSeekHelper
from resume_matcher import ResumeJobMatcher
from datetime import datetime

def ensure_output_dir():
    """确保输出目录存在"""
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def load_resume_data(file_path):
    """加载简历数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_matching_results():
    """生成匹配结果并输出到文件"""
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(__file__))
    
    # 初始化匹配器和AI助手
    matcher = ResumeJobMatcher(
        os.path.join(root_dir, "data/SZTU_2025_SPRING_POSITION_TABLE.xlsx"),
        os.path.join(root_dir, "data/generated_resumes.json")
    )
    deepseek_helper = DeepSeekHelper()
    
    # 加载简历数据
    resumes = load_resume_data(os.path.join(root_dir, "data/generated_resumes.json"))
    
    # 存储所有结果
    all_results = []
    
    # 为每个简历生成匹配结果
    for i, resume in enumerate(resumes):
        print(f"\n处理简历 {i+1}/{len(resumes)}: {resume['基本信息'].get('姓名', 'Unknown')}")
        
        try:
            # 获取职位匹配结果
            matched_jobs, resume_text = matcher.match_jobs(i)
            print(f"找到 {len(matched_jobs)} 个匹配的职位")
            
            # 获取AI分析结果
            analysis = deepseek_helper.generate_matching_analysis(resume_text, matched_jobs)
            print("AI分析完成")
            
            # 组合结果
            result = {
                "resume_info": {
                    "name": resume['基本信息'].get('姓名', 'Unknown'),
                    "major": resume['教育经历']['专业'],
                    "education": resume['教育经历']['学历']
                },
                "matched_jobs": matched_jobs,
                "ai_analysis": analysis
            }
            
            all_results.append(result)
            
        except Exception as e:
            print(f"处理简历时发生错误: {str(e)}")
    
    # 生成输出文件名（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(ensure_output_dir(), f'matching_results_{timestamp}.json')
    
    # 保存结果到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n所有结果已保存到: {output_file}")

if __name__ == "__main__":
    generate_matching_results()
