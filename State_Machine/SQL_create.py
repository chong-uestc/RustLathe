import subprocess
import re
from openai import OpenAI
from pathlib import Path
import os

import json
import socket
import threading
import torch
import numpy as np
import pandas as pd
import requests
import psycopg2
from text2vec import SentenceModel 
from psycopg2.extensions import register_adapter, AsIs
psycopg2.extensions.register_adapter(np.float32, psycopg2._psycopg.AsIs)
# from openai.embeddings_utils import get_embedding, cosine_similarity




##knowledgebase create

## get embeddings
def get_embeddings(content):
    model = SentenceModel('shibing624/text2vec-base-chinese')
    sentence = content
    vec = model.encode(sentence)

    return vec

# 连接到PostgreSQL数据库
def connect_to_db():
    try:
        conn = psycopg2.connect(
            host="localhost",   # 替换为数据库主机地址
            dbname="agentdb",   # 替换为数据库名称
            user="postgres",   # 替换为数据库用户名
            password="451125",  # 替换为数据库密码
            port="5432"    # 替换为数据库端口
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


##数据库插入tag对应向量
def process_and_insert_data(file_path):
    df = pd.read_excel(file_path)
    print("read .....")
    
    # 连接数据库
    conn = connect_to_db()
    if conn is None:
        return

    cursor = conn.cursor()
    print("connect sucessful!!")
    
    #before inserting data, clear the table.
    #cursor.execute("DELETE FROM query_database;")
    #print("clear the content of table.........")

    # 遍历Excel文件中的每一行数据
    for index, row in df.iterrows():
        try:
            # 获取每一行的数据
            case_name = row['Case']
            code_feature = row['Code Feature']
            total_rounds = row['Total Rounds']
            total_success_rate = row['Total Success Rate']
            agent1_success_rate = row['Agent1 Success Rate']
            agent2_success_rate = row['Agent2 Success Rate']
            agent3_success_rate = row['Agent3 Success Rate']
            agent4_success_rate = row['Agent4 Success Rate']
            agent5_success_rate = row['Agent5 Success Rate']
    
            # 计算Tag的embedding向量
            embedding = get_embeddings(code_feature)
            
            #插入数据到数据库中
            cursor.execute("""
                           INSERT INTO query_database(case_name, code_feature, total_rounds, total_success_rate, agent1_success_rate, agent2_success_rate, agent3_success_rate, agent4_success_rate, agent5_success_rate, embedding) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                           """,(case_name, code_feature, total_rounds, total_success_rate, agent1_success_rate, agent2_success_rate, agent3_success_rate, agent4_success_rate, agent5_success_rate, embedding.tolist()))
            # 提交每一条数据的插入
            conn.commit()
            print("insert.........")

        except Exception as e:
            print(f"Error processing row {index}: {e}")
            conn.rollback()
    
    # 关闭数据库连接
    cursor.close()
    conn.close()
    

if __name__ == "__main__":
    file_path = '/home/wyc/code/State_Machine/rustlathe_analysis_result.xlsx'
    process_and_insert_data(file_path)
