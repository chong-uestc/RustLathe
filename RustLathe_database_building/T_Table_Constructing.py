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
from T_Slow_Thinking import run_cargo_miri, refine 

#get the agent list
def get_solution_steps(solution_line):
    match = re.match(r"Solution_(\d+): \[(.*?)\]", solution_line) #check the line to see if it is a solution
    if match:
        steps = match.group(2).split(", ") #split the solution into steps
        agent_list = list()
        for step in steps:
            """use 'Agent' to find different steps"""
            agent_match = re.search(r"Agent(\d+)", step) #find the agents in the solution
            if agent_match:
                agent_key = agent_match.group(1)
                agent_list.append(int(agent_key))
        print(agent_list)
        return agent_list

#get the score of each solution
def get_solution_score(score_recording_file_path):
    with open(score_recording_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if '***Score:***' in line:
                score_str = line.split('***Score:***')[-1].strip()
                score = float(score_str)
                break  # after finding the score, you can jump out of the circle
    return score

#get the processing time of each solution
def get_solution_time(time_recording_file_path):
    with open(time_recording_file_path, "r", encoding="utf-8") as file:
        solution_processing_time = file.read()
    return float(solution_processing_time)

#generate the dataframe of each case
def generate_one_case_dataframe(CASE_NAME, directory_path):
    #generate a case dictionary first
    passed_solution_saving_file = '/home/wyc/save_database_file/solution_pass_filter/' + CASE_NAME + '_passed_solution.txt'
    if os.path.isfile(passed_solution_saving_file):
        with open(passed_solution_saving_file, 'r', encoding="utf-8") as file:
            content = file.readlines()
        
        case_dictionary = {
            'case_name':[],
            'solution_steps':[],
            'solution_description':[],
            'sample_code':[],
            'solution_code':[],
            'tag':[],
            'score':[],
            'processing_time':[]
        }

        edited_code_count = 1
        #for one case, case name, sample code, tag do not need to change
        case_name = CASE_NAME
        original_code_path = directory_path + '/' +CASE_NAME + '.rs'
        with open(original_code_path, "r", encoding="utf-8") as file:
            sample_code = file.read()
        #get the tags of error code
        error_message = run_cargo_miri(sample_code)
        tag = refine(sample_code, error_message)

        #recording each solution into the dataframe
        for line in content:
            match = re.match(r"Solution_(\d+): \[(.*?)\]", line)
            if match:
                print(f"Processing {CASE_NAME}_edited{edited_code_count}.rs...")
                solution_steps = get_solution_steps(line)
                solution_description = line
                #get the solution code
                edited_code_folder = '/home/wyc/save_database_file/edited_code_saving/' + CASE_NAME
                edited_code_file = edited_code_folder + '/' + CASE_NAME + '_edited'+ str(edited_code_count) + '.rs'
                with open(edited_code_file, "r", encoding="utf-8") as file:
                    solution_code = file.read()
                #get the score
                record_folder_path = '/home/wyc/save_database_file/score_recording/' + CASE_NAME
                record_file_path = record_folder_path + '/' + CASE_NAME + '_record' + str(edited_code_count) + '.txt'
                score = get_solution_score(record_file_path)

                #get the processing time
                time_folder_path = '/home/wyc/save_database_file/time_recording/' + CASE_NAME
                time_file_path = time_folder_path + '/' + CASE_NAME + '_time_record' + str(edited_code_count) + '.txt'
                time = get_solution_time(time_file_path)
                
                #fill the case dictonary
                case_dictionary['case_name'].append(case_name)
                case_dictionary['solution_steps'].append(str(solution_steps))
                case_dictionary['solution_description'].append(solution_description)
                case_dictionary['sample_code'].append(sample_code)
                case_dictionary['solution_code'].append(solution_code)
                case_dictionary['tag'].append(tag)
                case_dictionary['score'].append(score)
                case_dictionary['processing_time'].append(time)
                
                print("Finished!")

                edited_code_count+=1
        
        #generate the dataframe of one case, and select the top 5 score items
        dataframe = pd.DataFrame(case_dictionary)
        selected_dataframe = dataframe.sort_values(by='score', ascending=False).head(5)
        return selected_dataframe
    
    else:
        print(f"Code {CASE_NAME} failed to be solved!")

#write into the excel table
def update_dataframe_to_excel(selected_dataframe):
    existing_excel = pd.read_excel('/home/wyc/save_database_file/knowledge_database.xlsx',engine='openpyxl')
    if existing_excel.isna().all().all(): #if excel is empty
        combined_excel = selected_dataframe
    else:
        combined_excel = pd.concat([existing_excel, selected_dataframe], ignore_index=True)
        combined_excel = combined_excel.drop_duplicates()
    combined_excel.to_excel('/home/wyc/save_database_file/knowledge_database.xlsx', index=False)

#construct the excel table of a whole rust file directory
def table_construct_in_directory(directory_path):
    # initialize the excel table to an empty excel
    empty_dictionary = {
        'case_name':[],
        'solution_steps':[],
        'solution_description':[],
        'sample_code':[],
        'solution_code':[],
        'tag':[],
        'score':[],
        'processing_time':[]
    }
    empty_excel = pd.DataFrame(empty_dictionary)
    empty_excel.to_excel('/home/wyc/save_database_file/knowledge_database.xlsx', index=False)

    pathlist = Path(directory_path).rglob('*.rs')
    code_count = 0
    for path in pathlist:
        # 因为path是Path对象，所以转换为字符串
        CASE_NAME = path.stem
        code_count+=1
        print(f"Recording code number {code_count} {CASE_NAME} to the excel table:")
        selected_dataframe = generate_one_case_dataframe(CASE_NAME, directory_path)
        update_dataframe_to_excel(selected_dataframe)
        print(f"Successfully write code number {code_count} {CASE_NAME} to the excel table!")

if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/both_borrows'
    table_construct_in_directory(directory_path)






