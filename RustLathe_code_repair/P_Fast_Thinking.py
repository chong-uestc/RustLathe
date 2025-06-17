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
from P_Slow_Thinking import run_cargo_miri, refine, get_embeddings

client = OpenAI(
    api_key="",
    base_url=""
)



#定义一个函数用来专门保存PASS过的检查和没有通过PASS的
def save_new_code(name,code,passed):  #True or False
    directory = "/home/wyc/save_improvement_file/pass" if passed else "/home/wyc/save_improvement_file/failure"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # 生成文件名
    filename = f"{name}.rs"
    
    with open(os.path.join(directory, filename), 'w') as file:
        file.write(code)


def count_errors(output):
    """计算输出中的错误数量"""
    return len(re.findall(r"error(\[\w+\])?:", output))


def read_code_from_file(filepath):
    """从文件中读取代码"""
    with open(filepath, 'r', encoding='utf-8') as file:
        return file.read()


#calculate the embedding similarity, and select the most similar 10 solutions
def find_similar_errors(embedding):
    conn = psycopg2.connect(dbname='knowledgedb',user='postgres',password='451125',host='localhost',port='5432')
    cur = conn.cursor()
    # 将 NumPy 数组转换为列表并格式化为 PostgreSQL VECTOR 类型的字符串
    embedding_str = f"[{', '.join(map(str, embedding.tolist()))}]"
    
    # select 10 solutions according to similarity rank
    cur.execute(
        """
        SELECT solution_description 
        FROM query_database
        ORDER BY embedding <-> %s::vector
        LIMIT 10;
        """, (embedding_str,))
    res = cur.fetchall()
    result = {}
    for i, (solution_description,) in enumerate(res,1):
        result[f'Solution_{i}'] = {'solution_description':solution_description}
    cur.close()
    conn.close()
    #print(result)
    return result


def fast_process_code(filepath):

    code = read_code_from_file(filepath)
    
    error_message, returncode = run_cargo_miri(code)
    errors = count_errors(error_message)
    
    if errors != 0:
        #get the tags of the error code
        code_tag = refine(code,error_message)
        print("Successfully generate keywords!") 
        start = code_tag.find('[')
        end = code_tag.find(']')
        formatted_output = code_tag[start+1:end]

        code_embedding = get_embeddings(formatted_output)  #transform the code tags into embeddings
        result = find_similar_errors(code_embedding)
        solution_file = '/home/wyc/save_improvement_file/solution_saving/code_' + PATH_NAME + '_solution.txt'
        with open(solution_file, 'a') as file:
            for key, value in result.items():
                match = re.search(r'\[.*?\]', value['solution_description'])
                steps = match.group(0)
                print(f"{key}: {steps}")
                file.write(f"{key}: {steps}\n")
    
    else:
        #code without error will be saved in fast thinking 
        save_new_code(PATH_NAME,code,True)
        print("--------------------------------------")
        print("No Errors! No UBs")
        print("--------------------------------------")
        return

def fast_process_files_in_directory(directory_path):
    """处理目录下的所有Rust文件"""
    pathlist = Path(directory_path).rglob('*.rs')
    # print("step1....")
    code_count = 0
    for path in pathlist:
        # 因为path是Path对象，所以转换为字符串
        global PATH_NAME
        PATH_NAME = path.stem
        code_count+=1
        print(f"Processing code number {code_count} {PATH_NAME}:")
        fast_process_code(str(path))

if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/rust_one_trial'
    fast_process_files_in_directory(directory_path)