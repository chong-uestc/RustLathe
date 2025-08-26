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
    api_key="sk-iT55g2gYsI01wY3Q2ka2PokA4DdZPcIpbBmSCalmgqAiWbgE",
    base_url="https://api.pro365.top/v1/"
)

def gpt_analyze_code(prompt, original_code_snippet,error_message,edited_code_snippet):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\nOriginal Code Snippet:\n{original_code_snippet}\nError Information:\n{error_message}\nEdited Code Snippet:\n{edited_code_snippet}"}],
        stream=False,
        temperature=0.5,
        # max_tokens=64,
        top_p=1
    )

    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion

def agent_code_analyze(original_code_snippet,error_message,edited_code_snippet):
    #step to generate analysis
    # prompt = "You will first be provided with an original code snippet in Rust language which has undefined behaviors.\n\
    #             You will second be provided with the error information from the miri test of the code snippet.\n\
    #             Finally, you will be provided with an edited code snippet in Rust which has PASSED the miri test.\n\
    #             Your task is to check if the edited code snippet solves the undefined hehavior existing in the original code and keep the original core semantics at the same time.\n\
    #             Do not provide a corrected version.\n\
    #             Evaluation Steps:\n\
    #             1. Read the original code snippet and analyze its logic and goal.\n\
    #             2. Read the error information from the miri test carefully and identify the errors required to handle.\n\
    #             3. Read the edited code snippet and analyze its logic and goal. Figure out the edited code reaches the same goal of the original code or not.\n\
    #             4. Make sure whether the edited code snippet does not change the core semantics of the original code snippet.\
    #                 (Examine semantics from following aspects: functions and APIs used, return types, memory operations)\n\
    #             5. Finally, conclude your evaluation.\n\
    #             Please evaluate step by step.\n\
    #             Output format is like:\
    #             1. **Original Code Analysis**:<analysis of original code>\
    #             2. **Error Information**:<analysis of error information>\
    #             3. **Edited Code Analysis**:<analysis of edited code>\
    #             4. **Core Semantics Check**:<check of core Semantics>\
    #             5. **Conclusion**:<conclusion of evaluation>\
    #             "
    prompt = (
        "You are an expert Rust programming and software correctness evaluator specializing in memory safety, concurrency safety, "
        "and undefined behavior (UB) detection.\n"
        "\n"
        "You will be given:\n"
        "1. **Snippet A**: An unsafe Rust program that contains UB.\n"
        "2. **Miri Test Output**: The error information from running Snippet A under the Miri interpreter.\n"
        "3. **Snippet B**: A proposed 'fixed' version of Snippet A that has PASSED the Miri test.\n"
        "\n"
        "Your task is to determine whether Snippet B is a **semantic repair** of Snippet A, meaning:\n"
        "- The UB present in Snippet A is fully eliminated in Snippet B.\n"
        "- The core functional intent of Snippet A (what the program is supposed to accomplish) is preserved in Snippet B.\n"
        "- The fix does not simply bypass or replace the original logic entirely unless such replacement is the only way to remove UB while still preserving intended behavior.\n"
        "- In particular, **core functions or APIs explicitly invoked in Snippet A (e.g., `__rust_alloc`) must still be invoked in Snippet B, unless the UB arises from the impossibility of safely using them at all.**\n"
        "\n"
        "Analysis Guidelines:\n"
        "1. Read Snippet A and analyze its logic, goal, and intended functionality.\n"
        "2. Read the Miri test output and identify the specific UB issues that must be addressed (e.g., invalid pointer dereference, uninitialized memory, incorrect alignment, data race, double free).\n"
        "3. Read Snippet B and analyze how it works and what its goal is.\n"
        "4. Compare Snippet A and Snippet B to check whether Snippet B:\n"
        "   - Removes or prevents the UB using safe Rust constructs, correct unsafe usage, or equivalent logic.\n"
        "   - Preserves the core functional semantics (functions/APIs used, return values/types, memory operations, and control flow).\n"
        "   - Maintains calls to the same key APIs as in Snippet A, unless the API itself is inherently unfixable.\n"
        "5. Consider edge cases: Does Snippet B introduce new UB? Does it maintain memory safety, correctness, and intended results?\n"
        "6. Focus more on assertion (like assert!, assert_eq!), especially on assertion condition. If the condition leads to panic but it is irrational, the fix is incorrect."
        "\n"
        "Do not attempt to write or suggest a corrected version of the code.\n"
        "\n"
        "Please evaluate step-by-step.\n"
        "Output format:\n"
        "1. **Original Code Analysis**: <analysis of Snippet A>\n"
        "2. **Error Information**: <analysis of Miri output>\n"
        "3. **Edited Code Analysis**: <analysis of Snippet B>\n"
        "4. **Core Semantics Check**: <evaluation of semantic preservation>\n"
        "5. **Conclusion**: <Yes/No judgment on semantic repair, with justification>\n"
        "6. **Notes**: <optional notes on performance, safety, or trade-offs>\n"
        "\n"
        "### Example 1: Semantic Fix (Yes)\n"
        "**Snippet A**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 3);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Miri Output**:\n"
        "ERROR: creating allocation with non-power-of-two alignment\n"
        "\n"
        "**Snippet B**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        let ptr = __rust_alloc(1, 4); // fixed to valid alignment, preserves original API\n"
        "        if ptr.is_null() {\n"
        "            panic!(\"allocation failed\");\n"
        "        }\n"
        "    }\n"
        "}\n"
        "\n"
        "**Expected Output**:\n"
        "1. **Original Code Analysis**: Calls `__rust_alloc` with invalid alignment.\n"
        "2. **Error Information**: UB due to non-power-of-two alignment.\n"
        "3. **Edited Code Analysis**: Fixes alignment, still calls `__rust_alloc`.\n"
        "4. **Core Semantics Check**: Semantics preserved, UB removed.\n"
        "5. **Conclusion**: Yes.\n"
        "\n"
        "### Example 2: Not a Semantic Fix (No, API changed)\n"
        "**Snippet A**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 3);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Miri Output**:\n"
        "ERROR: creating allocation with non-power-of-two alignment\n"
        "\n"
        "**Snippet B**:\n"
        "fn main() {\n"
        "    let size: usize = 1;\n"
        "    let align: usize = 4;\n"
        "    let layout = std::alloc::Layout::from_size_align(size, align).unwrap();\n"
        "    let ptr = unsafe { std::alloc::alloc(layout) };\n"
        "    unsafe { std::alloc::dealloc(ptr, layout); }\n"
        "}\n"
        "\n"
        "**Expected Output**:\n"
        "1. **Original Code Analysis**: Calls `__rust_alloc` with invalid alignment.\n"
        "2. **Error Information**: UB due to non-power-of-two alignment.\n"
        "3. **Edited Code Analysis**: Changes allocator from `__rust_alloc` to `std::alloc::alloc`.\n"
        "4. **Core Semantics Check**: UB removed but core API call changed, so semantics not preserved.\n"
        "5. **Conclusion**: No.\n"
    )
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
        temperature=0.5,
        # max_tokens=64,
        top_p=1
    )
    
    if response.choices:
        suggestion = response.choices[0].message.content
        # print(suggestion)
    else:
        suggestion = "No suggestion found."

    return suggestion

def agent_code_summarization(analysis):
    #step to generate summarization
    prompt = 'You will be provided with an analysis result of an edited code snippet, which is aimed to solve the errors of the original code snippet without losing the original functionality.\n\
                "**Conclusion**" is important!\n\
                1. If the analysis believes that the core functionality is changed or altered, output: "No".\n\
                2. If the analysis believes that the original intent is changed, output: "No".\n\
                3. If 1,2,3 do not exist, and the analysis believes that the edited code snippet is successful, output: "Yes".\n\
                Think step by step!\n\
                '
    summarization = gpt_summarize_code(prompt,analysis)
    return summarization


#Filter to check the use of assertion starts!
def agent_assertion_analyze(original_code_snippet,error_message,edited_code_snippet):
    #separately analyze the assertion like a filter
    # prompt = 'You will first be provided with an original code snippet in Rust language which has undefined behaviors.\n\
    #             You will second be provided with the error information from the miri test of the code snippet.\n\
    #             Finally, you will be provided with an edited code snippet in Rust which has PASSED the miri test.\n\
    #             Your task is to analyze if the edited code snippet uses assertion correctly to solve undefined behavior and maintains the original functionality.\n\
    #             Analyze steps:\n\
    #             1. Check the edited code snippet using assertion "assert!" "assert_eq!" to solve the undefined behavior or not. If used, go to the next step. Otherwise, conclude.\n\
    #             2. Check the assertion if it catches the error(the undefined behavior) before they occur.\n\
    #             3. Check the assertion if it makes the edited code maintain the main logic and functionality.\
    #                 (If the subsequent code does not be executed because of the assertion BUT the assertion accurately catches the error, the main logic is CORRECTLY maintained!.)\n\
    #             4. Finally, conclude your check(Focuses more on assertion.)\n\
    #             Analyze step by step!\n\
    #             Output format is like:\
    #             1. **Assertion Using Analysis**:<analysis of assertion using>\
    #             2. **Error Catching Analysis**:<analysis of error catching>\
    #             3. **Logic Analysis**:<analysis of logic>\
    #             4. **Conclusion**:<conclusion of analysis>\
    #             '
    prompt = (
        "You are an expert Rust programming and software correctness evaluator specializing in memory safety and undefined behavior (UB).\n"
        "\n"
        "You will be given:\n"
        "1. An **original Rust code snippet** that contains undefined behavior.\n"
        "2. The **Miri test error output** describing the UB in the original code.\n"
        "3. An **edited Rust code snippet** that has PASSED the Miri test.\n"
        "\n"
        "Your task is to determine whether the edited code snippet correctly uses Rust assertions (`assert!`, `assert_eq!`) to eliminate UB **while preserving the original program's intent and functionality as much as possible**.\n"
        "\n"
        "Analysis Steps:\n"
        "1. **Assertion Usage Check**: Verify whether the edited code snippet introduces assertions (`assert!`, `assert_eq!`) as part of the UB fix. If no assertion is used, conclude immediately.\n"
        "2. **Error Catching Check**: Examine whether the assertion explicitly catches the condition that would otherwise lead to UB (e.g., invalid alignment, out-of-bounds indexing, null dereference) **before it occurs**.\n"
        "   - If the assertion fails and panics before UB happens, this is still considered a correct fix (defensive stop).\n"
        "   - If the assertion is unrelated or does not address the UB cause, it is incorrect.\n"
        "3. **Logic Preservation Check**: Analyze whether the edited code snippet still preserves the main logic and functionality of the original code:\n"
        "   - If the assertion guards the unsafe call or critical logic, preserving the same flow up until UB would have occurred, this is correct.\n"
        "   - If the assertion halts execution unnecessarily (without relation to UB) or changes the core program goal, this is incorrect.\n"
        "   - If the assertion replaces or removes the original unsafe operation entirely instead of guarding it, treat this as a failed fix.\n"
        "   - In particular, **core functions or APIs explicitly invoked in the original snippet (e.g., `__rust_alloc`) must still be invoked in the edited snippet, unless UB arises from the impossibility of safely calling them at all.**\n"
        "   - In particular, if the assertion fails and panics before UB happens, this is still considered a correct fix (defensive stop).\n"
        "4. **Conclusion**: Decide whether the assertion-based fix is correct.\n"
        "\n"
        "Output Format:\n"
        "1. **Assertion Using Analysis**: <analysis of assertion usage>\n"
        "2. **Error Catching Analysis**: <analysis of whether the assertion prevents UB>\n"
        "3. **Logic Analysis**: <analysis of whether main logic is preserved>\n"
        "4. **Conclusion**: <final judgment>\n"
        "\n"
        "### Example 1: Correct Assertion Fix (Yes)\n"
        "**Original Code**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 3);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Miri Error**: creating allocation with non-power-of-two alignment\n"
        "\n"
        "**Edited Code**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    assert!(3_u32.is_power_of_two(), \"Alignment must be power of two\");\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 3);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Expected Output**:\n"
        "1. **Assertion Using Analysis**: Assertion added before UB-causing call.\n"
        "2. **Error Catching Analysis**: Assertion checks `is_power_of_two`, directly addressing UB cause.\n"
        "3. **Logic Analysis**: Core logic (calling `__rust_alloc`) preserved, only guarded.\n"
        "4. **Conclusion**: Yes.\n"
        "\n"
        "### Example 2: Correct Defensive Assertion Fix (Yes, Even If Panic)\n"
        "**Original Code**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 1 << 30);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Miri Error**: exceeding rustc's maximum supported alignment (greater than 2^29)\n"
        "\n"
        "**Edited Code**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        assert!(1 << 30 <= 1 << 29, \"Alignment exceeds maximum supported value\");\n"
        "        __rust_alloc(1, 1 << 30);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Expected Output**:\n"
        "1. **Assertion Using Analysis**: Assertion added to guard alignment before unsafe call.\n"
        "2. **Error Catching Analysis**: Assertion checks maximum allowed alignment. Program panics before UB, which is acceptable.\n"
        "3. **Logic Analysis**: Original unsafe call preserved, guarded by assertion.\n"
        "4. **Conclusion**: Yes.\n"
        "\n"
        "### Example 3: Incorrect Assertion Fix (No, Assertion Misapplied)\n"
        "**Original Code**:\n"
        "extern \"Rust\" {\n"
        "    fn __rust_alloc(size: usize, align: usize) -> *mut u8;\n"
        "}\n"
        "fn main() {\n"
        "    unsafe {\n"
        "        __rust_alloc(1, 3);\n"
        "    }\n"
        "}\n"
        "\n"
        "**Miri Error**: creating allocation with non-power-of-two alignment\n"
        "\n"
        "**Edited Code**:\n"
        "fn main() {\n"
        "    assert!(true, \"Alignment ok\"); // assertion unrelated to UB\n"
        "}\n"
        "\n"
        "**Expected Output**:\n"
        "1. **Assertion Using Analysis**: Assertion added but unrelated to UB.\n"
        "2. **Error Catching Analysis**: Does not prevent invalid alignment UB.\n"
        "3. **Logic Analysis**: Original API call removed, logic not preserved.\n"
        "4. **Conclusion**: No.\n"
    )
    assertion_analysis = gpt_analyze_code(prompt,original_code_snippet,error_message,edited_code_snippet)
    #output the analysis of assertion
    print("===ASSERTION ANALYSIS===")
    print(assertion_analysis)
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
    # take down the assertion using judge
    # record_file_path = '/home/wyc/save_claude_3.5/score_recording/' + PATH_NAME + '_record.txt'
    # with open(record_file_path, 'w', encoding='utf-8') as file:
    #     file.write(f"Assertion Analysis:\n{assertion_analysis}\n\nExtra assertion judge: {summarization}\n\n")
    return summarization
#Assertion judge end


def gpt_fault_localize_code(prompt, original_code_snippet,edited_code_snippet,analysis,taxonomy):
    """通过 GPT-4.0 处理代码和错误"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        # -----升级
        messages=[{"role": "user", "content": f"{prompt}\nOriginal Code Snippet:\n{original_code_snippet}\nEdited Code Snippet:\n{edited_code_snippet}\nAnalysis:\n{analysis}\nCatalog of Common Inconsistencies:{taxonomy}"}],
        stream=False,
        temperature=0.5,
        # max_tokens=64,
        top_p=1
    )

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
            if os.path.exists(record_file_path):
                with open(record_file_path, 'a', encoding='utf-8') as file:
                    file.write(f"Code Analysis:\n{analysis}\n\nFault localization:\n{fault_localization}\nScore:{score}")
            else: 
                with open(record_file_path, 'w', encoding='utf-8') as file:
                    file.write(f"Code Analysis:\n{analysis}\n\nFault localization:\n{fault_localization}\nScore:{score}")
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
