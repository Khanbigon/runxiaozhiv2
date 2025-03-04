import gradio as gr
import pandas as pd
import json
from openai import OpenAI
import time
import re
# 大模型配置
client = OpenAI(
    api_key="sk-430766cb68934151aaeae540823fea2f",
    base_url="https://api.deepseek.com"
)

# 全局缓存
df_companies = pd.DataFrame()
CACHE_EXPIRY = 300

# 大模型匹配函数
def get_matching_score(student_skills, job_requirements):
    prompt = f"""请根据以下学生技能和企业岗位要求进行匹配度评分（0-100），并列出关键匹配点：
请基于以下规则评分：
1. 技能关键词匹配度（如“Python” vs “Python编程”）
2. 技能相关性（如“数据分析” vs “数据可视化”）
3. 综合能力覆盖度
学生技能：
{student_skills}
岗位要求：
{job_requirements}
输出JSON格式：{{"score": 分数, "matches": ["匹配点1", "匹配点2"]}}"""
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"大模型调用失败: {e}")
        return {"score": 0, "matches": []}

# 解析薪资字符串为最低和最高薪资
def parse_salary(salary_str):
    match = re.search(r'(\d+)K-(\d+)K', salary_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0

# 带进度显示的匹配处理
def match_process(resume_file, company_file, min_salary, major_filter):
    # 初始化进度条
    progress = gr.Progress()
    
    # 解析简历
    progress(0.1, desc="解析简历...")
    with open(resume_file.name, 'r', encoding='utf-8') as f:
        resume = json.load(f)
    
    # 加载企业数据
    progress(0.3, desc="加载企业数据...")
    global df_companies
    if company_file:
        with open(company_file.name, 'r', encoding='utf-8') as f:
            job_data = json.load(f)

        jobs = []
        for job in job_data['jobs']:
            min_k, max_k = parse_salary(job['salary'])
            jobs.append({
                '单位名称': job['company_name'],
                '岗位名称': job['job_name'],
                '最低薪资K月': min_k,
                '最高薪资K月': max_k,
                '工作城市': job['location'],
                '专业要求': job['major'],
                '岗位职责': job['job_responsibilities'],
                '岗位要求': job['job_requirements'],
                '职位备注': job['job_url']
            })
        df_companies = pd.DataFrame(jobs)

    # 应用筛选
    progress(0.5, desc="应用筛选条件...")
    filtered = df_companies.copy()
    filtered = filtered[filtered['最低薪资K月'] >= min_salary]
    if major_filter != "不限":
        filtered = filtered[filtered['专业要求'].str.contains(major_filter)]
    
    # 执行匹配
    results = []
    total = len(filtered)
    for idx, row in enumerate(filtered.itertuples()):
        progress(0.6 + 0.3*(idx/total), desc=f"分析岗位 {idx+1}/{total}...")
        match = get_matching_score(
            resume['专业技能'], 
            f"{row.岗位职责}\n{row.岗位要求}"
        )
        results.append({
            "公司": row.单位名称,
            "岗位": row.岗位名称,
            "匹配度": match['score'],
            "关键点": "<br>".join(match['matches'][:3]),
            "薪资": f"{row.最低薪资K月}-{row.最高薪资K月}K",
            "链接": row.职位备注
        })
    
    # 完成进度条
    progress(1.0, desc="完成分析！")
    sorted_results = sorted(results, key=lambda x: x['匹配度'], reverse=True)
    return build_html_result(sorted_results[:5])

# 结果展示HTML生成
def build_html_result(results):
    html = """<div style="font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 20px auto;">"""
    for item in results:
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin:0; color: #003788;">{item['公司']}</h3>
                    <p style="margin:5px 0; color: #0068ca;">{item['岗位']}</p>
                </div>
                <div style="background: {get_score_color(item['匹配度'])}; 
                           width: 60px; height: 60px; border-radius: 50%; 
                           display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-weight: bold; font-size: 18px;">{item['匹配度']}</span>
                </div>
            </div>
            <div style="margin-top: 15px;">
                <p style="color: #223259; margin: 8px 0;">薪资：{item['薪资']}</p>
                <p style="color: #223259; margin: 8px 0;">关键匹配：{item['关键点']}</p>
                <a href="{item['链接']}" target="_blank" 
                   style="display: inline-block; padding: 8px 20px; 
                          background: #3498db; color: white; border-radius: 5px; 
                          text-decoration: none; margin-top: 10px;">
                    查看详情 →
                </a>
            </div>
        </div>"""
    return html + "</div>"

def get_score_color(score):
    if score >= 80: return "#27ae60"
    elif score >= 60: return "#f1c40f"
    else: return "#e74c3c"

# 界面设计
with gr.Blocks(theme=gr.themes.Base(), title="润小职Agent") as demo:
    with gr.Row():
        logo_img=gr.Image('sztu.png', interactive=False, label='logo', height=100, width=100,)
        gr.Markdown("""<h1 style="text-align: center; color: #003788;">润小职</h1>""")
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 第一步：上传资料")
            resume_upload = gr.File(label="上传简历（JSON）", file_types=[".json"])
            company_upload = gr.File(label="上传企业数据（JSON）", file_types=[".json"])
            
            gr.Markdown("### 第二步：设置条件")
            with gr.Accordion("筛选设置", open=True):
                min_salary = gr.Slider(0, 20, 0, label="最低薪资(K/月)")
                major_filter = gr.Dropdown(["不限", "计算机", "电子", "机械", "自动化"], label="专业要求", value="不限")
            
            start_btn = gr.Button("开始智能匹配", variant="primary")
        
        with gr.Column(scale=2):
            gr.Markdown("### 实时匹配结果")
            result_html = gr.HTML(label="匹配结果")
            
            gr.Markdown("### 🛠 操作面板")
            with gr.Row():
                gr.Button("保存结果", variant="secondary")
                gr.Button("发送通知", variant="secondary")
                gr.Button("重新匹配", variant="secondary")

    # 事件绑定
    start_btn.click(
        fn=match_process,
        inputs=[resume_upload, company_upload, min_salary, major_filter],
        outputs=result_html
    )

demo.launch(server_port=7860, share=True)