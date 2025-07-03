#!/bin/bash
export python_path="$HOME/code/Graduation_Desgin/RustFixing_project_v2"
export current_path=`pwd`

# function: if a folder doesn't exsit, create it
create_dir_if_not_exists() {
    dir_path="$1"
    if [ ! -d "$dir_path" ]; then
        mkdir -p "$dir_path"
        echo "Directory created: $dir_path"
    fi
}
# delete all record files
create_dir_if_not_exists "$HOME/save_improvement_file"
create_dir_if_not_exists "$HOME/save_improvement_file/solution_saving"
cd $HOME/save_improvement_file/solution_saving/
rm -rf *.txt
create_dir_if_not_exists "$HOME/save_improvement_file/edited_code_saving"
cd $HOME/save_improvement_file/edited_code_saving/
rm -rf *.rs
create_dir_if_not_exists "$HOME/save_improvement_file/failure"
cd $HOME/save_improvement_file/failure/
rm -rf *.rs
create_dir_if_not_exists "$HOME/save_improvement_file/pass"
cd $HOME/save_improvement_file/pass/
rm -rf *.rs
create_dir_if_not_exists "$HOME/save_improvement_file/score_recording"
cd $HOME/save_improvement_file/score_recording/
rm -rf *.txt

# delete all rust file processed before
create_dir_if_not_exists "$HOME/rust_thetis_test"
create_dir_if_not_exists "$HOME/rust_thetis_test/rust_one_trial"
       
cd $python_path
echo "Fast Thinking:"
python3 P_Fast_Thinking.py
echo "Slow Thinking:"
python3 P_Slow_Thinking.py
echo "Evaluating:"
python3 P_Code_Evaluate.py

# output the result: including fixed rust files and solution advice
cd $current_path

base_dir="$current_path/output"
code_dir="$base_dir/fixed_code"
solution_dir="$base_dir/solution_advice"

# check and create base_dir
if [ ! -d "$base_dir" ]; then
    mkdir -p "$base_dir"
    echo "Created directory: $base_dir"
fi

# check and create code_dir
if [ ! -d "$code_dir" ]; then
    mkdir -p "$code_dir"
    echo "Created directory: $code_dir"
fi

# check and create solution_dir
if [ ! -d "$solution_dir" ]; then
    mkdir -p "$solution_dir"
    echo "Created directory: $solution_dir"
fi

cp -r $HOME/save_improvement_file/solution_saving/*.txt "$solution_dir/"
cp -r $HOME/save_improvement_file/edited_code_saving/*.rs "$code_dir/"
rm -f $HOME/rust_thetis_test/rust_one_trial/*.rs 
