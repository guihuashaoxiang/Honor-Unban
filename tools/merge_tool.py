# tools/merge_tool.py
import os
import json
import time

# --- 配置 ---
# 源目录：存放所有按时间戳生成的截图和题库文件夹
SOURCE_DIRECTORY = "screenshots"
# 目标文件名：最终生成的主题库文件名
OUTPUT_FILE = "master_qa_bank.json"
# 单个题库文件的标准名称
SOLUTION_MAP_FILENAME = "solution_map.json"
# --- 配置结束 ---


def deep_merge_qa(master_qa, new_qa):
    """
    智能地深度合并两个题库。
    - master_qa: 主题库，将被原地修改。
    - new_qa: 新加载的题库。
    """
    for q_text, new_variants in new_qa.items():
        # 如果问题首次出现，直接添加
        if q_text not in master_qa:
            master_qa[q_text] = new_variants
            continue

        # 如果问题已存在，则需要合并变种列表
        # 使用一个字典来快速查找和更新变种，键是选项列表的元组形式
        # 注意：我们假设选项在生成时已经被排序
        master_variants_map = {tuple(v['options']): v for v in master_qa[q_text]}

        for variant in new_variants:
            # 将新变种的选项列表转为元组，作为唯一的键
            variant_key = tuple(variant['options'])
            # 新的变种会直接覆盖旧的，实现了“新答案覆盖旧答案”
            master_variants_map[variant_key] = variant

        # 将合并后的变种字典转换回列表
        master_qa[q_text] = list(master_variants_map.values())


def merge_qa_banks():
    """
    主函数，扫描、加载、合并并保存题库。
    """
    print("=============================================")
    print("==   智能题库合并工具 (Smart QA Merge)   ==")
    print("=============================================")
    print(f"源目录: {os.path.abspath(SOURCE_DIRECTORY)}")
    print(f"输出文件: {os.path.abspath(OUTPUT_FILE)}")

    if not os.path.isdir(SOURCE_DIRECTORY):
        print(f"\n错误：源目录 '{SOURCE_DIRECTORY}' 不存在。请检查路径配置。")
        return

    # 1. 自动扫描并按时间排序查找所有题库文件
    print(f"\n[步骤 1/3] 正在扫描 '{SOLUTION_MAP_FILENAME}' 文件...")
    files_to_merge = []
    for root, dirs, files in os.walk(SOURCE_DIRECTORY):
        # 按时间戳(目录名)排序，确保旧的文件夹先被处理
        dirs.sort()
        if SOLUTION_MAP_FILENAME in files:
            file_path = os.path.join(root, SOLUTION_MAP_FILENAME)
            files_to_merge.append(file_path)
            
    if not files_to_merge:
        print("\n未找到任何可合并的题库文件。")
        return

    print(f"\n成功找到 {len(files_to_merge)} 个题库文件，将按时间顺序合并：")
    for file in files_to_merge:
        print(f"  - {file}")

    # 2. 深度合并
    print(f"\n[步骤 2/3] 正在加载和深度合并题库...")
    merged_qa_bank = {}
    total_variants_loaded = 0
    
    for file_path in files_to_merge:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data: # 跳过空文件
                    print(f"  - 警告：文件 '{file_path}' 为空，已跳过。")
                    continue
                
                # 计算本次加载的变种数量
                num_variants_in_file = sum(len(variants) for variants in data.values())
                total_variants_loaded += num_variants_in_file
                
                # 执行深度合并
                deep_merge_qa(merged_qa_bank, data)
                
                print(f"  - 已从 '{file_path}' 加载并合并 {len(data)} 个问题，共 {num_variants_in_file} 个变种。")
        except json.JSONDecodeError:
            print(f"  - 警告：文件 '{file_path}' 不是有效的JSON格式，已跳过。")
        except Exception as e:
            print(f"  - 错误：处理文件 '{file_path}' 时发生错误: {e}")

    # 3. 保存最终的主题库
    print(f"\n[步骤 3/3] 正在生成主主题库文件...")
    
    final_question_count = len(merged_qa_bank)
    final_variant_count = sum(len(v) for v in merged_qa_bank.values())

    print(f"合并完成！")
    print(f"  - 总共处理了 {len(files_to_merge)} 个文件。")
    print(f"  - 最终题库包含 {final_question_count} 个独立问题。")
    print(f"  - 共计 {final_variant_count} 个问题变种（问题+选项组合）。")

    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged_qa_bank, f, ensure_ascii=False, indent=4)
        print(f"\n✅ 成功生成主主题库文件: {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"\n❌ 错误：写入主主题库文件时失败: {e}")


if __name__ == "__main__":
    merge_qa_banks()