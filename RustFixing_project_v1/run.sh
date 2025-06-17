export path=`pwd`
cd /home/wyc/save_claude_3.5/solution_saving/
rm -rf *.txt
cd /home/wyc/save_claude_3.5/edited_code_saving/
rm -rf *.rs
cd /home/wyc/save_claude_3.5/failure/
rm -rf *.rs
cd /home/wyc/save_claude_3.5/pass/
rm -rf *.rs
cd /home/wyc/save_claude_3.5/score_recording/
rm -rf *.txt
cd $path
echo "Fast Thinking:"
python3 T_Fast_Thinking.py
echo "Slow Thinking:"
python3 T_Slow_Thinking.py
echo "Evaluating:"
python3 T_Code_Evaluate.py
