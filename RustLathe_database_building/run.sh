export path=`pwd`
cd /home/wyc/save_database_file/edited_code_saving/
rm -rf *
cd /home/wyc/save_database_file/failure/
rm -rf *
cd /home/wyc/save_database_file/pass/
rm -rf *
cd /home/wyc/save_database_file/score_recording/
rm -rf *
cd /home/wyc/save_database_file/solution_pass_filter/
rm -rf *
cd /home/wyc/save_database_file/solution_saving/
rm -rf *
cd /home/wyc/save_database_file/time_recording/
rm -rf *
cd $path
echo "Fast Thinking:"
python3 T_Fast_Thinking.py
echo "Slow Thinking:"
python3 T_Slow_Thinking.py
echo "Evaluating:"
python3 T_Code_Evaluate.py
echo "Table Constructing:"
python3 T_Table_Constructing.py
echo "Database Create:"
python3 SQL_create.py
