# -*- encoding=utf8 -*-
import os
import re
import time
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

# ==================== 日志配置 START ====================
# (日志部分保持不变)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    log_file = 'auto_solver.log'
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
# ==================== 日志配置 END ====================


# ==============================================================================
# ============================ 全局配置 (请仔细阅读) =============================
# ==============================================================================

# ------------------- 区域与核心配置 (必须修改) -------------------
SCREEN_REGION = (2481, 0, 901, 2063)
# 【新增】等待模式，SMART或FIXED，SMART模式下会自动判断是否刷新页面，FIXED模式下不会自动刷新
WAIT_MODE = 'FIXED'

# ------------------- 速度与延时控制 (可按需微调) -------------------
FIXED_POST_SUBMIT_DELAY = 1
SMART_RECHECK_INTERVAL = 0.5
SMART_MAX_WAIT_FOR_REFRESH = 8.0
POST_TOUCH_DELAY = 0.8
# 【新增】每次滚动操作后的等待时间（秒），给UI足够的时间响应
POST_SCROLL_DELAY = 1.5

# ------------------- 容错与重试机制 (可按需微调) -------------------
MAX_SINGLE_CHOICE_ATTEMPTS = 2
MAX_MULTI_CHOICE_ATTEMPTS = 3
# 【新增配置】当找不到提交按钮时，最大滚动屏幕的尝试次数
MAX_SCROLL_ATTEMPTS = 3


# ------------------- 资源与模型定义 (一般无需修改) -------------------
# ... (此部分保持不变) ...
SCREENSHOT_DIR = "screenshots"
if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
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
    logger.info("选项模板加载完成。")
    for name, t_list in option_templates.items():
        logger.info(f"  - 选项 [{name}] 加载了 {len(t_list)} 个模板。")
    if not option_templates:
        logger.warning("警告：未加载到任何符合 'option_[A-D]_[n].png' 格式的选项模板！")
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
logger.info(f"投屏区域 (Region): {SCREEN_REGION}")
logger.info(f"滚动后延时 (Scroll Delay): {POST_SCROLL_DELAY}s")
logger.info(f"最大滚动次数 (Scroll Retries): {MAX_SCROLL_ATTEMPTS}")
# ... (其余打印语句保持不变) ...


# --- 桌面操作核心函数 ---
# ... (capture_region, find_in_region, click_at_region_pos, scroll_in_region 保持不变) ...
def capture_region(filename=None):
    pil_img = pyautogui.screenshot(region=SCREEN_REGION)
    if filename:
        pil_img.save(filename)
    np_array = np.array(pil_img)
    opencv_img = cv2.cvtColor(np_array, cv2.COLOR_RGB2BGR)
    return opencv_img

def find_in_region(template):
    # 【优化】find_in_region现在只负责匹配，不再截图，由调用方传入截图
    # 这可以避免在一次查找中（如find_submit_button_with_scroll）重复截图
    # screen_img = capture_region() # 旧代码
    # match_pos = template.match_in(screen_img) # 旧代码
    # return match_pos
    pass # 函数体现在合并到调用方了，这里先留空，或者直接删除此函数，但为减少改动保留

def click_at_region_pos(region_pos):
    if not region_pos: return
    absolute_x = SCREEN_REGION[0] + region_pos[0]
    absolute_y = SCREEN_REGION[1] + region_pos[1]
    logger.info(f"执行点击: 区域坐标={region_pos}, 屏幕绝对坐标=({absolute_x}, {absolute_y})")
    pyautogui.click(absolute_x, absolute_y)

def scroll_in_region():
    logger.info(f"执行自定义拖动滚动...")
    region_x, region_y, region_w, region_h = SCREEN_REGION
    drag_center_x = region_x + region_w // 2
    start_y = region_y + region_h * 0.70
    end_y = region_y + region_h * 0.30
    pyautogui.moveTo(drag_center_x, start_y, duration=0.2)
    pyautogui.mouseDown()
    pyautogui.moveTo(drag_center_x, end_y, duration=0.5)
    pyautogui.mouseUp()
    logger.info("自定义拖动完成。")
    
# --- 逻辑函数 ---
def get_screen_info():
    # ... (此函数无需修改) ...
    screen_path = os.path.join(SCREENSHOT_DIR, "temp_screen.png")
    capture_region(filename=screen_path)
    try:
        result = ocr.ocr(screen_path, cls=True)
        if not result or not result[0]: return None, "单选题"
        full_text = " ".join([line[1][0] for line in result[0]])
        match = re.search(r'第(\d+|[一二三四五六七八九十百]+)题', full_text)
        question_num = f"第{match.group(1)}题" if match else None
        question_type = "多选题" if "多选" in full_text else "单选题"
        return question_num, question_type
    except Exception:
        return None, "单选题"

# ============================ 【核心修改部分】 ============================
def find_submit_button_with_scroll():
    """
    【已重构】查找提交按钮，如果找不到，会循环滚动屏幕最多 MAX_SCROLL_ATTEMPTS 次。
    """
    # 步骤 1: 在当前屏幕直接查找，不滚动
    screen_img = capture_region()
    submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
    if submit_pos:
        logger.info(f"在当前页面找到[提交按钮]，区域坐标: {submit_pos}")
        return submit_pos, False  # 找到，且未滚动

    # 步骤 2: 如果没找到，开始循环滚动查找
    logger.info(f"未找到[提交按钮]，开始滚动查找 (最多 {MAX_SCROLL_ATTEMPTS} 次)...")
    for i in range(MAX_SCROLL_ATTEMPTS):
        logger.info(f"--- 第 {i + 1}/{MAX_SCROLL_ATTEMPTS} 次滚动尝试 ---")
        
        # 执行滚动并等待
        scroll_in_region()
        time.sleep(POST_SCROLL_DELAY)
        
        # 重新截图并查找
        screen_img = capture_region()
        submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
        
        if submit_pos:
            logger.info(f"在第 {i + 1} 次滚动后找到[提交按钮]，区域坐标: {submit_pos}")
            return submit_pos, True # 找到，且已滚动
    
    # 步骤 3: 如果循环结束仍未找到，则判定失败
    logger.warning(f"在 {MAX_SCROLL_ATTEMPTS} 次滚动后仍未找到[提交按钮]！")
    return None, True # 未找到，且已滚动
# ============================ 【修改结束】 ============================

def find_available_options():
    available = {}
    screen_img = capture_region()
    for name, template_list in sorted(TEMPLATE_OPTIONS.items()):
        for template in template_list:
            pos = template.match_in(screen_img)
            if pos:
                available[name] = pos
                logger.info(f"找到选项 [{name}] (使用模板: {os.path.basename(template.filename)})，区域坐标: {pos}")
                break
    if not available:
        logger.warning("未在屏幕上找到任何已定义的选项 (A, B, C, D)。")
    return available

# ... 所有后续函数 (solve_single_choice, main_loop 等) 都保持原样，无需任何修改 ...
def solve_single_choice(current_q_num, options, submit_pos):
    logger.info(f"开始解答单选题: {current_q_num}")
    for attempt in range(1, MAX_SINGLE_CHOICE_ATTEMPTS + 1):
        logger.info(f"--- 开始第 {attempt}/{MAX_SINGLE_CHOICE_ATTEMPTS} 轮单选题尝试 ---")
        for option_name in sorted(options.keys()):
            logger.info(f"尝试单选项 [{option_name}]...")
            click_at_region_pos(options[option_name]); time.sleep(POST_TOUCH_DELAY)
            click_at_region_pos(submit_pos)
            if wait_for_next_question(current_q_num):
                return True
            else:
                logger.info(f"选项 [{option_name}] 错误或未生效，继续...")
        logger.warning(f"第 {attempt} 轮尝试完成，题目仍未改变。")
    logger.error(f"单选题 {current_q_num} 在 {MAX_SINGLE_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return False

def solve_multiple_choice(current_q_num, options, submit_pos):
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

                for opt in options_to_unselect: 
                    click_at_region_pos(options[opt])
                    time.sleep(POST_TOUCH_DELAY)
                for opt in options_to_select: 
                    click_at_region_pos(options[opt])
                    time.sleep(POST_TOUCH_DELAY)

                click_at_region_pos(submit_pos)
                
                if wait_for_next_question(current_q_num):
                    return True
                else:
                    logger.info(f"组合 {list(current_combo)} 错误，继续...")
                    last_combo = current_combo

        logger.warning(f"第 {attempt} 轮所有组合尝试完成，题目仍未改变。")
        logger.info("重置所有选项为未选中状态，准备开始下一轮...")
        if last_combo:
            for opt in last_combo:
                click_at_region_pos(options[opt])
                time.sleep(POST_TOUCH_DELAY)

    logger.error(f"多选题 {current_q_num} 在 {MAX_MULTI_CHOICE_ATTEMPTS} 轮尝试后仍未解决。")
    return False

def wait_for_next_question(current_q_num):
    if WAIT_MODE == 'SMART': return _smart_wait(current_q_num)
    else: return _fixed_wait(current_q_num)

def _fixed_wait(current_q_num):
    logger.info(f"采用[固定延时]策略，等待 {FIXED_POST_SUBMIT_DELAY} 秒...")
    time.sleep(FIXED_POST_SUBMIT_DELAY)
    new_q_num, _ = get_screen_info()
    logger.info(f"延时结束，重新识别... {f'新题号: {new_q_num}' if new_q_num else '未识别到题号'}")
    return new_q_num and new_q_num != current_q_num

def _smart_wait(current_q_num):
    logger.info(f"采用[智能动态等待]策略... (超时: {SMART_MAX_WAIT_FOR_REFRESH}s)")
    start_time = time.time()
    while time.time() - start_time < SMART_MAX_WAIT_FOR_REFRESH:
        new_q_num, _ = get_screen_info()
        logger.info(f"重新识别... {f'新题号: {new_q_num}' if new_q_num else '未识别到题号'}")
        if new_q_num and new_q_num != current_q_num:
            return True
        time.sleep(SMART_RECHECK_INTERVAL)
    logger.warning("等待超时！页面未在规定时间内刷新到下一题。")
    return False

def main_loop():
    last_question_num = "初始化"
    logger.info("脚本将在3秒后开始，请确保投屏窗口在前台且无遮挡...")
    time.sleep(3)
    while True:
        logger.info("\n" + "="*20 + " 新一轮检测循环 " + "="*20)
        q_num, q_type = get_screen_info()
        if not q_num:
            logger.error("无法识别当前题号，脚本可能卡住或已结束。等待5秒后重试..."); time.sleep(5)
            continue
        
        if q_num != last_question_num:
            logger.info(f"检测到新题目: {q_num} (上一题: {last_question_num})")
            
            # main_loop中对find_submit_button_with_scroll的调用无需修改
            # 它已经能正确处理新函数返回的结果
            submit_pos, scrolled = find_submit_button_with_scroll()
            if not submit_pos:
                # 只有在多次滚动后仍然找不到按钮，才会执行到这里
                logger.error(f"在题目 {q_num} 找不到[提交按钮]，脚本无法继续。"); break

            safe_q_num = re.sub(r'[\\/*?:"<>|]', "", q_num)
            # 优化：截图逻辑调整到查找函数内部，避免重复截图
            # capture_region(filename=f"{screenshot_base}.png") # 旧代码
            logger.info(f"已对题目 {safe_q_num} 的屏幕状态进行分析。")
            
            options = find_available_options()
            if not options:
                logger.error(f"在题目 {q_num} 找不到任何选项，脚本无法继续。"); break

            success = False
            if q_type == "单选题":
                success = solve_single_choice(q_num, options, submit_pos)
            else:
                success = solve_multiple_choice(q_num, options, submit_pos)
            
            if success:
                last_question_num = q_num
            else:
                logger.critical(f"题目 {q_num} 未能成功解答，脚本终止！"); break
        else:
            logger.info(f"题号未变({q_num})，可能上次提交错误或在等待。等待2秒..."); time.sleep(2)


if __name__ == "__main__":
    try:
        main_loop()
    except pyautogui.FailSafeException:
        logger.critical("Fail-Safe触发！鼠标移动到屏幕左上角，脚本已紧急停止。")
    except Exception as e:
        logger.exception("脚本运行过程中发生未处理的异常！")
    finally:
        logger.info("脚本执行结束。")