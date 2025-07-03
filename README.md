# RustLathe
RustLathe是一个大模型驱动的Rust智能修复框架。
## RustFixing文件夹
其中RustFixing_project_v1是RustBrain项目结合上语义评估模块，未加入自动化知识库生成模块。
这个文件夹中的项目可以视为“性能对照组”，并不隶属于RustLathe项目。
## RustLathe项目
### RustLathe_database_building
RustLathe_database_building是自动化知识库生成的部分，作用为筛选出语义评估分数高的解决方案并记录于知识库中。
### RustLathe_code_repair
RustLathe_code_repair是RustLathe的核心部分，利用生成的记忆知识库，完成针对性建议提供以及参考修复代码生成的功能。
在Rustlathe_code_repair中有两个shell脚本文件：（1）run.sh为在再Linux终端运行项目；（2）run_frontend.sh则在与前端页面交互时使用。
### Frontend
Frontend是RustLathe项目的前端交互设计部分。
