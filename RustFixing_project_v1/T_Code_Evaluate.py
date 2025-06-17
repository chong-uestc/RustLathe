import subprocess
import re
from openai import OpenAI
from pathlib import Path
import os

import json
import socket
import threading

import numpy as np
import pandas as pd

#count the amount of different kinds of codes
correct_code_amount = 0
partial_correct_code_amount = 0
serious_problem_code_amount = 0
fail_miri_test_code_amount = 0
original_pass_num = 0

def read_code_from_file(filepath):
    """从文件中读取代码"""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"No solution can solve {PATH_NAME}!")
        return ""
    except Exception as e:
        print(f"Other problems: {e}")
        return ""

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

client = OpenAI(
    api_key="",
    base_url=""
)

def gpt_analyze_code(prompt, original_code_snippet,error_message,edited_code_snippet):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\nOriginal Code Snippet:\n{original_code_snippet}\nError Information:\n{error_message}\nEdited Code Snippet:\n{edited_code_snippet}"}],
        stream=False,
    )
    temperature=0.5
    # max_tokens=64,
    # top_p=1
  
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion

def agent_code_analyze(original_code_snippet,error_message,edited_code_snippet):
    #step to generate analysis
    prompt = "You will first be provided with an original code snippet in Rust language which has undefined behaviors.\n\
                You will second be provided with the error information from the miri test of the code snippet.\n\
                Finally, you will be provided with an edited code snippet in Rust which has PASSED the miri test.\n\
                Your task is to check if the edited code snippet solves the undefined hehavior existing in the original code and keep the original core functionality at the same time.\n\
                Do not provide a corrected version.\n\
                Evaluation Steps:\n\
                1. Read the original code snippet and analyze its logic.\n\
                2. Read the error information from the miri test carefully and identify the errors required to handle.\n\
                3. Read the edited code snippet and analyze its logic. Figure out the edited code solving the errors or not. Check the assertion carefully.\n\
                4. Make sure whether the edited code snippet changes the core functionality of the original code snippet heavily.\n\
                5. Finally, conclude your evaluation.\n\
                Please evaluate step by step.\n\
                Output format is like:\
                1. **Original Code Analysis**:<analysis of original code>\
                2. **Error Information**:<analysis of error information>\
                3. **Edited Code Analysis**:<analysis of edited code>\
                4. **Core Functionality Check**:<check of core funcionality>\
                5. **Conclusion**:<conclusion of evaluation>\
                "
    analysis = gpt_analyze_code(prompt,original_code_snippet,error_message,edited_code_snippet)
    return analysis

#NOT USED
def analysis_conclude(analysis):
    #only let the conclusion remained
    conclusion_start = analysis.find("**Conclusion**:")
    if conclusion_start != -1:
        analysis_conclusion = analysis[conclusion_start:].strip()
    else:
        analysis_conclusion = "No conclusion found!"
    return analysis_conclusion
#NOT USED


def gpt_summarize_code(prompt,analysis):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f'{prompt}\nAnalysis Result:\n{analysis}\nOnly output "Yes" or "No"!'}],
        stream=False,
    )
    temperature=0.5
    # max_tokens=64,
    # top_p=1
  
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion

def agent_code_summarization(analysis):
    #step to generate summarization
    prompt = 'You will be provided with an analysis result of an edited code snippet, which is aimed to solve the errors of the original code snippet and keep the original functionality.\n\
                "**Conclusion**" is important!\n\
                1. If the analysis believes that the core functionality is changed or altered, output: "No".\n\
                2. If the analysis believes that the logic is changed, output: "No".\n\
                3. If the analysis believes that the original intent is changed, output: "No".\n\
                4. If 1,2,3 do not exist, and the analysis believes that the edited code snippet is successful, output: "Yes".\n\
                Think step by step!\n\
                '
    summarization = gpt_summarize_code(prompt,analysis)
    return summarization


#Filter to check the use of assertion starts!
def agent_assertion_analyze(original_code_snippet,error_message,edited_code_snippet):
    #separately analyze the assertion like a filter
    prompt = 'You will first be provided with an original code snippet in Rust language which has undefined behaviors.\n\
                You will second be provided with the error information from the miri test of the code snippet.\n\
                Finally, you will be provided with an edited code snippet in Rust which has PASSED the miri test.\n\
                Your task is to analyze if the edited code snippet uses assertion correctly to solve undefined behavior and maintains the original functionality.\n\
                Analyze steps:\n\
                1. Check the edited code snippet using assertion "assert!" "assert_eq!" to solve the undefined behavior or not. If used, go to the next step. Otherwise, conclude.\n\
                2. Check the assertion if it catches the error(the undefined behavior) before they occur.\n\
                3. Check the assertion if it makes the edited code maintain the main logic and functionality.\n\
                4. Finally, conclude your check.\n\
                Analyze step by step!\n\
                Output format is like:\
                1. **Assertion Using Analysis**:<analysis of assertion using>\
                2. **Error Catching Analysis**:<analysis of error catching>\
                3. **Logic Analysis**:<analysis of logic>\
                4. **Conclusion**:<conclusion of analysis>\
                '
    assertion_analysis = gpt_analyze_code(prompt,original_code_snippet,error_message,edited_code_snippet)
    #output the analysis of assertion
    #print(assertion_analysis)
    return assertion_analysis

def agent_assertion_summarization(assertion_analysis):
    #step to generate summarization
    prompt = 'You will be provided with a conclusion of an edited code snippet, which is aimed to judge the assertion use.\n\
                "**Conclusion**" is important!\n\
                If the analysis believes that the edited code does NOT use assertion, output: "No".\
                If the analysis believes that the assertion use is correct, output: "Yes".\
                If the analysis believes that the assertion makes the original functionality lost, output: "No".\
                '
    summarization = gpt_summarize_code(prompt,assertion_analysis)
    return summarization

def agent_assertion_judge(original_code_snippet,error_message,edited_code_snippet):
    assertion_analysis = agent_assertion_analyze(original_code_snippet,error_message,edited_code_snippet)
    summarization = agent_assertion_summarization(assertion_analysis)
    return summarization
#Assertion judge end


def gpt_fault_localize_code(prompt, original_code_snippet,edited_code_snippet,analysis,taxonomy):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\nOriginal Code Snippet:\n{original_code_snippet}\nEdited Code Snippet:\n{edited_code_snippet}\nAnalysis:\n{analysis}\nCatalog of Common Inconsistencies:{taxonomy}"}],
        stream=False,
    )
    temperature=0.5
    # max_tokens=64,
    # top_p=1
  
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion

def agent_fault_localize(original_code_snippet,error_message,edited_code_snippet,analysis):
    #localize faults of generated code
    prompt = 'You will first be provided with an original code snippet in Rust language which has undefined behaviors.\n\
                You will second be provided with an edited code snippet in Rust which has PASSED the miri test.\n\
                You will third be provided with an analysis which analyzes if the edited code snippet solves the undefined behavior existing in the original code and maintains the original core functionality at the same time.\n\
                Finally, you will be provided with a catalog of code inconsistencies.\n\
                Evaluation Steps:\n\
                1. Read the original code snippet and the edited code snippet.\n\
                2. Read the analysis carefully, and conscientiously identify two issues:(When reading the analysis,conclusion is IMPORTANT!!!)\n\
                i) Identify whether the edited code snippet solves the undefined behavior existing in the original code.\n\
                ii) Identify whether the edited code snippet keep the original core functionality at the same time.\n\
                3. Output your answer in a JSON format list.\n\
                a) If the edited code snippet solves the undefined behavior and maintains the original core functionality, it is correct. Output: [{"inconsistency": "None", "severity": "Negligible"}].\n\
                b) If the edited code snippet does not meet the above condition, it is incorrect. Output the identified inconsistencies and their severity according to the catalog of code inconsistencies.\n\
                For example: [{"inconsistency": "<inconsistency1>", "severity": "<severity>", "inconsistency": "<inconsistency2>", "severity": "<severity>", ...}]\
                '
    taxonomy = 'inconsistency1: Missing dependency declarations; severity: Negligible\n\
                inconsistency2: Inefficiency, unnecessary statements; severity: Negligible\n\
                inconsistency3: Use safe alternatives to replace unsafe APIs or unsafe functions without changing core functionality; severity: Negligible\n\
                inconsistency4: The edited code partially change the intended functionality of the original code; severity: Medium\n\
                inconsistency5: Serious logic error exists; severity: Serious\n\
                inconsistency6: Code functionality is totally changed or lost; severity: Serious\n\
                inconsistency7: Not effectively solve the undefined behavior present in the original code; severity: Serious\n\
                inconsistency8: The edited code is not completed or is none; severity: Fatal\n\
                (Match the inconsistency step by step!)\n\
                Evaluation Form:\n\
                JSON output (a JSON list only):\n\
                For example: [{"inconsistency": "The edited code partially change the intended functionality of the original code", "severity": "Medium"}]\
                '
    #Only use conclusion as analysis to input.
    #analysis = analysis_conclude(analysis)
    summarization = agent_code_summarization(analysis)
    if summarization == "No":
        summarization = agent_assertion_judge(original_code_snippet,error_message,edited_code_snippet)
        #output the extra judgement of assertion use
        print("Extra assertion judge:",summarization)
        if summarization == "No":
            #not use assertion or assertion is incorrect
            print("The edited code is incorrect!")
            fault_localization = gpt_fault_localize_code(prompt,original_code_snippet,edited_code_snippet,analysis,taxonomy)
    if summarization == "Yes":
        print("The edited code is correct!")
        fault_localization = '```json\n[{"inconsistency": "None", "severity": "Negligible"}]\n```'
    return fault_localization

def clean_json_string(s):
    if s.startswith("```json") and s.endswith("```"):
        return s[7:-3].replace("\n","").strip()
    return s.strip()

def score_code(fault_localization):
    #score the edited code based on fault_localization
    #print(f"Fault localization is:{fault_localization}")
    data = json.loads(clean_json_string(fault_localization))
    medium_num = sum(1 for item in data if item.get("severity") == "Medium")
    serious_num = sum(1 for item in data if item.get("severity") == "Serious")
    fatal_num = sum(1 for item in data if item.get("severity") == "Fatal")
    # calculate M, S, F and Penalty
    M = medium_num * 5
    S = serious_num * 50
    F = fatal_num * 100
    Penalty = max(-100, -(S + M + F))
    # calculate the final score
    score = 1 + Penalty / 100
    return score

def calculate_different_kinds_of_code(score):
    global fail_miri_test_code_amount,correct_code_amount,partial_correct_code_amount,serious_problem_code_amount
    if score == -1:
        fail_miri_test_code_amount+=1
    if score == 1:
        correct_code_amount+=1
    if score > 0.5 and score < 1:
        partial_correct_code_amount+=1
    if score >= 0 and score <= 0.5:
        serious_problem_code_amount+=1    

def evalutate_code(original_file_path):
    #analyze the original code and the edited code, get evaluation with a format of fault_localization
    original_code = read_code_from_file(original_file_path)
    error_message, returncode = run_cargo_miri(original_code)
    errors = count_errors(error_message)
   
    if errors != 0:
        #only evalutate the orignial codes not passing miri test!
        edited_file_path = '/home/wyc/save_claude_3.5/edited_code_saving/' + PATH_NAME + '_edited.rs'
        edited_code = read_code_from_file(edited_file_path)
        if edited_code != '':
            #solutions CAN solve the undefined behavior
            analysis = agent_code_analyze(original_code,error_message,edited_code)
            fault_localization = agent_fault_localize(original_code,error_message,edited_code,analysis)
            score = score_code(fault_localization)
            print(f"{PATH_NAME} Evaluation:\n{fault_localization}")
            print(f"{PATH_NAME} Score: {score}")

            #record score information,including analysis,fault localization
            record_file_path = '/home/wyc/save_claude_3.5/score_recording/' + PATH_NAME + '_record.txt'
            with open(record_file_path, 'w', encoding='utf-8') as file:
                file.write(f"Analysis:\n{analysis}\n\nFault localization:\n{fault_localization}\nScore:{score}")
        else:
            #solutions CANNOT solve the undefined behavior
            score = -1
            #record score information,and the situation that solutions cannot solve errors
            record_file_path = '/home/wyc/save_claude_3.5/score_recording/' + PATH_NAME + '_record.txt'
            with open(record_file_path, 'w', encoding='utf-8') as file:
                file.write(f"Solutions CANNOT solve the undefined behavior of {PATH_NAME}!\nScore:{score}")
    
        calculate_different_kinds_of_code(score)
    
    else:
        print("The original code passes miri test!")
        global original_pass_num
        original_pass_num+=1

def evaluate_files_in_directory(directory_path):
    """处理目录下的所有Rust文件"""
    pathlist = Path(directory_path).rglob('*.rs')
    for path in pathlist:
        # 因为path是Path对象，所以转换为字符串
        global PATH_NAME
        PATH_NAME = path.stem
        print(f"Evaluting code {PATH_NAME}:")
        evalutate_code(str(path))

if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/rust_one_trial'
    evaluate_files_in_directory(directory_path)
    all_code_num = correct_code_amount + fail_miri_test_code_amount + partial_correct_code_amount + serious_problem_code_amount
    print("\nOverall Statics Result:")
    if original_pass_num != 0:
        print(f"The amount of the original passed codes is:{original_pass_num}") 
    print(f"The amount of correct codes is:{correct_code_amount}\n\
The amount of failed codes is:{fail_miri_test_code_amount}\n\
The amount of partial correct codes is:{partial_correct_code_amount}\n\
The amount of codes with serious problems is:{serious_problem_code_amount}\n\
Pass@1: {(all_code_num-fail_miri_test_code_amount)/all_code_num}\n\
Exec@1: {correct_code_amount/all_code_num}")
