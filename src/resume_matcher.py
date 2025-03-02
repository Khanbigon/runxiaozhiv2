import json
import pandas as pd
from typing import List, Dict, Tuple
from langchain_community.embeddings import HuggingFaceEmbeddings  # 导入HuggingFace的文本嵌入模型
from langchain_community.vectorstores import Chroma  # 导入向量数据库
from langchain.text_splitter import CharacterTextSplitter  # 文本分割工具
import os
from dotenv import load_dotenv  # 环境变量加载工具
from chromadb.utils import embedding_functions
import chromadb

#实现逻辑：
#1.初始化简历匹配器，加载职位数据和简历数据
#2.将职位数据转换为向量形式，存储在向量数据库chromadb中，vectorstore是collection类型
#3.为每个简历匹配最适合的职位，返回匹配结果
#4.匹配结果包括公司名称、职位名称、职位要求、薪资范围、匹配度
#5.匹配度是根据简历和职位的相似度计算得到的
#核心函数collection.query()是从ChromaDB查询结果中获取的。
#ChromaDB是一个向量数据库，它可以存储文本的向量表示，并支持高效的相似度搜索。查询时，ChromaDB会返回与查询文本最相似的文本及其相似度距离。



# 简历匹配器类：用于实现简历与职位的智能匹配
class ResumeJobMatcher:
    def __init__(self, job_data_path: str, resume_data_path: str):
        """
        初始化简历匹配器
        :param job_data_path: Excel文件路径，包含企业岗位信息，预期包含列：公司名称、职位名称、职位要求、薪资范围
        :param resume_data_path: JSON文件路径，包含简历信息，包括基本信息、专业技能、工作经历等
        """
        self.job_data = pd.read_excel(job_data_path)  # 读取职位数据Excel文件
        with open(resume_data_path, 'r', encoding='utf-8') as f:
            self.resume_data = json.load(f)  # 读取简历JSON数据
        
        # 初始化文本嵌入模型，用于将文本转换为向量
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-zh-v1.5",  # 使用中文预训练模型
            model_kwargs={'device': 'cuda'}  # 使用GPU加速处理
        )
        self.job_vectorstore = self._create_job_vectorstore()  # 创建职位向量数据库
        self.client = chromadb.Client()
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        # Initialize the collection in constructor
        self._initialize_collection()

    def _initialize_collection(self):
        """
        Initialize or reset the jobs collection
        """
        # Try to delete existing collection if it exists
        try:
            self.client.delete_collection("jobs_collection")
        except:
            pass
        
        # Create new collection
        self.collection = self.client.create_collection(
            name="jobs_collection",
            embedding_function=self.embedding_function
        )
        
        # Add job data to collection
        job_texts = [
            self._format_job_text(job) for _, job in self.job_data.iterrows()
        ]
        self.collection.add(
            documents=job_texts,
            ids=[f"job_{i}" for i in range(len(job_texts))]
        )

    def _create_job_vectorstore(self) -> Chroma:
        """
        创建职位信息的向量数据库
        将所有职位信息转换为向量形式，用于后续的相似度匹配
        :return: 返回创建好的向量数据库
        """
        # 准备数据结构
        job_texts = []  # 存储所有职位描述文本
        metadatas = []  # 存储职位的元数据信息
        
        # 遍历每个职位记录，转换为文本格式
        for _, row in self.job_data.iterrows():
            job_text = self._format_job_text(row)  # 将职位信息格式化为文本
            job_texts.append(job_text)
            
            # 保存职位的关键信息作为元数据
            metadatas.append({
                'company': row['单位名称'],  # 公司名称
                'position': row['岗位名称'],  # 职位名称
                'salary': str(row['最低薪资（K/月）']) + '-' + str(row['最高薪资（K/月）']) + '千',  # 薪资范围
                'requirements': row['岗位要求']  # 职位要求
            })

        # 创建向量数据库
        vectorstore = Chroma.from_texts(
            texts=job_texts,  # 职位描述文本列表
            embedding=self.embeddings,  # 使用的嵌入模型
            metadatas=metadatas,  # 职位元数据
            collection_name="jobs"  # 集合名称
        )
        return vectorstore

    def _format_job_text(self, job_row: pd.Series) -> str:
        """
        将职位信息格式化为文本字符串，用于向量化处理
        :param job_row: 包含职位信息的DataFrame行
        :return: 格式化后的文本字符串
        """
        return f"""
        公司：{job_row['单位名称']}
        职位：{job_row['岗位名称']}
        要求：{job_row['岗位要求']}
        薪资：{str(job_row['最低薪资（K/月）']) + '-' + str(job_row['最高薪资（K/月）']) + '千'}
        """

    def _format_resume(self, resume: Dict) -> str:
        """
        将简历信息格式化为文本字符串，用于与职位进行匹配
        :param resume: 简历信息字典
        :return: 格式化后的文本字符串
        """
        text = f"""
        专业技能：{resume['专业技能']}
        工作经历：{resume['工作经历']}
        项目经历：{resume['项目经历']}
        教育经历：{resume['教育经历']['专业']} {resume['教育经历']['学历']}
        期望职位：{resume['意向岗位']['职位']}
        期望行业：{resume['意向岗位']['行业']}
        期望薪资：{resume['意向岗位']['薪资']}
        """
        return text

    def match_jobs(self, resume_index: int, top_k: int = 10) -> Tuple[List[Dict], str]:
        """
        为指定简历匹配最适合的职位
        :param resume_index: 要匹配的简历在简历列表中的索引
        :param top_k: 需要返回的最佳匹配职位数量
        :return: 返回一个元组：(匹配到的职位列表, 简历文本)
                匹配的职位列表中每个职位包含：公司名称、职位名称、职位要求、薪资范围、匹配度
        """
        # 获取并处理简历信息
        resume = self.resume_data[resume_index]  # 获取指定简历
        resume_text = self._format_resume(resume)  # 格式化简历文本
        
        # 打印简历信息
        print(f"匹配简历索引: {resume_index}")
        print(f"简历唯一标识: {resume['基本信息']['唯一标识']}")
        print(f"简历文本: {resume_text}")
        
        # Use the existing collection instead of creating a new one
        results = self.collection.query(
            query_texts=[resume_text],
            n_results=top_k
        )
        
        # 处理匹配结果
        matched_jobs = []
        for i, (job_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0])):
            job_index = int(job_id.split('_')[1])
            job = self.job_data.iloc[job_index]
        #在resume_matcher.py中，
        # distance是从ChromaDB查询结果中获取的。
        # ChromaDB是一个向量数据库，它可以存储文本
        # 的向量表示，并支持高效的相似度搜索。查询时，ChromaDB会返回与查询文本最相似的文本及其相似度距离。
            # 计算匹配度（将距离转换为百分比）
            match_percentage = int((1 - distance) * 100)
            
            matched_jobs.append({
                'company': job['单位名称'],
                'position': job['岗位名称'],
                'salary': str(job['最低薪资（K/月）']) + '-' + str(job['最高薪资（K/月）']) + '千',
                'requirements': job['岗位要求'],
                'match_percentage': match_percentage
            })
        
        # 打印匹配结果
        print(f"匹配到的职位数量: {len(matched_jobs)}")
        for job in matched_jobs:
            print(f"公司: {job['company']}, 职位: {job['position']}, 匹配度: {job['match_percentage']}%")
        
        return matched_jobs, resume_text