from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)

RUST_CODE_DIR = os.path.expanduser("~/rust_thetis_test/rust_one_trial")
RUSTLATHE_SCRIPT = os.path.expanduser("~/code/Graduation_Desgin/RustLathe_code_repair/run_frontend.sh")
SAVE_DIR = os.path.expanduser("~/save_improvement_file")

@app.route('/')
def index():
    return send_from_directory('.', 'RustLathe.html')

@app.route('/run_rustlathe', methods=['POST'])
def run_rustlathe():
    if 'file' not in request.files:
        return jsonify({'error': '未接收到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(RUST_CODE_DIR, filename)
    os.makedirs(RUST_CODE_DIR, exist_ok=True)
    file.save(file_path)

    # 调用 RustLathe 执行脚本
    try:
        subprocess.run([RUSTLATHE_SCRIPT], check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({'error': 'RustLathe 执行失败', 'detail': str(e)}), 500

    # 获取输出内容
    edited_path = os.path.join(SAVE_DIR, "edited_code_saving", filename.replace(".rs", "_edited.rs"))
    solution_path = os.path.join(SAVE_DIR, "solution_saving", "code_"+filename.replace(".rs", "_solution.txt"))
    score_path = os.path.join(SAVE_DIR, "score_recording", filename.replace(".rs", "_record.txt"))
    def safe_read(path):
        return open(path, encoding='utf-8').read() if os.path.exists(path) else ""
    
    # 如果RustLathe修复失败，那么edited_path为空且solution_path存在，指定edited_code和score的输出内容
    if (safe_read(solution_path) != '' )and(safe_read(edited_path) == ''):
        result = {
        "edited_code": "糟糕,请检查上传文件,或参考建议手动修复Rust代码!",
        "solution": safe_read(solution_path),
        "score": "未生成有效修复代码！"
    }
    # RustLathe修复成功
    else:
        result = {
        "edited_code": safe_read(edited_path),
        "solution": safe_read(solution_path),
        "score": safe_read(score_path)
    }

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
