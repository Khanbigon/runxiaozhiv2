import streamlit as st
import pandas as pd
import json
import os
import sys

# 添加项目根目录到Python路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

# 现在可以直接从utils导入
from utils.deepseek_helper import DeepSeekHelper
from resume_matcher import ResumeJobMatcher

# Streamlit 配置
st.set_option('server.fileWatcherType', 'none')
st.set_option('server.maxUploadSize', 5)

# 设置环境变量来禁用文件监视
os.environ['STREAMLIT_FILE_WATCHER_TYPE'] = 'none'

def load_resume_data(file_path:str):
    """加载简历JSON数据文件"""
    absolute_path = os.path.join(ROOT_DIR, file_path.lstrip('./'))
    print(f"Loading file from: '{absolute_path}'")
    try:
        with open(absolute_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except OSError as e:
        if e.errno == 28:  # ENOSPC错误
            st.error("系统文件监视限制达到上限，请在终端执行：\n"
                    "echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p")
        raise e



def main():
    """主函数：实现简历匹配系统的核心功能"""
    st.title("智能简历匹配系统")
    
    # 尝试加载简历和职位数据
    try:
        resumes = load_resume_data("data/generated_resumes.json")  # 加载简历数据
        job_data = pd.read_excel(os.path.join(ROOT_DIR, "data/SZTU_2025_SPRING_POSITION_TABLE.xlsx"))        # 加载职位数据
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return
    
    # 初始化匹配器和AI分析助手（使用绝对路径）
    matcher = ResumeJobMatcher(
        os.path.join(ROOT_DIR, "data/SZTU_2025_SPRING_POSITION_TABLE.xlsx"),
        os.path.join(ROOT_DIR, "data/generated_resumes.json")
    )
    deepseek_helper = DeepSeekHelper()
    
    # 创建简历选择下拉框
    st.subheader("选择简历")
    # 生成简历列表，格式为：序号. 姓名 - 专业
    resume_names = [f"{i+1}. {resume['基本信息'].get('姓名', 'Unknown')} - {resume['教育经历']['专业']}" 
                   for i, resume in enumerate(resumes)]
    selected_index = st.selectbox("请选择要匹配的简历:", range(len(resume_names)), 
                                format_func=lambda x: resume_names[x])
    
    # 当用户点击"开始匹配分析"按钮时
    if st.button("开始匹配分析"):
        with st.spinner("正在进行匹配分析..."):
            try:
                # 执行职位匹配
                matched_jobs, resume_text = matcher.match_jobs(selected_index)
                
                # 使用AI生成匹配分析
                analysis = deepseek_helper.generate_matching_analysis(resume_text, matched_jobs)
                
                # 显示匹配结果部分
                st.subheader("🎯 职位匹配结果")
                for i, job in enumerate(matched_jobs, 1):
                    # 为每个匹配的职位创建一个可展开的区域
                    with st.expander(
                        f"#{i} {job['company']} - {job['position']} "
                        f"(匹配度: {job['match_percentage']}%)"
                    ):
                        # 显示职位详细信息
                        st.write("**公司：**", job['company'])
                        st.write("**职位：**", job['position'])
                        st.write("**薪资：**", job['salary'])
                        st.write("**要求：**", job['requirements'])
                        
                        # 显示AI分析的匹配详情
                        if "matching_analysis" in analysis:
                            for analysis_item in analysis["matching_analysis"]:
                                # 确保分析结果与当前职位对应
                                if (analysis_item.get("company") == job['company'] and 
                                    analysis_item.get("position") == job['position']):
                                    # 显示匹配优势
                                    st.write("**匹配优势：**")
                                    for point in analysis_item.get("matching_points", []):
                                        st.write(f"- {point}")
                                    # 显示差距分析
                                    st.write("**差距分析：**")
                                    for gap in analysis_item.get("gap_analysis", []):
                                        st.write(f"- {gap}")
                
                # 显示AI生成的简历优化建议
                st.subheader("📝 简历优化建议")
                if "resume_optimization" in analysis:
                    for suggestion in analysis["resume_optimization"]:
                        st.write(f"- {suggestion}")
                
                # 显示AI生成的技能提升建议
                st.subheader("💡 技能提升建议")
                if "skill_improvement" in analysis:
                    for skill in analysis["skill_improvement"]:
                        st.write(f"- {skill}")
                        
            except Exception as e:
                st.error(f"分析过程中出现错误: {str(e)}")

if __name__ == "__main__":
    main()