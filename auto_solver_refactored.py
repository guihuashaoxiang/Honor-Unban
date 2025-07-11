# auto_solver_refactored.py
import os
import re
import time
import json
import logging
from itertools import combinations
from collections import defaultdict
import pyautogui
import pyperclip
from airtest.core.cv import Template
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

# 全局变量
solved_questions = {}
qa_bank = {} # 【新增】用于存放从文件加载的主题库

# ==================== 日志配置 START ====================
# (日志部分保持不变)
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
SCREEN_REGION = (2959, 0, 828, 2062)
SCROLL_MODE = 'PC_WHEEL'
FIXED_POST_SUBMIT_DELAY = 1
POST_TOUCH_DELAY = 0.8
POST_SCROLL_DELAY = 1.5
MAX_SINGLE_CHOICE_ATTEMPTS = 2
MAX_MULTI_CHOICE_ATTEMPTS = 3
MAX_SCROLL_ATTEMPTS = 3
STOP_AT_QUESTION_NUM = "第78题" # "第78题" 或 None

# ============================ 【新增】题库配置 ============================
# 是否启用题库进行快速答题
USE_QA_BANK = True
# 主题库文件路径
QA_BANK_FILE = "master_qa_bank.json"
# ===========================================================================


# ------------------- 资源与模板定义 -------------------
# (load_option_templates, TEMPLATE_SUBMIT, TEMPLATE_OPTIONS 定义保持不变)
TEMPLATES_DIR = "templates"
if not os.path.exists(TEMPLATES_DIR): 
    os.makedirs(TEMPLATES_DIR)
    logger.warning(f"模板目录 '{TEMPLATES_DIR}' 不存在，已自动创建。请将模板图片放入其中。")

def load_option_templates(directory, threshold=0.7):
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
    required_options = {'A', 'B', 'C', 'D'}
    loaded_options = set(option_templates.keys())
    if not required_options.issubset(loaded_options):
        missing = required_options - loaded_options
        logger.error(f"模板文件不完整！templates文件夹中缺少选项 {sorted(list(missing))} 的模板图片。")
        return {}
    logger.info("选项模板加载完成。")
    return dict(option_templates)

TEMPLATE_SUBMIT = Template(os.path.join(TEMPLATES_DIR, "submit_button.png"), threshold=0.6)
TEMPLATE_OPTIONS = load_option_templates(TEMPLATES_DIR, threshold=0.6)

if not TEMPLATE_OPTIONS:
    logger.critical("由于选项模板加载失败，脚本无法继续运行。")
    exit()

logger.info(f"=========== 配置加载 ===========")
logger.info(f"日志文件将保存至: {LOG_FILE_PATH}")
logger.info(f"本次运行截图将保存至: {SCREENSHOT_RUN_DIR}")
logger.info(f"投屏区域 (Region): {SCREEN_REGION}")
logger.info(f"启用题库模式: {'是' if USE_QA_BANK else '否'}")

# --- 桌面操作核心函数 ---
# (capture_region, click_at_region_pos, scroll* 函数均无需修改)
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

# (get_question_from_clipboard, find_submit_button_with_scroll, find_available_options, validate_all_options_visible, initialize_and_activate 均无需修改)
def get_question_from_clipboard():
    logger.info("正在通过剪贴板获取题目信息...")
    pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c'); time.sleep(0.2)
    try:
        clipboard_text = pyperclip.paste()
        if not clipboard_text:
            logger.warning("剪贴板为空，可能未能成功复制内容。")
            return None
        lines = [line.strip() for line in clipboard_text.split('\n') if line.strip()]
        q_info = {"options": {}}
        question_text_lines = []
        is_question_line = False
        for line in lines:
            match_q_num = re.search(r'^(第\d+题)\s*(单选|多选)', line)
            if match_q_num:
                q_info['q_num'] = match_q_num.group(1)
                q_info['q_type'] = f"{match_q_num.group(2)}题"
                is_question_line = True
                continue
            match_option = re.search(r'^([A-D])\.(.*)', line)
            if match_option:
                is_question_line = False
                q_info['options'][match_option.group(1)] = match_option.group(2).strip()
                continue
            if is_question_line:
                question_text_lines.append(line)
        if question_text_lines:
            q_info['q_text'] = " ".join(question_text_lines)
        else:
            logger.error("解析剪贴板内容失败：未能找到题目文本。")
            return None
        if 'q_text' in q_info and 'q_num' in q_info and q_info['options']:
            logger.info(f"题目解析成功: {q_info['q_num']} - {q_info['q_text'][:30]}...")
            return q_info
        else:
            logger.error(f"解析剪贴板内容不完整。解析结果: {q_info}")
            return None
    except Exception as e:
        logger.error(f"从剪贴板获取或解析信息时发生错误: {e}")
        return None
def find_submit_button_with_scroll(q_num, screenshot_dir):
    safe_q_num = re.sub(r'[\\/*?:"<>|]', "_", q_num) if q_num else "unknown_q"
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
    available = {}; screen_img = capture_region()
    for name, template_list in sorted(TEMPLATE_OPTIONS.items()):
        for template in template_list:
            pos = template.match_in(screen_img)
            if pos: available[name] = pos; break
    if not available: logger.warning("在当前屏幕上未找到任何选项 (A, B, C, D)。")
    return available
def validate_all_options_visible():
    logger.info("="*20 + " 开始初始环境校验 " + "="*20)
    logger.info("脚本将在3秒后进行屏幕选项校验...")
    time.sleep(3)
    screen_img = capture_region(filename=os.path.join(SCREENSHOT_RUN_DIR, "validation_screenshot.png"))
    expected_options = set(TEMPLATE_OPTIONS.keys())
    found_options_map = {}
    for name, template_list in sorted(TEMPLATE_OPTIONS.items()):
        for template in template_list:
            pos = template.match_in(screen_img)
            if pos: found_options_map[name] = pos; break
    found_options = set(found_options_map.keys())
    if expected_options.issubset(found_options):
        logger.info("✅ [校验通过] 所有必需的选项模板 (A, B, C, D) 均已成功匹配。")
        return True
    else:
        missing_options = expected_options - found_options
        logger.critical(f"❌ [校验失败] 未能匹配到所有必需的选项模板！缺失的选项: {sorted(list(missing_options))}")
        return False
def initialize_and_activate():
    logger.info("正在进行初始化操作：激活窗口...")
    submit_pos, _ = find_submit_button_with_scroll("initial_check", SCREENSHOT_RUN_DIR)
    if submit_pos:
        logger.info("找到[提交按钮]，点击一次以激活窗口。")
        click_at_region_pos(submit_pos)
        time.sleep(1)
        return True
    else:
        logger.error("初始化失败：未能找到[提交按钮]来激活窗口。")
        return False

# ============================ 【新增】题库加载函数 ============================
def load_qa_bank():
    """在脚本启动时加载主答题库文件。"""
    global qa_bank
    if not USE_QA_BANK:
        logger.info("配置为不使用题库，跳过加载。")
        return
    
    if os.path.exists(QA_BANK_FILE):
        try:
            with open(QA_BANK_FILE, 'r', encoding='utf-8') as f:
                qa_bank = json.load(f)
            logger.info(f"✅ 成功从 '{QA_BANK_FILE}' 加载 {len(qa_bank)} 条题目。")
        except Exception as e:
            logger.error(f"❌ 加载题库 '{QA_BANK_FILE}' 失败: {e}")
            qa_bank = {}
    else:
        logger.warning(f"⚠️ 题库文件 '{QA_BANK_FILE}' 不存在，将仅使用遍历模式答题。")
        qa_bank = {}

# ============================ 解答函数 (新增题库模式) ============================
def solve_with_qa_bank(q_info, options_pos, submit_pos):
    """
    【新增】使用已加载的题库尝试解答。
    如果成功，返回正确答案列表。
    如果失败，返回 'FALLBACK'，通知主循环使用遍历模式。
    """
    q_text = q_info['q_text']
    
    # 1. 检查题库中是否存在该题目
    if q_text not in qa_bank or not qa_bank[q_text]:
        logger.info(f"题库中未找到题目: '{q_text[:30]}...' 或答案为空。")
        return 'FALLBACK' # 返回特殊信号，表示需要回退到遍历模式

    correct_answer_texts = qa_bank[q_text]
    logger.info(f"✅ 在题库中找到题目，预设答案: {correct_answer_texts}")

    # 2. 反向映射：根据答案文本找到对应的选项字母
    options_text_to_letter = {v: k for k, v in q_info['options'].items()}
    letters_to_click = []
    for answer_text in correct_answer_texts:
        if answer_text in options_text_to_letter:
            letters_to_click.append(options_text_to_letter[answer_text])
        else:
            logger.warning(f"题库答案 '{answer_text}' 在当前选项中未找到，可能选项已变更。")
            return 'FALLBACK'
    
    if not letters_to_click:
        logger.error("根据题库答案未能匹配到任何可点击的选项。")
        return 'FALLBACK'
        
    # 3. 尝试使用题库答案点击并提交（最多两次）
    for attempt in range(1, 3): # 尝试2次
        logger.info(f"--- [题库模式] 第 {attempt}/2 次尝试，点击选项: {letters_to_click} ---")
        
        # 点击所有正确选项
        for letter in letters_to_click:
            click_at_region_pos(options_pos[letter])
            time.sleep(POST_TOUCH_DELAY)
        
        # 提交
        click_at_region_pos(submit_pos)

        # 检查题目是否刷新
        if wait_for_next_question(q_text):
            logger.info(f"🎉 [题库模式] 解答成功！正确答案: {correct_answer_texts}")
            return correct_answer_texts # 成功，返回答案列表
        else:
            logger.warning(f"[题库模式] 第 {attempt} 次尝试失败，题目未刷新。")
            # 如果是多选题，需要取消刚才的选择，以便下一次尝试或回退
            if len(letters_to_click) > 1 or attempt == 1: # 单选第一次尝试后也取消
                for letter in letters_to_click:
                    click_at_region_pos(options_pos[letter])
                    time.sleep(POST_TOUCH_DELAY)

    logger.error(f"[题库模式] 两次尝试后依然失败。将回退到遍历模式进行解答。")
    return 'FALLBACK' # 两次都失败，返回回退信号

# (solve_single_choice, solve_multiple_choice, wait_for_next_question, write_solution_map_to_file 均无需修改)
def solve_single_choice(q_info, options_pos, submit_pos):
    logger.info(f"--- [遍历模式] 开始解答单选题: {q_info['q_text']} ---")
    for attempt in range(1, MAX_SINGLE_CHOICE_ATTEMPTS + 1):
        logger.info(f"--- 开始第 {attempt}/{MAX_SINGLE_CHOICE_ATTEMPTS} 轮单选题尝试 ---")
        for option_name in sorted(options_pos.keys()):
            logger.info(f"尝试单选项 [{option_name}]...")
            click_at_region_pos(options_pos[option_name]); time.sleep(POST_TOUCH_DELAY)
            click_at_region_pos(submit_pos)
            if wait_for_next_question(q_info['q_text']):
                correct_answer_text = q_info['options'][option_name]
                logger.info(f"🎉 [遍历模式] 单选题 [{q_info['q_num']}] 的正确答案是: [{correct_answer_text}]")
                return [correct_answer_text]
            else:
                logger.info(f"选项 [{option_name}] 错误，继续...")
        logger.warning(f"第 {attempt} 轮尝试完成，题目仍未改变。")
    logger.error(f"单选题 {q_info['q_text']} 在 {MAX_SINGLE_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return None
def solve_multiple_choice(q_info, options_pos, submit_pos):
    logger.info(f"--- [遍历模式] 开始解答多选题: {q_info['q_text']} ---")
    option_letters = sorted(options_pos.keys())
    for attempt in range(1, MAX_MULTI_CHOICE_ATTEMPTS + 1):
        logger.info(f"--- 开始第 {attempt}/{MAX_MULTI_CHOICE_ATTEMPTS} 轮多选题尝试 ---")
        last_combo = set()
        start_size = 2 if len(option_letters) > 1 else 1
        for i in range(start_size, len(option_letters) + 1):
            for combo in combinations(option_letters, i):
                current_combo = set(combo)
                logger.info(f"尝试多选组合: {list(current_combo)}")
                options_to_unselect = last_combo - current_combo
                options_to_select = current_combo - last_combo
                for opt in options_to_unselect: click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
                for opt in options_to_select: click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
                click_at_region_pos(submit_pos)
                if wait_for_next_question(q_info['q_text']):
                    correct_combo_letters = sorted(list(current_combo))
                    correct_answer_texts = [q_info['options'][letter] for letter in correct_combo_letters]
                    logger.info(f"🎉 [遍历模式] 多选题 [{q_info['q_num']}] 的正确答案是: {correct_answer_texts}")
                    return correct_answer_texts
                else:
                    logger.info(f"组合 {list(current_combo)} 错误，继续...")
                    last_combo = current_combo
        logger.warning(f"第 {attempt} 轮所有组合尝试完成，题目仍未改变。")
        if last_combo:
            for opt in last_combo: click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
    logger.error(f"多选题 {q_info['q_text']} 在 {MAX_MULTI_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return None
def wait_for_next_question(current_q_text):
    logger.info(f"等待 {FIXED_POST_SUBMIT_DELAY} 秒后检查题目是否刷新...")
    time.sleep(FIXED_POST_SUBMIT_DELAY)
    new_q_info = get_question_from_clipboard()
    return new_q_info and new_q_info.get('q_text') != current_q_text
def write_solution_map_to_file():
    if not solved_questions:
        logger.info("没有成功解答任何题目，无需生成答案映射文件。")
        return
    map_file_path = os.path.join(SCREENSHOT_RUN_DIR, "solution_map.json")
    logger.info(f"正在将 {len(solved_questions)} 条解题记录写入答案映射文件: {map_file_path}")
    try:
        with open(map_file_path, 'w', encoding='utf-8') as f:
            json.dump(solved_questions, f, ensure_ascii=False, indent=4)
        logger.info("答案映射文件写入成功。")
    except Exception as e:
        logger.error(f"写入答案映射文件失败: {e}")

# ============================ 主循环 (已升级为混合模式) ============================
def main_loop():
    last_question_text = "初始化"
    
    while True:
        logger.info("\n" + "="*20 + " 新一轮检测循环 " + "="*20)
        q_info = get_question_from_clipboard()
        
        if not q_info or not q_info.get('q_text'):
            logger.error("无法获取或解析当前题目信息，脚本可能卡住或已结束。等待5秒后重试..."); time.sleep(5)
            continue
        
        current_q_text = q_info['q_text']
        
        if current_q_text != last_question_text:
            logger.info(f"检测到新题目: {q_info['q_num']} - {current_q_text}")
            
            if STOP_AT_QUESTION_NUM and q_info.get('q_num') == STOP_AT_QUESTION_NUM:
                logger.info(f"已到达预设的停止题号: {STOP_AT_QUESTION_NUM}。脚本将正常停止。")
                capture_region(filename=os.path.join(SCREENSHOT_RUN_DIR, f"{q_info['q_num']}_stop_screenshot.png"))
                break

            submit_pos, _ = find_submit_button_with_scroll(q_info['q_num'], SCREENSHOT_RUN_DIR)
            if not submit_pos:
                logger.error(f"在题目 {q_info['q_num']} 找不到[提交按钮]，脚本无法继续。"); break
            
            options_pos = find_available_options()
            if not options_pos:
                logger.error(f"在题目 {q_info['q_num']} 找不到任何选项，脚本无法继续。"); break
            
            correct_answer = None
            
            # --- 混合答题策略 ---
            use_fallback = False
            if USE_QA_BANK:
                bank_result = solve_with_qa_bank(q_info, options_pos, submit_pos)
                if bank_result == 'FALLBACK':
                    use_fallback = True
                else:
                    correct_answer = bank_result
            
            # 如果不使用题库，或者题库解答失败，则使用遍历模式
            if not USE_QA_BANK or use_fallback:
                if q_info['q_type'] == "单选题":
                    correct_answer = solve_single_choice(q_info, options_pos, submit_pos)
                else: # 多选题
                    correct_answer = solve_multiple_choice(q_info, options_pos, submit_pos)
            # --- 策略结束 ---

            if correct_answer:
                solved_questions[current_q_text] = correct_answer
                last_question_text = current_q_text
            else:
                logger.critical(f"题目 {q_info['q_num']} 未能成功解答，脚本终止！"); break
        else:
            logger.info(f"题目未变({q_info['q_num']})，等待2秒..."); time.sleep(2)

# ============================ 程序入口 ============================
if __name__ == "__main__":
    try:
        # 0. 加载主题库
        load_qa_bank()

        # 1. 初始化操作，点击提交按钮以激活窗口
        if not initialize_and_activate():
            exit()

        # 2. 校验屏幕环境，确保所有选项按钮模板都能被识别
        if not validate_all_options_visible():
            exit()
        
        # 3. 开始正式的答题循环
        main_loop()

    except pyautogui.FailSafeException:
        logger.critical("Fail-Safe触发！鼠标移动到屏幕左上角，脚本已紧急停止。")
    except Exception as e:
        logger.exception("脚本运行过程中发生未处理的异常！")
    finally:
        # 确保无论脚本如何退出，都会尝试写入已解答的题目
        write_solution_map_to_file()
        logger.info("脚本执行结束。")