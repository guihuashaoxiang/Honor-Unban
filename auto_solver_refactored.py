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

# ============================ 新增依赖库导入 ============================
try:
    import win32clipboard
    from bs4 import BeautifulSoup
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False
    print("警告：未找到 'pywin32' 或 'beautifulsoup4' 库。HTML验证功能将不可用。")
    print("请运行 'pip install pywin32 beautifulsoup4' 来安装。")
# =========================================================================


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
qa_bank = {}

# ==================== 日志配置 START ====================
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
FIXED_POST_SUBMIT_DELAY = 0.5
POST_TOUCH_DELAY = 0.5  # 适当降低延时，因为有验证机制
POST_SCROLL_DELAY = 1.5
MAX_SINGLE_CHOICE_ATTEMPTS = 2
MAX_MULTI_CHOICE_ATTEMPTS = 3
MAX_SCROLL_ATTEMPTS = 3
STOP_AT_QUESTION_NUM = "第78题"

# ============================ 题库配置 ============================
USE_QA_BANK = False
QA_BANK_FILE = "master_qa_bank.json"

# ===========================================================================


# ------------------- 资源与模板定义 -------------------
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
logger.info(f"启用HTML验证: {'是' if IS_WINDOWS else '否 (环境不支持)'}")


# --- 桌面操作核心函数 ---
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


# ============================ 【核心升级】剪贴板解析函数 ============================
def _get_html_from_clipboard():
    """尝试从剪贴板读取'HTML Format'内容。"""
    if not IS_WINDOWS: return None
    try:
        win32clipboard.OpenClipboard()
        html_format = win32clipboard.RegisterClipboardFormat("HTML Format")
        if win32clipboard.IsClipboardFormatAvailable(html_format):
            data = win32clipboard.GetClipboardData(html_format)
            # 找到HTML内容的起始位置
            match = re.search(b"StartFragment:(\\d+)", data)
            if match:
                start_index = int(match.group(1))
                # 解码为utf-8字符串，忽略错误
                return data[start_index:].decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"读取剪贴板HTML格式时出错: {e}")
    finally:
        if IS_WINDOWS:
            win32clipboard.CloseClipboard()
    return None

def _parse_html_data(html_content):
    """
    【升级版】使用BeautifulSoup解析HTML，提取问题、选项和选中状态。
    此版本兼容文字题、视频题和图片题的HTML结构。
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取题号和类型 (这部分结构通用，无需修改)
        title_count_div = soup.find('div', class_='ts_title_count')
        if not title_count_div: return None
        q_num_tag = title_count_div.find('i')
        q_type_tag = title_count_div.find('em')
        q_num = q_num_tag.get_text(strip=True) if q_num_tag else ""
        q_type = f"{q_type_tag.get_text(strip=True)}题" if q_type_tag else ""

        # 提取问题文本 (这部分结构通用，无需修改)
        q_text_div = soup.find('div', class_='ts_title_text')
        if not q_text_div: return None
        q_text = q_text_div.get_text(strip=True)

        # 提取选项和选中状态
        options_wrapper = soup.find('div', class_='options-wrapper')
        if not options_wrapper: return None
        
        options = {}
        selected_options = []
        
        # ======================= 【核心修改点 1】 =======================
        # 不再硬编码class名，而是查找所有带class属性的li标签，使其更通用
        option_lis = options_wrapper.find_all('li', class_=True)

        for li in option_lis:
            # 提取选项字母和文本
            text = li.get_text(strip=True)
            match = re.match(r'([A-D])\.(.*)', text)
            if match:
                option_letter = match.group(1)
                
                # ======================= 【核心修改点 2】 =======================
                # 为图片选项提供一个占位符，而不是空字符串
                option_text = match.group(2).strip()
                if not option_text and li.find('img'):
                    option_text = "[图片选项]"
                options[option_letter] = option_text
                
                # ======================= 【核心修改点 3】 =======================
                # 通用化“选中状态”的判断
                classes = li.get('class', [])
                if any('active' in c for c in classes):
                    selected_options.append(option_letter)
        
        if q_num and q_text and options:
            return {
                "q_num": q_num,
                "q_type": q_type,
                "q_text": q_text,
                "options": options,
                "selected_options": sorted(selected_options)
            }
    except Exception as e:
        logger.error(f"解析HTML时发生错误: {e}")
    return None

def _parse_text_data(clipboard_text):
    """原有的纯文本解析逻辑，作为备用方案。"""
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
    
    if 'q_text' in q_info and 'q_num' in q_info and q_info['options']:
        q_info['selected_options'] = []  # 纯文本模式无法获知选中状态
        return q_info
    return None

def get_clipboard_data_robust():
    """
    健壮的剪贴板数据获取函数。
    优先使用HTML格式获取题目内容和选中状态。
    如果失败，则回退到纯文本格式。
    """
    logger.info("正在通过剪贴板获取题目信息...")
    pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c'); time.sleep(0.2)
    
    # 优先尝试HTML解析
    html_content = _get_html_from_clipboard()
    if html_content:
        parsed_data = _parse_html_data(html_content)
        if parsed_data:
            logger.info(f"✅ [HTML解析成功] 题目: {parsed_data['q_num']}, 已选: {parsed_data['selected_options'] or '无'}")
            return parsed_data

    # HTML失败，回退到纯文本解析
    logger.warning("HTML解析失败或不可用，回退到纯文本解析...")
    try:
        clipboard_text = pyperclip.paste()
        if not clipboard_text:
            logger.warning("剪贴板为空。")
            return None
        
        parsed_data = _parse_text_data(clipboard_text)
        if parsed_data:
            logger.info(f"✅ [纯文本解析成功] 题目: {parsed_data['q_num']}")
            return parsed_data
        else:
            logger.error(f"纯文本解析不完整。")
            return None
    except Exception as e:
        logger.error(f"从剪贴板获取或解析纯文本时出错: {e}")
        return None

# --- 逻辑函数 ---
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
            screenshot_path_2 = os.path.join(screenshot_dir, f"{safe_q_num}_2_scrolled.png")
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

def wait_for_next_question(current_q_text):
    logger.info(f"等待 {FIXED_POST_SUBMIT_DELAY} 秒后检查题目是否刷新...")
    time.sleep(FIXED_POST_SUBMIT_DELAY)
    new_q_info = get_clipboard_data_robust()
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

# ============================ 【核心升级】带验证的解答函数 ============================

def verify_and_click(options_to_select, options_pos, max_retries=2):
    """
    点击、验证、再点击的核心函数。
    :param options_to_select: 期望被选中的选项列表，例如 ['A', 'C']
    :param options_pos: 各选项的屏幕坐标
    :param max_retries: 最大重试次数
    :return: True如果验证成功，False如果失败
    """
    if not IS_WINDOWS: # 如果不支持HTML验证，直接点击并返回成功
        for opt in options_to_select:
            click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
        return True

    expected_selection = set(options_to_select)
    
    for attempt in range(max_retries):
        logger.info(f"  -> 第 {attempt+1}/{max_retries} 次尝试点击并验证: {options_to_select}")
        # 点击所有期望的选项 (这种方式对于多选更安全，每次都重置状态)
        # 1. 先获取当前状态
        current_data = get_clipboard_data_robust()
        current_selection = set(current_data.get('selected_options', []))
        
        # 2. 计算需要点击和取消点击的选项
        to_select = expected_selection - current_selection
        to_deselect = current_selection - expected_selection
        
        for opt in to_deselect:
            click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
        for opt in to_select:
            click_at_region_pos(options_pos[opt]); time.sleep(POST_TOUCH_DELAY)
        
        # 3. 验证结果
        time.sleep(0.3) # 等待UI反应
        verified_data = get_clipboard_data_robust()
        if verified_data and set(verified_data.get('selected_options', [])) == expected_selection:
            logger.info(f"  -> ✅ 验证成功，选项 {options_to_select} 已被选中。")
            return True
        else:
            logger.warning(f"  -> ❌ 验证失败。期望选中: {sorted(list(expected_selection))}, 实际选中: {verified_data.get('selected_options', '未知')}")
    
    logger.error(f"  -> ❌ 经过 {max_retries} 次尝试后，仍无法正确选中选项 {options_to_select}。")
    return False

def solve_with_qa_bank(q_info, options_pos, submit_pos):
    """
    【升级版】使用已加载的新格式题库尝试解答。
    它会先匹配问题文本，再匹配选项集。
    """
    q_text = q_info['q_text']
    
    # 1. 检查题库中是否存在该问题文本
    if q_text not in qa_bank:
        logger.info(f"题库中未找到题目: '{q_text[:30]}...'")
        return 'FALLBACK'

    # 2. 获取当前屏幕上的选项集合，用于匹配
    # 使用 set 是为了无序比较
    current_options_set = set(q_info['options'].values())
    
    # 3. 遍历该问题的所有已知变种 (variants)
    for variant in qa_bank[q_text]:
        known_options_set = set(variant['options'])
        
        # 4. 如果选项集合完全匹配
        if current_options_set == known_options_set:
            correct_answer_texts = variant['answer']
            logger.info(f"✅ 在题库中找到题目和完全匹配的选项集，预设答案: {correct_answer_texts}")

            # --- 后续逻辑与之前类似，但使用匹配到的答案 ---
            options_text_to_letter = {v: k for k, v in q_info['options'].items()}
            letters_to_click = []
            for answer_text in correct_answer_texts:
                if answer_text in options_text_to_letter:
                    letters_to_click.append(options_text_to_letter[answer_text])
                else:
                    # 这种情况理论上不应发生，因为我们已经确认了选项集匹配
                    logger.error(f"严重错误：选项集匹配但答案文本 '{answer_text}' 找不到。")
                    return 'FALLBACK' # 出现意外，回退
            
            if not letters_to_click:
                logger.error("根据题库答案未能匹配到任何可点击的选项。")
                return 'FALLBACK'

            logger.info(f"--- [题库模式] 尝试解答，点击选项: {letters_to_click} ---")
            if verify_and_click(letters_to_click, options_pos):
                click_at_region_pos(submit_pos)
                if wait_for_next_question(q_text):
                    logger.info(f"🎉 [题库模式] 解答成功！")
                    return correct_answer_texts # 返回正确答案
                else:
                    logger.warning(f"[题库模式] 提交后题目未刷新，题库答案可能已失效。")
            
            # 如果题库答案错误，则回退到遍历模式
            logger.error(f"[题库模式] 解答失败。将回退到遍历模式。")
            return 'FALLBACK'
    
    # 遍历完所有变种，没有找到匹配的选项集
    logger.info(f"题库中虽有同名问题，但选项集不匹配。这是一个新变种。")
    return 'FALLBACK'

def solve_single_choice(q_info, options_pos, submit_pos):
    logger.info(f"--- [遍历模式] 开始解答单选题: {q_info['q_text']} ---")
    for option_name in sorted(options_pos.keys()):
        logger.info(f"尝试单选项 [{option_name}]...")
        if verify_and_click([option_name], options_pos):
            click_at_region_pos(submit_pos)
            if wait_for_next_question(q_info['q_text']):
                correct_answer_text = q_info['options'][option_name]
                logger.info(f"🎉 [遍历模式] 单选题 [{q_info['q_num']}] 的正确答案是: [{correct_answer_text}]")
                return [correct_answer_text]
            else:
                logger.info(f"选项 [{option_name}] 错误，继续...")
    logger.error(f"单选题 {q_info['q_text']} 在所有尝试后仍未解决。")
    return None

def solve_multiple_choice(q_info, options_pos, submit_pos):
    logger.info(f"--- [遍历模式] 开始解答多选题: {q_info['q_text']} ---")
    option_letters = sorted(options_pos.keys())
    start_size = 2 if len(option_letters) > 1 else 1
    
    for i in range(start_size, len(option_letters) + 1):
        for combo in combinations(option_letters, i):
            current_combo = list(combo)
            logger.info(f"尝试多选组合: {current_combo}")
            
            if verify_and_click(current_combo, options_pos):
                click_at_region_pos(submit_pos)
                if wait_for_next_question(q_info['q_text']):
                    correct_answer_texts = [q_info['options'][letter] for letter in current_combo]
                    logger.info(f"🎉 [遍历模式] 多选题 [{q_info['q_num']}] 的正确答案是: {correct_answer_texts}")
                    return correct_answer_texts
                else:
                    logger.info(f"组合 {current_combo} 错误，继续...")
    
    logger.error(f"多选题 {q_info['q_text']} 在所有组合尝试后仍未解决。")
    return None

# ============================ 主循环 ============================
def main_loop():
    last_question_text = "初始化"
    
    while True:
        logger.info("\n" + "="*20 + " 新一轮检测循环 " + "="*20)
        q_info = get_clipboard_data_robust()
        
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
            use_fallback = False
            if USE_QA_BANK:
                bank_result = solve_with_qa_bank(q_info, options_pos, submit_pos)
                if bank_result == 'FALLBACK':
                    use_fallback = True
                else:
                    correct_answer = bank_result
            
            if not USE_QA_BANK or use_fallback:
                if q_info['q_type'] == "单选题":
                    correct_answer = solve_single_choice(q_info, options_pos, submit_pos)
                else:
                    correct_answer = solve_multiple_choice(q_info, options_pos, submit_pos)

            if correct_answer:
                # ------ 【核心修改】 ------
                # 使用新的、更健壮的数据结构来记录答案
                q_text = q_info['q_text']
                # 获取当前这道题的所有选项文本，并排序以创建唯一标识
                current_options_sorted = sorted(list(q_info['options'].values()))
                
                # 准备要存储的新条目
                new_entry = {
                    "options": current_options_sorted,
                    "answer": correct_answer
                }

                # 检查此问题是否已在solved_questions中
                if q_text not in solved_questions:
                    solved_questions[q_text] = []

                # 检查这个选项组合是否已经存在，存在则更新，不存在则添加
                found = False
                for i, existing_entry in enumerate(solved_questions[q_text]):
                    if existing_entry["options"] == current_options_sorted:
                        # 选项组合已存在，用新答案覆盖（通常不会发生在一轮运行中，但为保险起见）
                        solved_questions[q_text][i] = new_entry
                        found = True
                        break
                
                if not found:
                    solved_questions[q_text].append(new_entry)
                # ------ 【修改结束】 ------

                last_question_text = current_q_text
            else:
                logger.critical(f"题目 {q_info['q_num']} 未能成功解答，脚本终止！"); break
        else:
            logger.info(f"题目未变({q_info.get('q_num', '未知')})，等待2秒..."); time.sleep(2)

# ============================ 程序入口 ============================
if __name__ == "__main__":
    try:
        load_qa_bank()

        if not initialize_and_activate():
            exit()

        if not validate_all_options_visible():
            exit()
        
        main_loop()

    except pyautogui.FailSafeException:
        logger.critical("Fail-Safe触发！鼠标移动到屏幕左上角，脚本已紧急停止。")
    except Exception as e:
        logger.exception("脚本运行过程中发生未处理的异常！")
    finally:
        write_solution_map_to_file()
        logger.info("脚本执行结束。")