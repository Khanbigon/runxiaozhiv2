import os
import json
import time  # 添加缺失的time模块
from datetime import datetime
import requests
import re
from typing import List, Dict
import logging  # 添加日志模块

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请设置DEEPSEEK_API_KEY环境变量")
    
API_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

def call_deepseek_api(prompt: str, max_retries: int = 3) -> str:
    """
    调用DeepSeek API进行文本分析
    Args:
        prompt: 输入提示文本
        max_retries: 最大重试次数
    Returns:
        API响应的文本内容
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4  # 控制输出的随机性，值越低越稳定
    }

    for attempt in range(max_retries):
        try:
            logging.info(f"正在进行第{attempt + 1}次API调用")
            response = requests.post(API_ENDPOINT, json=payload, headers=headers, timeout=60)
            response.raise_for_status()  # 添加错误检查
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            logging.error(f"API调用失败: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(f"经过{max_retries}次尝试后调用仍然失败: {str(e)}")
            wait_time = 2 ** attempt
            logging.info(f"等待{wait_time}秒后重试")
            time.sleep(wait_time)

def process_batch(resume_text: str, jobs: List[Dict], batch_size: int = 5) -> List[Dict]:
    """
    批量处理简历和职位匹配分析
    Args:
        resume_text: 简历文本
        jobs: 职位列表
        batch_size: 每批处理的职位数量
    Returns:
        包含分析结果的列表
    """
    results = []
    total_batches = (len(jobs) + batch_size - 1) // batch_size
    
    for i in range(0, len(jobs), batch_size):
        batch_jobs = jobs[i:i + batch_size]
        current_batch = i // batch_size + 1
        logging.info(f"正在处理第{current_batch}/{total_batches}批职位")
        
        # 构建批量提示文本
        prompts = []
        for idx, job in enumerate(batch_jobs, 1):
            prompts.append(f"""### 岗位{idx}分析请求：
简历信息：{resume_text[:500]}...

职位信息：
公司：{job['company']}
职位：{job['position']}
薪资：{job['salary']}
要求：{job['requirements']}
匹配度：{job['match_percentage']}%
""")
        
        batch_prompt = "\n\n".join(prompts) + "\n\n请针对以上每个岗位分别给出优化建议，每条建议以『建议X：』(X为岗位编号)开头。"
        
        try:
            # 获取API响应
            response = call_deepseek_api(batch_prompt)
            
            # 提取建议
            suggestions = re.findall(r'建议(\d+)：(.+?)(?=\n建议\d+：|$)', response, re.DOTALL)
            
            # 将建议与职位匹配
            for job, (idx, suggestion) in zip(batch_jobs, suggestions):
                results.append({
                    "job": job,
                    "llm_analysis": suggestion.strip()
                })
        except Exception as e:
            logging.error(f"处理批次{current_batch}时发生错误: {str(e)}")
            continue
    
    return results

def main():
    """
    主函数：处理简历匹配结果并生成LLM分析
    """
    try:
        output_dir = os.path.join(os.getcwd(), "llm_output")
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载最新的匹配结果
        matching_files = [f for f in os.listdir("output") if f.startswith("matching_results_")]
        if not matching_files:
            raise FileNotFoundError("未找到匹配结果文件")
            
        latest_file = max(matching_files, key=lambda x: os.path.getctime(os.path.join("output", x)))
        logging.info(f"正在处理最新的匹配结果文件: {latest_file}")
        
        with open(os.path.join("output", latest_file), 'r', encoding='utf-8') as f:
            matching_results = json.load(f)
        
        llm_results = {}
        total_resumes = len(matching_results)
        
        for idx, (resume_id, data) in enumerate(matching_results.items(), 1):
            logging.info(f"正在处理简历 {resume_id} ({idx}/{total_resumes})")
            llm_results[resume_id] = {
                "resume_text": data["resume_text"],
                "job_analyses": process_batch(data["resume_text"], data["matched_jobs"]),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # 保存结果
        output_file = os.path.join(output_dir, f"llm_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(llm_results, f, ensure_ascii=False, indent=2)
        
        logging.info(f"LLM分析结果已保存到: {output_file}")
        
    except Exception as e:
        logging.error(f"程序执行过程中发生错误: {str(e)}")
        raise

if __name__ == "__main__":
    main()