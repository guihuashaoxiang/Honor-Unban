# tools/merge_tool.py
import os
import json
import time

# --- 配置 ---
# ... (配置部分保持不变) ...

def merge_qa_banks():
    # ... (前面的打印和目录检查保持不变) ...

    # 1. 自动扫描并查找所有题库文件
    print(f"\n[步骤 1/3] 正在扫描 '{SOURCE_DIRECTORY}' 目录下的所有 '{SOLUTION_MAP_FILENAME}' 文件...")
    
    files_to_merge = []
    for root, dirs, files in os.walk(SOURCE_DIRECTORY):
        if SOLUTION_MAP_FILENAME in files:
            file_path = os.path.join(root, SOLUTION_MAP_FILENAME)
            files_to_merge.append(file_path)
            
    if not files_to_merge:
        print("\n未找到任何可合并的题库文件。请先运行主程序生成题库。")
        return

    print(f"\n成功找到 {len(files_to_merge)} 个题库文件。")
    # for file in files_to_merge:  # 暂时注释掉未排序的打印
    #     print(f"  - {file}")

    # ========================== 关键修复：排序文件列表 ==========================
    # 在合并前，对文件列表进行排序。
    # 由于目录名是 YYYYMMDD_HHMMSS 格式，直接按字符串排序即可实现按时间升序。
    # 这能确保我们总是从最旧的记录合并到最新的记录，从而实现“新答案覆盖旧答案”。
    print("\n[新增步骤] 正在对文件列表按时间顺序排序...")
    files_to_merge.sort()
    print("排序完成！将按以下顺序合并：")
    for file in files_to_merge:
        print(f"  - {file}")
    # ========================== 修复结束 ==========================

    # 2. 合并与去重
    print(f"\n[步骤 2/3] 正在加载和合并题库...")
    
    merged_qa_bank = {}
    total_questions_loaded = 0

    # ... (后续的合并、写入和打印逻辑完全正确，无需修改) ...
    for file_path in files_to_merge:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                num_questions_in_file = len(data)
                total_questions_loaded += num_questions_in_file
                merged_qa_bank.update(data)
                print(f"  - 已从 '{file_path}' 加载 {num_questions_in_file} 道题目。")
        except json.JSONDecodeError:
            print(f"  - 警告：文件 '{file_path}' 不是有效的JSON格式，已跳过。")
        except Exception as e:
            print(f"  - 错误：读取文件 '{file_path}' 时发生错误: {e}")

    # ... (步骤 3 保持不变) ...
    print(f"\n[步骤 3/3] 正在生成主主题库文件 '{OUTPUT_FILE}'...")
    # ... (后续代码无需修改)

if __name__ == "__main__":
    merge_qa_banks()