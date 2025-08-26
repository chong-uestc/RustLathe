import numpy as np
import psycopg2
from pathlib import Path
from psycopg2.extensions import register_adapter, AsIs
psycopg2.extensions.register_adapter(np.float32, psycopg2._psycopg.AsIs)
from Test_Slow_Thinking import read_code_from_file, run_cargo_miri, error_calculate, refine, get_embeddings, agent_function_call
from Test_Code_Evaluate import agent_code_analyze, agent_fault_localize, score_code

class StateMachine:
    def __init__(self):
        self.state = "INIT"
        self.repair_count = 0
        self.max_repair = 7  # 修复次数上限
        self.max_beyond_limits = 10 # 超次轮数上限
        self.case_name_count = {}  # 记录每个case_name被索引的次数
        self.used_agents = set()  # 记录所有已用过的agent
        self.best_rust_code = None  # 记录error数量最少的rust代码
        self.best_error_count = None  # 记录最少的error数量
    
    def run(self, rust_code):
        """运行状态机"""
        self.state = "INIT"
        print(f"进入状态: {self.state}")
        original_rust_code = rust_code # 记录下原始代码
        self.beyond_limits = 0

        while self.state != "END":
            if self.state == "INIT":
                self.repair_count = 0 # 如果语义评估失败重置为初始状态，修复次数需要置于0
                rust_code = original_rust_code # 如果语义评估失败重置为初始状态，rust_code需要重置为原始代码
                error_message, error_exist = self.miri_check(rust_code) # error_message是miri报错信息，error_exist是状态机跳转判断
                # 初始化 best_rust_code 和 best_error_count
                self.best_rust_code = rust_code
                self.best_error_count = error_calculate(error_message)
                original_error_message = error_message # 记录下原始报错信息
                if error_exist:
                    self.state = "SELECT_AGENT"
                else:
                    pass_code_file = '/home/wyc/save_improvement_file/pass/' + PATH_NAME + '_passed.rs'
                    with open(pass_code_file, 'w') as file:
                        file.write(original_rust_code)
                    self.state = "END"

            elif self.state == "SELECT_AGENT":
                agent_number = self.select_agent(rust_code, error_message)
                self.state = "AGENT_REPAIR"
                self.current_agent = agent_number

            elif self.state == "AGENT_REPAIR":
                self.repair_count += 1
                rust_code = self.current_agent_repair(rust_code, self.current_agent, error_message)
                error_message, error_exist = self.miri_check(rust_code)
                error_count = error_calculate(error_message)
                # 更新 best_rust_code
                if self.best_error_count is None or error_count < self.best_error_count:
                    self.best_error_count = error_count
                    self.best_rust_code = rust_code
                if error_exist:
                    if self.repair_count >= self.max_repair:
                        self.beyond_limits += 1
                        if self.beyond_limits >= self.max_beyond_limits:
                            print("修复次数超过上限，直接到 END")
                            print(f"{PATH_NAME}.rs存在的未定义行为难以解决，请人工核查!")
                            fail_code_file = '/home/wyc/save_improvement_file/failure/' + PATH_NAME + '_failed.rs'
                            with open(fail_code_file, 'w') as file:
                                file.write(original_rust_code)
                            self.state = "END"
                        else:
                            print(f"第{self.beyond_limits}轮修复失败，回到 INIT")
                            self.state = "INIT"
                    else:
                        self.state = "SELECT_AGENT"
                else:
                    self.state = "SEMANTIC_EVAL"

            elif self.state == "SEMANTIC_EVAL":
                if self.semantic_eval(rust_code, original_error_message, original_rust_code):
                    # 自动语义评估通过，把修复好的代码存储到本地
                    edited_code_file = '/home/wyc/save_improvement_file/edited_code_saving/' + PATH_NAME + '_edited.rs'
                    with open(edited_code_file, 'w') as file:
                        file.write(rust_code)
                    self.state = "END"
                else:
                    print("语义评估未通过，回到 INIT")
                    self.state = "INIT"

            print(f"当前状态 -> {self.state}")
        print("状态机结束")
        print(f"best_rust_code error_count: {self.best_error_count}")
        return rust_code

    # ====== 以下是功能函数的实现 ======

    def miri_check(self, code):
        error_message, returncode = run_cargo_miri(code)
        error_count = error_calculate(error_message)
        if error_count == 0:
            return error_message, False # False是无未定义行为
        else:
            return error_message, True # True是有未定义行为

    def select_agent(self, code, error_message):
        # 生成当前处理代码的特征标签以及向量
        code_tag = refine(code,error_message)
        print("Successfully generate keywords!") 
        start = code_tag.find('[')
        end = code_tag.find(']')
        formatted_output = code_tag[start+1:end]
        code_embedding = get_embeddings(formatted_output)  #将代码的特征标签转化为向量
        result = find_similar_errors(code_embedding)
        # 过滤出所有agent的成功率并转成浮点数
        agent_rates = { 
            key: float(value) for key, value in result.items() if key.startswith("agent")
        }
        # case_name计数
        print(f"database item is : {result['case_name']}")
        case_name = result.get('case_name', None)
        if case_name is not None:
            count = self.case_name_count.get(case_name, 0)
            self.case_name_count[case_name] = count + 1
        else:
            count = 0
        # 按成功率从高到低排序
        sorted_agents = sorted(agent_rates.items(), key=lambda x: x[1], reverse=True)
        # 跳过所有已用过的 agent，优先选未用过的 success_rate 高的 agent
        selected_agent = None
        for agent, _ in sorted_agents:
            if agent not in self.used_agents:
                selected_agent = agent
                break
        # 如果都用过了，则选 success_rate 最高的 agent，并清空used_agents
        if selected_agent is None:
            selected_agent = sorted_agents[0][0]
            self.used_agents = set() # 清空used_agents
        # 记录已用过的 agent
        self.used_agents.add(selected_agent)
        # 提取 agent 后面的数字
        selected_agent_number = selected_agent.replace("agent", "").replace("_success_rate", "")
        return selected_agent_number

    def current_agent_repair(self, code, agent_number, error_message):
        """调用 Agent 修复代码"""
        print(f"Agent{agent_number} 正在修复代码...")
        if agent_number != '4': 
            code = agent_function_call(agent_number, code, error_message)
        else:
            code = self.best_rust_code # agent4需要单独设置，回滚到error数量最少的rust代码
        return code

    def semantic_eval(self, code, original_error_message, original_rust_code):
        """模拟语义评估 (返回 True 表示通过)"""
        analysis = agent_code_analyze(original_rust_code, original_error_message, code) # 生成分析报告
        fault_localization = agent_fault_localize(original_rust_code, original_error_message, code, analysis) # 生成问题定位
        score = score_code(fault_localization) # 生成分数评估
        print(f"Evaluation:\n{fault_localization}")
        print(f"Score: {score}")
        if score == 1:
            # 自动语义评估通过的话则把语义评估的相关信息记录下来
            record_file_path = '/home/wyc/save_improvement_file/score_recording/' + PATH_NAME + '_record.txt'
            with open(record_file_path, 'w', encoding='utf-8') as file:
                file.write(f"Analysis:\n{analysis}\n\nFault localization:\n{fault_localization}\nScore:{score}")
            return True
        else:
            return False

# ========= 需要重写或者实现的子模块函数 =========

# # 计算相似度，在数据库中索引向量相似度最大的条目
def find_similar_errors(embedding):
    conn = psycopg2.connect(dbname='agentdb',user='postgres',password='451125',host='localhost',port='5432')
    cur = conn.cursor()
    # 将 NumPy 数组转换为列表并格式化为 PostgreSQL VECTOR 类型的字符串
    embedding_str = f"[{', '.join(map(str, embedding.tolist()))}]"
    
    # WHERE(embedding <-> %s::vector) >= 0.5
    cur.execute(
        """
        SELECT case_name, agent1_success_rate, agent2_success_rate, agent3_success_rate, agent4_success_rate, agent5_success_rate 
        FROM query_database
        ORDER BY embedding <-> %s::vector
        LIMIT 1;
        """, (embedding_str,))
    res = cur.fetchall()
    result = {} # result记录索引出来的相似度最高的数据库条目
    for i, (case_name, agent1_success_rate, agent2_success_rate, agent3_success_rate, agent4_success_rate, agent5_success_rate) in enumerate(res,1):
        result = {'case_name':case_name, 'agent1_success_rate':agent1_success_rate, 'agent2_success_rate':agent2_success_rate, 'agent3_success_rate':agent3_success_rate, 'agent4_success_rate':agent4_success_rate, 'agent5_success_rate':agent5_success_rate}
    cur.close()
    conn.close()
    # print(result)
    return result

def slow_process_files_in_directory(directory_path):
    """处理目录下的所有Rust文件"""
    pathlist = Path(directory_path).rglob('*.rs')
    # print("step1....")
    code_count = 0
    for path in pathlist: 
        # 因为path是Path对象，所以转换为字符串
        global PATH_NAME
        PATH_NAME = path.stem
        code_count += 1
        print(f"正在处理第{code_count}个Rust代码{PATH_NAME}.rs...")
        fsm = StateMachine()
        rust_code = read_code_from_file(str(path))
        result = fsm.run(rust_code)
        print("最终代码:\n", result)

# ========= 测试运行 =========
if __name__ == "__main__":
    directory_path = '/home/wyc/rust_thetis_test/rust_one_trial'
    slow_process_files_in_directory(directory_path)

