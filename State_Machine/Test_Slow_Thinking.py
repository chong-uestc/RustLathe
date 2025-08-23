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


code_count = 0
"""code count is used to record which code is processed"""

Best_Code = ""
client = OpenAI(
    api_key="sk-iT55g2gYsI01wY3Q2ka2PokA4DdZPcIpbBmSCalmgqAiWbgE",
    base_url="https://api.pro365.top/v1/"
)


def gpt_process_code(prompt, code_snippet,error_message):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\n\nThe code to fix is as below:\n{code_snippet}\nThe error message is as below:\n{error_message}"}],
        stream=False,
        temperature=0.5,
        # max_tokens=64,
        # top_p=1
    )

  
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion



def slow_process_files_in_directory(directory_path):
    """处理目录下的所有Rust文件"""
    pathlist = Path(directory_path).rglob('*.rs')
    # print("step1....")
    global code_count
    for path in pathlist:
        # 因为path是Path对象，所以转换为字符串
        global PATH_NAME
        PATH_NAME = path.stem
        code_count+=1
        print(f"Processing code number {code_count} {PATH_NAME}:")
        slow_process_code(str(path))

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



def modify_code(prompt,code_snippet,error_message):
    """根据 GPT-4.0 的建议修改代码"""
    suggestion = gpt_process_code(prompt,code_snippet,error_message)
    # print(f"Modification Suggestion from GPT-4.0:\n {suggestion}")
    # 实际修改代码逻辑（模拟）
    #initialize
    lines = suggestion.splitlines()
    start_marker = ["```Rust","```rust","```"]
    end_marker = "```"
    new_file_path = "/home/wyc/rust_test/src/main.rs"
    in_replacement_zone = False
    rust_code_blocks =[]
    current_block = []
    # new_lines = []
    # formal code 
    for line in lines:
        if in_replacement_zone:
            if end_marker in line:
                rust_code_blocks.append("\n".join(current_block))
                current_block = []
                in_replacement_zone = False
            else:
                current_block.append(line)
        elif any(marker in line for marker in start_marker):
            in_replacement_zone = True
            
    if current_block and in_replacement_zone:
        rust_code_blocks.append("\n".join(current_block))
    
    # print(rust_code_blocks)
    with open(new_file_path,'w') as file:
        file.writelines(rust_code_blocks)
    
    return new_file_path




#定义一个函数用来专门保存PASS过的检查和没有通过PASS的
def save_new_code(name,code,passed):  #True or False
    directory = "/home/wyc/save_claude_3.5/pass" if passed else "/home/wyc/save_claude_3.5/failure"
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # 生成文件名
    filename = f"new_{name}.rs"
    
    with open(os.path.join(directory, filename), 'w') as file:
        file.write(code)


def error_calculate(output):
    """calculate the exact amount of errors"""
    errors = count_errors(output)
    
    if errors != 0:        
        return errors-1
    else:
        return 0

def agent_function_call(agent_key,code,error_message):
    if agent_key == '1':
        code_fix = agent1(code,error_message)
    if agent_key == '2':
        code_fix = agent2(code,error_message)
    if agent_key == '3':
        code_fix = agent3(code,error_message)
    if agent_key == '4':
        code_fix = agent4(code,error_message)
    if agent_key == '5':
        code_fix = agent5(code,error_message)
    return code_fix

def slow_process_code(filepath):

    
    code = read_code_from_file(filepath)
    global Best_Code
    Best_Code = code
    output, returncode = run_cargo_miri(code)
    error_count = error_calculate(output)
    print("Begain: ",error_count," errors left")
   
    if error_count != 0:

        solution_file_path = '/home/wyc/save_claude_3.5/solution_saving/code_' + PATH_NAME + '_solution.txt'
        """find the solution file"""
        if not os.path.exists(solution_file_path):
            print("Solution file not found!")
            return
        with open(solution_file_path, "r", encoding="utf-8") as file:
            content = file.readlines()
        
        for line in content:
            """find different solutions"""
            match = re.match(r"Solution_(\d+): \[(.*?)\]", line)
            if match:
                solution_num = match.group(1)
                steps = match.group(2).split(", ")

                #before using another solution to process code,need to initialize code and best code
                code = read_code_from_file(filepath)
                Best_Code = code

                print(f"Processing Solution {solution_num}...")
                
                count_step = 0
                for step in steps:
                    """use 'Agent' to find different steps"""
                    agent_match = re.search(r"Agent(\d+)", step)
                    if agent_match:
                        count_step+=1
                        agent_key = agent_match.group(1)
                        print(f"Step{count_step}: ","Excuting Agent",agent_key)
                        code = agent_function_call(agent_key,code,output)

                        """adjust best code according to error count"""
                        error_count_past = error_count
                        output, returncode = run_cargo_miri(code)
                        error_count = error_calculate(output)
                        if error_count_past > error_count:
                            Best_Code = code
                        
                        print(f"After Step{count_step}: ",error_count,"errors left")
                        if error_count == 0:
                            break #jump out the steps circle
            if error_count == 0:
                break #jump out the solutions circle
        
        if error_count != 0:
            print(f"No solution can solve the error of {PATH_NAME}!")
            fail_code_file = '/home/wyc/save_claude_3.5/failure/' + PATH_NAME + '_failed.rs'
            with open(fail_code_file, 'w') as file:
                file.write(code)
        else:
            print(code)

            #try to solve the edited code
            edited_code_file = '/home/wyc/save_claude_3.5/edited_code_saving/' + PATH_NAME + '_edited.rs'
            with open(edited_code_file, 'w') as file:
                file.write(code)
    
    else:
        #code without error has saved in fast thinking, no need to save in slow thinking
        print("NO ERRORS!")
        print(code)
        return


# assertion 
def agent1(code,error_message):
    prompt = "You will be provide with a code snippet in Rust and its error information under miri test\
                1. Read the error information from the miri test carefully and identify the undefined behavior required to handle.\
                2. Fix the code snippet. Pre-assertions are added to determine before undefined behavior is possible, thus preventing undefined behavior from occurring.\
                3. Important and must do: Only assertions are added, no other modules of the code (including inputs, code structure, statements, etc.) are adjusted or deleted.\
                4. Output format: output only the proposed code in ``rust begin and ``end format."
    
    codepath = modify_code(prompt,code,error_message)
    code = read_code_from_file(codepath)
    
    return code

# modification
def agent2(code,error_message):
    prompt = "You will be provide with a code snippet in Rust and its error information under miri test. And the following is the idea of repair:\
                1. Read the error information from the miri test carefully and identify the undefined behavior required to handle.\
                2. The code to add assertions can not be modified, the code logic itself has problems.\
                3. Maintain the functionality and semantics of the source code, to avoid drastically changing the logical structure. \
                    For example, if the purpose is to access a field of a tuple, make sure that access to the field is carried out in a valid and safe memory range.\
                4. Design safe alternatives:Refactor the code according to safe alternatives. \
                    Ensure that the modified code not only avoids undefined behavior, but also maintains the original functional logic and performance standards.\
                5. Output only recommended code, starting with ``rust and ending with ```."
    codepath = modify_code(prompt,code,error_message)
    code = read_code_from_file(codepath)
    
    return code

# replacement
def agent3(code,error_message):
    prompt = "You will be provide with a code snippet in Rust and its error information under miri test. And the following is the idea of repair:\
                1. Read the error information from the miri test carefully and identify the undefined behavior required to handle.\
                2. The following code is a Rust code snippet that utilises unsafe APIs or unsafe functions. \
                3. Design safe alternatives for unsafe APIs or unsafe functions:Refactor the code according to safe alternatives. \
                4. Must and important maintains the original functionality! Functionally equivalent replacement!!\
                5. Output only recommended code, starting with ``rust and ending with ```."
    codepath = modify_code(prompt,code,error_message)
    code = read_code_from_file(codepath)
    
    return code
    
# rollback
def agent4(code,error_message):
    return Best_Code 

# knowledge 
def agent5(code,error_message):
    code_tag = refine(code,error_message)  #Undefined Behaviors ["use after free", "invalid memory reference", "double free risk", "memory corruption", "unsafe code block"]
    # 使用字符串操作提取方括号内的内容
    start = code_tag.find('[')
    end = code_tag.find(']')
    formatted_output = code_tag[start+1:end]     #"use after free", "invalid memory reference", "double free risk", "memory corruption", "unsafe code block"
    # print(formatted_output)
    
    code_embedding = get_embeddings(formatted_output)   #将代码转化为tag并embedding
    # print('code_embedding:',code_embedding)
    find_prompt = find_similar_errors(code_embedding)
    know_gencode = knowledge_modification(find_prompt,code,error_message)
    
    return know_gencode


def knowledge_modification(result,code,error_message):
    
    #提取 example_code、solution 和 solution_code 字段
    for key, value in result.items():
        sample_code = value['sample_code']
        solution_description = value['solution_description']
        solution_code = value['solution_code']
        
    prompt = f"1, Q:{sample_code}.\
              2, A:{solution_code}.\
              3. Please handle the new code segment and its undefined behavior.\
              4. Important and must:In the format {solution_description}, the presence of undefined behavior is resolved by assertion or code modification.\
              5. To maintain the functionality and semantics of the source code, to avoid drastically changing the logical structure.\
              6.Output format: output only the proposed code in ``rust begin and ``end format.\
              7. Let's think step by step"
    
    codepath = modify_code(prompt,code,error_message)
    code = read_code_from_file(codepath)
    
    return code 




def refine(content,error_message):
    prompt = ('You are a request summarizer, and you will be provided with a code existing undefined behaviors and its error information.'
                'You must summarize the undefined behaviors in the content of the requests I send.'
                'Requirements:'
                '1.Your answer should only include the summary content, without any other statements.'
                '2.Your summary should only have keywords.'
                '3.Your summary should consist of separate keywords.'
                '4.Your summary should summarize five keywords related to undefined behaviors. \
                   as much as possible, and represent a certain keyword in the following format:'
                'Undefined Behaviors ["<keyword1>", "<keyword2>", "<keyword3>", "<keyword4>", "<keyword5>"]'
                '5. Let us think step by step')

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\n\n Code:\n{content}\n Error Message:\n{error_message}\n"}],
        stream=False,
        temperature=0.5,
        # max_tokens=64,
        # top_p=1
    )
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."
        
    # code_embedding = get_embeddings(suggestion)
    
    return suggestion

## get embeddings
def get_embeddings(content):
    model = SentenceModel('shibing624/text2vec-base-chinese')
    sentence = content          # 返回 NumPy 数组
    vec = model.encode(sentence)

    return vec

##数据库插入tag对应向量
def Updata_embedding(embedding_tag,id):
    conn = psycopg2.connect(dbname='knowledgedb',user='postgres',password='451125',host='localhost',port='5432')
    cur = conn.cursor()
    cur.execute("""
        UPDATE query_database
        SET embedding = %s
        WHERE id = %s
    """,  (embedding_tag,id))
    
    conn.commit()
    cur.close()
    conn.close()
    

# # 计算相似度
def find_similar_errors(embedding):
    conn = psycopg2.connect(dbname='knowledgedb',user='postgres',password='451125',host='localhost',port='5432')
    cur = conn.cursor()
    # 将 NumPy 数组转换为列表并格式化为 PostgreSQL VECTOR 类型的字符串
    embedding_str = f"[{', '.join(map(str, embedding.tolist()))}]"
    
    # WHERE(embedding <-> %s::vector) >= 0.5
    cur.execute(
        """
        SELECT sample_code, solution_description, solution_code 
        FROM query_database
        ORDER BY embedding <-> %s::vector
        LIMIT 1;
        """, (embedding_str,))
    res = cur.fetchall()
    result = {}
    for i, (sample_code, solution_description, solution_code) in enumerate(res,1):
        result[f'Prompt{i}'] = {'sample_code':sample_code, 'solution_description':solution_description, 'solution_code':solution_code}
    cur.close()
    conn.close()
    print(result)
    return result



##knowledgebase 
if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/rust_one_trial'
    slow_process_files_in_directory(directory_path)

