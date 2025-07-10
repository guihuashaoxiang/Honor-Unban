# auto_solver.py
import os
import re
import time
import json # 引入json库，用于优雅地保存和读取数据
import logging
from itertools import combinations
from collections import defaultdict
# 桌面自动化核心库
import pyautogui
from airtest.core.cv import Template
from paddleocr import PaddleOCR
# 引入转换所需的库
import numpy as np
import cv2

# ============================ 动态路径与全局变量配置 ============================
RUN_TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
LOG_FILE_PATH = os.path.join(LOG_DIR, f"{RUN_TIMESTAMP}.log")
SCREENSHOT_BASE_DIR = "screenshots"
SCREENSHOT_RUN_DIR = os.path.join(SCREENSHOT_BASE_DIR, RUN_TIMESTAMP)
if not os.path.exists(SCREENSHOT_RUN_DIR): os.makedirs(SCREENSHOT_RUN_DIR)

# 【新增】全局变量，用于存储已解答的题目及其正确答案
solved_questions = {}

# ==================== 日志配置 START ====================
# (日志部分保持不变, 但使用新的动态文件路径)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
# ==================== 日志配置 END ====================

# ==============================================================================
# ============================ 全局配置 =============================
# ==============================================================================
SCREEN_REGION = (2481, 0, 901, 2063)
SCROLL_MODE = 'BOTH'
FIXED_POST_SUBMIT_DELAY = 1
POST_TOUCH_DELAY = 0.8
POST_SCROLL_DELAY = 1.5
MAX_SINGLE_CHOICE_ATTEMPTS = 2
MAX_MULTI_CHOICE_ATTEMPTS = 3
MAX_SCROLL_ATTEMPTS = 3

# ------------------- 资源与模型定义 -------------------
TEMPLATES_DIR = "templates"
if not os.path.exists(TEMPLATES_DIR): 
    os.makedirs(TEMPLATES_DIR)
    logger.warning(f"模板目录 '{TEMPLATES_DIR}' 不存在，已自动创建。请将模板图片放入其中。")
def load_option_templates(directory, threshold=0.7):
    # ... (此函数无需修改) ...
    logger.info(f"开始从 '{directory}' 目录加载选项模板...")
    option_templates = defaultdict(list)
    try:
        filenames = os.listdir(directory)
    except FileNotFoundError:
        logger.error(f"模板目录 '{directory}' 未找到！脚本无法继续。")
        return {}
    pattern = re.compile(r"option_([A-D])_(\d+)\.png")
    for filename in sorted(filenames):
        match = pattern.match(filename)
        if match:
            option_name = match.group(1)
            full_path = os.path.join(directory, filename)
            template = Template(full_path, threshold=threshold)
            option_templates[option_name].append(template)
            logger.info(f"  -> 已加载模板: {filename} for Option {option_name}")
    logger.info("选项模板加载完成。")
    return dict(option_templates)

TEMPLATE_SUBMIT = Template(os.path.join(TEMPLATES_DIR, "submit_button.png"), threshold=0.85)
TEMPLATE_OPTIONS = load_option_templates(TEMPLATES_DIR, threshold=0.7)
logger.info("正在初始化OCR模型...")
try:
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
    logger.info("OCR模型初始化完成。")
except Exception as e:
    logger.error(f"OCR模型初始化失败: {e}"); exit()
logger.info(f"=========== 配置加载 ===========")
logger.info(f"日志文件将保存至: {LOG_FILE_PATH}")
logger.info(f"本次运行截图将保存至: {SCREENSHOT_RUN_DIR}")
logger.info(f"投屏区域 (Region): {SCREEN_REGION}")
logger.info(f"滚动模式 (Scroll Mode): {SCROLL_MODE}")

# --- 桌面操作核心函数 ---
# ... (capture_region, click_at_region_pos, scroll* 函数均无需修改) ...
def capture_region(filename=None):
    pil_img = pyautogui.screenshot(region=SCREEN_REGION)
    if filename:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        pil_img.save(filename)
        logger.info(f"截图已保存至: {filename}")
    np_array = np.array(pil_img)
    opencv_img = cv2.cvtColor(np_array, cv2.COLOR_RGB2BGR)
    return opencv_img
def click_at_region_pos(region_pos):
    if not region_pos: return
    absolute_x = SCREEN_REGION[0] + region_pos[0]
    absolute_y = SCREEN_REGION[1] + region_pos[1]
    pyautogui.click(absolute_x, absolute_y)
def _scroll_with_drag():
    logger.info("执行[拖动滚动]...")
    region_x, region_y, region_w, region_h = SCREEN_REGION
    drag_center_x = region_x + region_w // 2; start_y = region_y + region_h * 0.70; end_y = region_y + region_h * 0.30
    pyautogui.moveTo(drag_center_x, start_y, duration=0.2); pyautogui.mouseDown(); pyautogui.moveTo(drag_center_x, end_y, duration=0.5); pyautogui.mouseUp()
def _scroll_with_wheel():
    logger.info("执行[PC滚轮滚动]...")
    region_x, region_y, region_w, region_h = SCREEN_REGION
    center_x = region_x + region_w // 2; center_y = region_y + region_h // 2
    pyautogui.moveTo(center_x, center_y, duration=0.2); pyautogui.scroll(-500)
def scroll_in_region():
    if SCROLL_MODE == 'MOBILE_DRAG': _scroll_with_drag()
    elif SCROLL_MODE == 'PC_WHEEL': _scroll_with_wheel()
    elif SCROLL_MODE == 'BOTH': _scroll_with_drag(); time.sleep(0.3); _scroll_with_wheel()
    else: _scroll_with_drag()

# --- 逻辑函数 ---
def get_screen_info():
    # ... (此函数无需修改) ...
    screen_img = capture_region()
    try:
        result = ocr.ocr(screen_img, cls=True)
        if not result or not result[0]: return None, "单选题"
        full_text = " ".join([line[1][0] for line in result[0]])
        match = re.search(r'第(\d+|[一二三四五六七八九十百]+)题', full_text)
        question_num = f"第{match.group(1)}题" if match else None
        question_type = "多选题" if "多选" in full_text else "单选题"
        return question_num, question_type
    except Exception: return None, "单选题"

def find_submit_button_with_scroll(q_num, screenshot_dir):
    # ... (此函数无需修改) ...
    safe_q_num = re.sub(r'[\\/*?:"<>|]', "_", q_num)
    screenshot_path_1 = os.path.join(screenshot_dir, f"{safe_q_num}_1.png")
    screen_img = capture_region(filename=screenshot_path_1)
    submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
    if submit_pos: return submit_pos, False
    logger.info(f"未找到[提交按钮]，开始滚动查找...")
    for i in range(MAX_SCROLL_ATTEMPTS):
        scroll_in_region(); time.sleep(POST_SCROLL_DELAY)
        screen_img = capture_region()
        submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
        if submit_pos:
            screenshot_path_2 = os.path.join(screenshot_dir, f"{safe_q_num}_2.png")
            cv2.imwrite(screenshot_path_2, screen_img)
            logger.info(f"已保存滚动后的截图: {screenshot_path_2}")
            return submit_pos, True
    logger.warning(f"滚动后仍未找到[提交按钮]！"); return None, True

def find_available_options():
    # ... (此函数无需修改) ...
    available = {}; screen_img = capture_region()
    for name, template_list in sorted(TEMPLATE_OPTIONS.items()):
        for template in template_list:
            pos = template.match_in(screen_img)
            if pos: available[name] = pos; break
    if not available: logger.warning("未找到任何选项 (A, B, C, D)。")
    return available

# ============================ 【核心修改部分：解答函数返回正确答案】 ============================
def solve_single_choice(current_q_num, options, submit_pos):
    """【已重构】解答单选题，成功后返回正确选项。"""
    logger.info(f"开始解答单选题: {current_q_num}")
    for attempt in range(1, MAX_SINGLE_CHOICE_ATTEMPTS + 1):
        logger.info(f"--- 开始第 {attempt}/{MAX_SINGLE_CHOICE_ATTEMPTS} 轮单选题尝试 ---")
        for option_name in sorted(options.keys()):
            logger.info(f"尝试单选项 [{option_name}]...")
            click_at_region_pos(options[option_name]); time.sleep(POST_TOUCH_DELAY)
            click_at_region_pos(submit_pos)
            if wait_for_next_question(current_q_num):
                # 题目刷新成功，意味着当前选项是正确的
                logger.info(f"单选题 [{current_q_num}] 的正确答案是: [{option_name}]")
                return [option_name] # 返回包含正确选项的列表
            else:
                logger.info(f"选项 [{option_name}] 错误，继续...")
        logger.warning(f"第 {attempt} 轮尝试完成，题目仍未改变。")
    logger.error(f"单选题 {current_q_num} 在 {MAX_SINGLE_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return None # 所有尝试失败，返回 None

def solve_multiple_choice(current_q_num, options, submit_pos):
    """【已重构】解答多选题，成功后返回正确选项组合。"""
    logger.info(f"开始解答多选题: {current_q_num}")
    option_names = sorted(options.keys())
    for attempt in range(1, MAX_MULTI_CHOICE_ATTEMPTS + 1):
        logger.info(f"--- 开始第 {attempt}/{MAX_MULTI_CHOICE_ATTEMPTS} 轮多选题尝试 ---")
        last_combo = set()
        start_combination_size = 2 if len(option_names) > 1 else 1
        for i in range(start_combination_size, len(option_names) + 1):
            for combo in combinations(option_names, i):
                current_combo = set(combo)
                logger.info(f"尝试多选组合: {list(current_combo)}")
                options_to_unselect = last_combo - current_combo
                options_to_select = current_combo - last_combo
                for opt in options_to_unselect: click_at_region_pos(options[opt]); time.sleep(POST_TOUCH_DELAY)
                for opt in options_to_select: click_at_region_pos(options[opt]); time.sleep(POST_TOUCH_DELAY)
                click_at_region_pos(submit_pos)
                if wait_for_next_question(current_q_num):
                    # 题目刷新成功，意味着当前组合是正确的
                    correct_combo = sorted(list(current_combo))
                    logger.info(f"多选题 [{current_q_num}] 的正确答案是: {correct_combo}")
                    return correct_combo # 返回包含正确选项的列表
                else:
                    logger.info(f"组合 {list(current_combo)} 错误，继续...")
                    last_combo = current_combo
        logger.warning(f"第 {attempt} 轮所有组合尝试完成，题目仍未改变。")
        if last_combo: # 重置选项
            for opt in last_combo: click_at_region_pos(options[opt]); time.sleep(POST_TOUCH_DELAY)
    logger.error(f"多选题 {current_q_num} 在 {MAX_MULTI_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return None # 所有尝试失败，返回 None
# ============================ 【修改结束】 ============================

def wait_for_next_question(current_q_num):
    # ... (此函数无需修改) ...
    logger.info(f"采用[固定延时]策略，等待 {FIXED_POST_SUBMIT_DELAY} 秒...")
    time.sleep(FIXED_POST_SUBMIT_DELAY)
    new_q_num, _ = get_screen_info()
    return new_q_num and new_q_num != current_q_num

# ============================ 【核心新增部分：写入答案映射文件】 ============================
def write_solution_map_to_file():
    """
    将已解答的题目和答案写入到本次运行的截图中文件夹下的 aolution_map.txt 文件。
    使用 JSON 格式，方便机器读取和解析。
    """
    if not solved_questions:
        logger.info("没有成功解答任何题目，无需生成答案映射文件。")
        return
    
    map_file_path = os.path.join(SCREENSHOT_RUN_DIR, "solution_map.json")
    logger.info(f"正在将 {len(solved_questions)} 条解题记录写入答案映射文件: {map_file_path}")
    
    try:
        with open(map_file_path, 'w', encoding='utf-8') as f:
            # 使用json.dump来写入，格式更规范，ensure_ascii=False保证中文正常显示
            json.dump(solved_questions, f, ensure_ascii=False, indent=4)
        logger.info("答案映射文件写入成功。")
    except Exception as e:
        logger.error(f"写入答案映射文件失败: {e}")
# ============================ 【修改结束】 ============================

def main_loop():
    last_question_num = "初始化"
    logger.info("脚本将在3秒后开始...")
    time.sleep(3)
    while True:
        logger.info("\n" + "="*20 + " 新一轮检测循环 " + "="*20)
        q_num, q_type = get_screen_info()
        if not q_num:
            logger.error("无法识别当前题号，脚本可能卡住或已结束。等待5秒后重试..."); time.sleep(5)
            continue
        
        if q_num != last_question_num:
            logger.info(f"检测到新题目: {q_num} (上一题: {last_question_num})")
            submit_pos, _ = find_submit_button_with_scroll(q_num, SCREENSHOT_RUN_DIR)
            if not submit_pos:
                logger.error(f"在题目 {q_num} 找不到[提交按钮]，脚本无法继续。"); break
            
            options = find_available_options()
            if not options:
                logger.error(f"在题目 {q_num} 找不到任何选项，脚本无法继续。"); break
            
            correct_answer = None
            if q_type == "单选题":
                correct_answer = solve_single_choice(q_num, options, submit_pos)
            else: # 多选题
                correct_answer = solve_multiple_choice(q_num, options, submit_pos)
            
            # 【核心修改】处理解答函数返回的结果
            if correct_answer:
                # 如果成功解答，记录答案
                solved_questions[q_num] = correct_answer
                last_question_num = q_num
            else:
                # 如果解答失败，终止脚本
                logger.critical(f"题目 {q_num} 未能成功解答，脚本终止！"); break
        else:
            logger.info(f"题号未变({q_num})，等待2秒..."); time.sleep(2)

if __name__ == "__main__":
    try:
        main_loop()
    except pyautogui.FailSafeException:
        logger.critical("Fail-Safe触发！鼠标移动到屏幕左上角，脚本已紧急停止。")
    except Exception as e:
        logger.exception("脚本运行过程中发生未处理的异常！")
    finally:
        # 【核心修改】确保无论脚本如何退出，都会尝试写入答案文件
        write_solution_map_to_file()
        logger.info("脚本执行结束。")