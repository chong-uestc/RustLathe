
import boto3
import json
import subprocess
import re
from openai import OpenAI
from pathlib import Path
import os
import socket
import threading

import numpy as np
import pandas as pd

code_count = 0
"""code count is used to record which code is processed"""

client = OpenAI(
    api_key="",
    base_url=""
)


def gpt_process_code(prompt, code_snippet,error_message):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\n\nThe code to fix is as below:\n{code_snippet}\nThe error message is as below:\n{error_message}"}],
        stream=False,
    )
    temperature=0.7
    n = 3
    # max_tokens=64,
    # top_p=1
  
    
    solutions = []
    if response.choices:
        for choice in response.choices:
            solutions.append(choice.message.content.strip())
    else:
        solutions.append("No suggestion found.")

    return solutions



def fast_process_files_in_directory(directory_path):
    """处理目录下的所有Rust文件"""
    pathlist = Path(directory_path).rglob('*.rs')
    # print("step1....")
    for path in pathlist:
        # 因为path是Path对象，所以转换为字符串
        global PATH_NAME
        PATH_NAME = path.stem
        global code_count
        code_count+=1
        print(f"Processing code number {code_count} {PATH_NAME}:")
        fast_process_code(str(path))

def read_code_from_file(filepath):
    """从文件中读取代码"""
    with open(filepath, 'r', encoding='utf-8') as file:
        return file.read()

# returncode它用来表示子进程的退出代码
def run_cargo_miri(code):
    """将代码写入临时文件并运行 cargo miri"""
    temp_file = '/home/wyc/rust_test/src/main.rs'
    # print("step4_1...")
    with open(temp_file, 'w') as file:
        file.write(code)
    # print("step4_2...")
    try:
        result = subprocess.run(['cargo', '+nightly-2024-10-01', 'miri', 'run'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd='/home/wyc/rust_test/src')
        # print("step4_3...")
        return result.stderr, result.returncode
    except Exception as e:
        print(f"Failed to run cargo miri: {str(e)}")
        return "", 1

def count_errors(output):
    """计算输出中的错误数量"""
    return len(re.findall(r"error(\[\w+\])?:", output))




#定义一个函数用来专门保存PASS过的检查和没有通过PASS的
def save_new_code(name,code,passed):  #True or False
    directory = "/home/wyc/save_database_file/pass" if passed else "/home/wyc/save_database_file/failure"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # 生成文件名
    filename = f"{name}.rs"
    
    with open(os.path.join(directory, filename), 'w') as file:
        file.write(code)

def fast_process_code(filepath):

    code = read_code_from_file(filepath)
    
    output, returncode = run_cargo_miri(code)
    errors = count_errors(output)
    
    if errors != 0:        
        prompt = "You are a Rust Language Expert. Your task is to analyze the Rust code and the error message of miri test I send you, \
                    and identify the key characteristics of the code, and generate multiple potential solutions based on these characteristics.\
                 Requirements:\
                 1.Summarize the characteristics of the code:Identify any usage of unsafe Rust operations, and categorize them based on common unsafe operation types (e.g., dereferencing raw pointers, calling unsafe functions, etc.).\
                    Read the error information from the miri test carefully and identify the errors required to handle. Assess if there are any potential Undefined Behavior (UB) patterns in the code, and specify the possible causes.\
                 2.Provide multiple agents to combine and generate a solution, including:\
                     (1)Agent1:Refactoring the unsafe code with safe Rust alternatives.\
                     (2)Agent2:Adding assertions to ensure safety during runtime.\
                     (3)Agent3:Modifying the code's logic or structure to ensure better safety while maintaining performance.\
                     (4)Agent4:Rollback mechanism.\
                     (5)Agent5:Knowledge base support.\
                 3.Please note that the generated solution is complete, and it is necessary to consider the follow-up measures if the step fails to solve the problem.\
                 4.Different agent orders, Different solutions.Consider flexibly incorporating the knowledge base agent into the steps, rather than being limited to the final step.\
                 5. Generate ten solutions: The generated solutions consist of a complete debugging system composed of (1), (2), (3), (4), (5) or other agent combinations, with different orders and solutions\
                 6. Output formal: [Important] must only only only  output solutions!! must only only only  output solutions!! Do not output anything else !! And in the following format:\
                        Solution_n: [step1:<Agent>:xxx, step2:<Agent>:xxx, step_n:<Agent>:xxx']\
                            For example:Solution_1: [step1: Agent1: Refactor the unsafe allocation with a safe Rust allocator instead of raw pointers, step2: Agent2: Add assertions to check if the allocation was successful, step3: Agent5: Consult knowledge base for best practices in memory allocation using safe Rust]\
                 7. Let us think step by step.\
                 "
        repair_solution = gpt_process_code(prompt,code,output)
        
        solutions = {}
        for i in range(1, 11):  # 从Solution_1到Solution_10
            # 使用正则表达式匹配Solution的名称和步骤
            solution_key = f"Solution_{i}"
            match = re.search(f"{solution_key}:\s*(\[[^\]]*\])", repair_solution[0])  # 查找Solution的内容
            if match:
                solutions[solution_key] = match.group(1)  # 提取并存储每个Solution的步骤列表

        """save solutions as txt files in a folder"""
        solution_file = '/home/wyc/save_database_file/solution_saving/code_' + PATH_NAME + '_solution.txt'
        # 打印每个Solution的步骤
        for solution, steps in solutions.items():
            print(f"{solution}: {steps}")
            """save the solutions"""
            with open(solution_file, 'a') as file:
                file.write(f"{solution}: {steps}\n")
            
    else:
        #code without error will be saved in fast thinking 
        save_new_code(PATH_NAME,code,True)
        print("--------------------------------------")
        print("No Errors! No UBs")
        print("--------------------------------------")
        return



##knowledgebase 
if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/both_borrows'
    fast_process_files_in_directory(directory_path)
