# auto_solver_refactored.py

# 导入标准库
import os
import re
import time
import json
import logging
from itertools import combinations
from collections import defaultdict

# 导入第三方库
import pyautogui
import pyperclip
from airtest.core.cv import Template
import numpy as np
import cv2

# ============================ 新增依赖库导入 (可选，但强烈推荐) ============================
try:
    # 导入用于访问Windows剪贴板高级格式 (HTML) 的库
    import win32clipboard
    # 导入用于解析HTML内容的库
    from bs4 import BeautifulSoup
    # 标记为Windows环境，可以启用高级功能
    IS_WINDOWS = True
except ImportError:
    # 如果缺少库，则标记为非Windows环境，并禁用相关功能
    IS_WINDOWS = False
    print("警告：未找到 'pywin32' 或 'beautifulsoup4' 库。基于HTML的题目内容和选中状态验证功能将不可用。")
    print("请运行 'pip install pywin32 beautifulsoup4' 来安装这些库以获得最佳体验。")
# =========================================================================================


# ============================ 动态路径与全局变量配置 ============================
# 使用当前时间戳为本次运行创建唯一的标识符
RUN_TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')

# 日志文件存放目录
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
LOG_FILE_PATH = os.path.join(LOG_DIR, f"{RUN_TIMESTAMP}.log")

# 截图文件存放基础目录
SCREENSHOT_BASE_DIR = "screenshots"
# 为本次运行创建一个单独的截图文件夹，方便管理和回溯
SCREENSHOT_RUN_DIR = os.path.join(SCREENSHOT_BASE_DIR, RUN_TIMESTAMP)
if not os.path.exists(SCREENSHOT_RUN_DIR): os.makedirs(SCREENSHOT_RUN_DIR)

# 全局变量，用于在程序运行期间存储数据
solved_questions = {}  # 存储本次运行成功解答的题目及其答案
qa_bank = {}           # 存储从文件中加载的题库数据

# ==================== 日志配置 START ====================
# 获取一个日志记录器实例
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # 设置日志记录的最低级别为INFO

# 防止重复添加处理器
if not logger.handlers:
    # 创建一个文件处理器，用于将日志写入文件
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='w', encoding='utf-8')
    # 创建一个控制台处理器，用于将日志输出到屏幕
    console_handler = logging.StreamHandler()
    
    # 定义日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 将处理器添加到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
# ==================== 日志配置 END ====================


# ==============================================================================
# ============================ 全局配置 (请根据您的环境修改) =============================
# ==============================================================================

# --- 主要运行配置 ---
# 目标窗口/区域在屏幕上的位置和大小。格式: (左上角x坐标, 左上角y坐标, 宽度, 高度)
# 可以使用 pyautogui.displayMousePosition() 在终端中实时查看鼠标坐标来确定此区域。
SCREEN_REGION = (2959, 0, 828, 2062) 

# ============================ 题库配置 ============================
# 是否启用题库模式。如果为 True，脚本会优先使用题库中的答案。
USE_QA_BANK = True
# 主题库文件名。脚本将从此文件加载和更新题库。
QA_BANK_FILE = "master_qa_bank.json"

# ============================ 图像识别相似度配置 ============================
# 选项图片(如 A.png, B.png)的识别阈值。范围 0.0 ~ 1.0，值越高代表要求匹配越精确。
# 如果选项标识经常识别失败，可以适当降低此值。根据自己屏幕清晰度来调整。
SIMILARITY_THRESHOLD_OPTION = 0.6
# “提交”按钮图片的识别阈值。范围 0.0 ~ 1.0，值越高代表要求匹配越精确。根据自己屏幕清晰度来调整。
SIMILARITY_THRESHOLD_SUBMIT = 0.6

# 滚动页面的方式。
# 'PC_WHEEL': 模拟桌面电脑的鼠标滚轮滚动，速度快，推荐在PC端模拟器或网页上使用。
# 'MOBILE_DRAG': 模拟手机屏幕的拖动操作（从下往上拖动以向下滚动），适用于无法使用滚轮的场景。
# 'BOTH': 两种方式都执行一次，兼容性更强。
SCROLL_MODE = 'PC_WHEEL'

# --- 延时与重试配置 ---
# ============================ 【新增】解题重试配置 ============================
# 当一道题目解答失败时 (例如，所有选项都试过但题目未刷新)，允许的最大重试次数。
# 这可以应对临时的UI卡顿或网络问题。
MAX_SOLVE_ATTEMPTS = 3
# 每次解题重试之间的等待时间（秒）。
RETRY_DELAY_BETWEEN_ATTEMPTS = 1.5
# =========================================================================

# ============================ 【新增】精细延时控制 (高级) ============================
# 以下配置项控制脚本在特定操作后的等待时间，单位为秒。
# 如果您的计算机或模拟器反应较慢，导致操作失败（如复制不完整、点击后状态未更新），
# 可以适当增加这些值。通常情况下，保持默认值即可。
# =================================================================================
# 脚本启动后，在进行初始环境校验前的等待时间。给用户留出切换窗口的时间。
# 默认值: 3.0
INITIAL_VALIDATION_DELAY = 3.0

# --- 已有延时配置 ---
# 提交答案后，等待题目刷新的固定延时（秒）。
FIXED_POST_SUBMIT_DELAY = 1
# 每次点击选项后的等待时间（秒）。如果点击后UI反应慢，可适当增加此值。
POST_TOUCH_DELAY = 0.6

# 初始化时，点击“提交”按钮激活窗口后的等待时间，以确保窗口状态稳定。
# 默认值: 1.0
POST_ACTIVATION_CLICK_DELAY = 1.0

# 在主循环中，如果检测到题目内容没有变化，脚本将等待此时间后再次检查。
# 默认值: 2
POLLING_INTERVAL_NO_CHANGE = 2

# 在主循环中，如果无法获取到题目信息（可能应用卡死或已结束），脚本等待此时间后重试。
# 默认值: 5.0
RETRY_DELAY_ON_ERROR = 3

# 模拟“全选”(Ctrl+A)后，等待系统响应的时间。
# 默认值: 0.1
DELAY_AFTER_SELECT_ALL = 0.1

# 模拟“复制”(Ctrl+C)后，等待内容进入剪贴板的时间。
# 默认值: 0.2
DELAY_AFTER_COPY = 0.2

# 在多选题验证点击中，完成一系列点击操作后，等待UI稳定再进行HTML验证的延时。
# 默认值: 0.5
DELAY_BEFORE_VERIFY_CLICK = 0.5

# 当滚动模式为 'BOTH' 时，在两种滚动方式（拖动和滚轮）之间的延时，防止操作冲突。
# 默认值: 0.3
DELAY_BETWEEN_SCROLL_METHODS = 0.5

# 每次滚动操作后的等待时间（秒），确保页面内容已加载完毕。
POST_SCROLL_DELAY = 1.5
# # 【已弃用】单选题遍历模式下的最大尝试次数。现在由逻辑自动决定。
# MAX_SINGLE_CHOICE_ATTEMPTS = 2
# # 【已弃用】多选题遍历模式下的最大尝试次数。现在由逻辑自动决定。
# MAX_MULTI_CHOICE_ATTEMPTS = 3
# 当屏幕上找不到“提交”按钮时，尝试向下滚动的最大次数。
MAX_SCROLL_ATTEMPTS = 3
# 当遇到指定题号时，脚本将自动停止。设置为空字符串 "" 可禁用此功能。例如: "第78题",未修复。
STOP_AT_QUESTION_NUM = None

# ===========================================================================


# ------------------- 资源与模板定义 -------------------
# 存放模板图片的目录 (如 option_A_1.png, option_A_2.png, option_B_1.png 等)
TEMPLATES_DIR = "templates"
if not os.path.exists(TEMPLATES_DIR): 
    os.makedirs(TEMPLATES_DIR)
    logger.warning(f"模板目录 '{TEMPLATES_DIR}' 不存在，已自动创建。请将模板图片放入其中。")

def load_option_templates(directory, threshold=0.7):
    """
    从指定目录加载选项模板图片 (例如, option_A_1.png)。
    支持同一选项有多个模板 (例如 option_A_1.png, option_A_2.png)，以提高识别率。
    
    Args:
        directory (str): 存放模板图片的目录路径。
        threshold (float): 图像匹配的相似度阈值。

    Returns:
        dict: 一个字典，键是选项名 ( 'A', 'B', ...)，值是对应的Template对象列表。
              如果关键模板缺失，则返回空字典。
    """
    logger.info(f"开始从 '{directory}' 目录加载选项模板...")
    option_templates = defaultdict(list)
    try:
        filenames = os.listdir(directory)
    except FileNotFoundError:
        logger.error(f"模板目录 '{directory}' 未找到！脚本无法继续。")
        return {}
    
    # 使用正则表达式匹配文件名，格式为 "option_字母_序号.png"
    pattern = re.compile(r"option_([A-D])_(\d+)\.png")
    for filename in sorted(filenames):
        match = pattern.match(filename)
        if match:
            option_name = match.group(1)
            full_path = os.path.join(directory, filename)
            # 使用配置的阈值创建Template对象
            template = Template(full_path, threshold=threshold)
            option_templates[option_name].append(template)
            logger.info(f"  -> 已加载模板: {filename} for Option {option_name}")
            
    # 校验是否所有必需的选项 (A, B, C, D) 都有模板
    required_options = {'A', 'B', 'C', 'D'}
    loaded_options = set(option_templates.keys())
    if not required_options.issubset(loaded_options):
        missing = required_options - loaded_options
        logger.error(f"模板文件不完整！templates文件夹中缺少选项 {sorted(list(missing))} 的模板图片。")
        return {}
        
    logger.info("选项模板加载完成。")
    return dict(option_templates)

# 使用全局配置的相似度阈值来加载模板
TEMPLATE_SUBMIT = Template(os.path.join(TEMPLATES_DIR, "submit_button.png"), threshold=SIMILARITY_THRESHOLD_SUBMIT)
TEMPLATE_OPTIONS = load_option_templates(TEMPLATES_DIR, threshold=SIMILARITY_THRESHOLD_OPTION)

# 如果选项模板加载失败，则无法进行答题，直接退出
if not TEMPLATE_OPTIONS:
    logger.critical("由于选项模板加载失败，脚本无法继续运行。")
    exit()

# 打印关键配置信息，方便用户检查
logger.info(f"=========== 配置加载 ===========")
logger.info(f"日志文件将保存至: {LOG_FILE_PATH}")
logger.info(f"本次运行截图将保存至: {SCREENSHOT_RUN_DIR}")
logger.info(f"投屏区域 (Region): {SCREEN_REGION}")
logger.info(f"启用题库模式: {'是' if USE_QA_BANK else '否'}")
logger.info(f"启用HTML验证: {'是' if IS_WINDOWS else '否 (环境不支持)'}")
logger.info(f"选项识别阈值: {SIMILARITY_THRESHOLD_OPTION}")
logger.info(f"提交按钮识别阈值: {SIMILARITY_THRESHOLD_SUBMIT}")


# --- 桌面操作核心函数 ---

def capture_region(filename=None):
    """
    截取在 SCREEN_REGION 中定义的屏幕区域。

    Args:
        filename (str, optional): 如果提供，截图将被保存到指定路径。 Defaults to None.

    Returns:
        numpy.ndarray: 返回OpenCV格式的图像数组 (BGR)。
    """
    pil_img = pyautogui.screenshot(region=SCREEN_REGION)
    if filename:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        pil_img.save(filename)
        logger.info(f"截图已保存至: {filename}")
    # 将Pillow图像转换为numpy数组，并从RGB转为OpenCV兼容的BGR格式
    np_array = np.array(pil_img)
    opencv_img = cv2.cvtColor(np_array, cv2.COLOR_RGB2BGR)
    return opencv_img

def click_at_region_pos(region_pos):
    """
    在 SCREEN_REGION 内的相对坐标上执行点击。

    Args:
        region_pos (tuple): (x, y) 相对坐标。
    """
    if not region_pos: return
    # 计算绝对屏幕坐标
    absolute_x = SCREEN_REGION[0] + region_pos[0]
    absolute_y = SCREEN_REGION[1] + region_pos[1]
    pyautogui.click(absolute_x, absolute_y)

def _scroll_with_drag():
    """私有函数：通过模拟鼠标拖动来实现滚动。"""
    logger.info("执行[拖动滚动]...")
    region_x, region_y, region_w, region_h = SCREEN_REGION
    # 计算拖动的起点和终点
    drag_center_x = region_x + region_w // 2
    start_y = region_y + region_h * 0.70
    end_y = region_y + region_h * 0.30
    pyautogui.moveTo(drag_center_x, start_y, duration=0.2)
    pyautogui.mouseDown()
    pyautogui.moveTo(drag_center_x, end_y, duration=0.5)
    pyautogui.mouseUp()

def _scroll_with_wheel():
    """私有函数：通过模拟鼠标滚轮来实现滚动。"""
    logger.info("执行[PC滚轮滚动]...")
    region_x, region_y, region_w, region_h = SCREEN_REGION
    # 将鼠标移动到区域中心以确保滚动作用于目标窗口
    center_x = region_x + region_w // 2
    center_y = region_y + region_h // 2
    pyautogui.moveTo(center_x, center_y, duration=0.2)
    # 负值表示向下滚动
    pyautogui.scroll(-500)

def scroll_in_region():
    """根据全局配置 SCROLL_MODE 来执行滚动操作。"""
    if SCROLL_MODE == 'MOBILE_DRAG':
        _scroll_with_drag()
    elif SCROLL_MODE == 'PC_WHEEL':
        _scroll_with_wheel()
    elif SCROLL_MODE == 'BOTH':
        _scroll_with_drag()
        time.sleep(DELAY_BETWEEN_SCROLL_METHODS)
        _scroll_with_wheel()
    else: # 默认为拖动模式
        _scroll_with_drag()


# ============================ 【核心升级】剪贴板解析函数 ============================

def _get_html_from_clipboard():
    """
    【仅Windows】尝试从剪贴板中读取 'HTML Format' 内容。
    当在网页或某些应用中复制内容时，除了纯文本，还会附带HTML格式的数据。
    
    Returns:
        str or None: 如果成功，返回HTML内容的字符串；否则返回None。
    """
    if not IS_WINDOWS: return None
    try:
        win32clipboard.OpenClipboard()
        # 注册并获取 "HTML Format" 的格式ID
        html_format = win32clipboard.RegisterClipboardFormat("HTML Format")
        if win32clipboard.IsClipboardFormatAvailable(html_format):
            data = win32clipboard.GetClipboardData(html_format)
            # HTML格式数据有一个头部，描述了HTML内容的起始和结束位置
            # 我们需要解析这个头部来找到真正的HTML片段
            match = re.search(b"StartFragment:(\\d+)", data)
            if match:
                start_index = int(match.group(1))
                # 从起始位置解码为utf-8字符串，忽略可能出现的解码错误
                return data[start_index:].decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"读取剪贴板HTML格式时出错: {e}")
    finally:
        if IS_WINDOWS:
            win32clipboard.CloseClipboard()
    return None

def _parse_html_data(html_content):
    """
    使用 BeautifulSoup 解析HTML字符串，智能提取问题、选项（文本或图片URL）和选中状态。
    这是脚本获取题目信息最可靠的方式。

    Args:
        html_content (str): 包含题目信息的HTML代码片段。

    Returns:
        dict or None: 解析成功则返回包含题目信息的字典，否则返回None。
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 1. 提取题号和题目类型
        title_count_div = soup.find('div', class_='ts_title_count')
        if not title_count_div: return None
        q_num_tag = title_count_div.find('i')
        q_type_tag = title_count_div.find('em')
        q_num = q_num_tag.get_text(strip=True) if q_num_tag else ""
        q_type = f"{q_type_tag.get_text(strip=True)}题" if q_type_tag else ""

        # 2. 提取问题文本
        q_text_div = soup.find('div', class_='ts_title_text')
        if not q_text_div: return None
        q_text = q_text_div.get_text(strip=True)

        # 3. 提取选项和选中状态
        options_wrapper = soup.find('div', class_='options-wrapper')
        if not options_wrapper: return None
        
        options = {}
        selected_options = []
        # 找到所有选项的列表项 (li 标签)
        option_lis = options_wrapper.find_all('li', class_=True)

        for li in option_lis:
            # 提取选项字母 (A, B, C, D)
            option_letter_span = li.find('span')
            text_content = option_letter_span.get_text(strip=True) if option_letter_span else li.get_text(strip=True)
            match = re.match(r'([A-D])\.', text_content)
            if not match and option_letter_span: # 有时字母不在span里, 需要从li的完整文本匹配
                 match = re.match(r'([A-D])\.', li.get_text(strip=True))

            if match:
                option_letter = match.group(1)
                
                # ======================= 【核心升级点】 =======================
                # 智能判断选项是图片还是文字
                img_tag = li.find('img')
                if img_tag and img_tag.has_attr('src'):
                    # 如果li标签内有<img>，则这是一个图片选项，我们使用图片的URL作为其内容。
                    option_content = img_tag['src']
                else:
                    # 否则，这是一个文字选项，我们提取其文本内容。
                    full_text = li.get_text(strip=True)
                    # 移除开头的 "A."、"B." 等，得到纯净的选项文本。
                    option_content = re.sub(r'^[A-D]\.', '', full_text, 1).strip()
                
                options[option_letter] = option_content
                
                # 通过检查li标签的class属性是否包含 'active' 来判断此选项是否被选中。
                classes = li.get('class', [])
                if any('active' in c for c in classes):
                    selected_options.append(option_letter)
        
        # 如果成功提取到所有关键信息，则构建并返回结果字典
        if q_num and q_text and options:
            return {
                "q_num": q_num,
                "q_type": q_type,
                "q_text": q_text,
                "options": options, # 选项内容可能是文本或图片URL
                "selected_options": sorted(selected_options) # 返回已排序的选中选项列表
            }
    except Exception as e:
        logger.error(f"解析HTML时发生严重错误: {e}", exc_info=True)
    return None

def _parse_text_data(clipboard_text):
    """
    【备用方案】解析纯文本格式的剪贴板内容。
    功能有限，无法识别图片选项和已选中状态。
    在当前版本中，此函数主要作为历史参考，因为HTML解析更优越。

    Args:
        clipboard_text (str): 从剪贴板获取的纯文本。

    Returns:
        dict or None: 解析成功则返回字典，否则None。
    """
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
    健壮的剪贴板数据获取和解析函数。
    它会模拟 "全选" (Ctrl+A) 和 "复制" (Ctrl+C)，然后优先尝试用HTML格式解析剪贴板内容。
    这是获取当前屏幕题目信息的主要入口点。

    Returns:
        dict or None: 成功解析则返回包含题目信息的字典，否则返回None。
    """
    logger.info("正在通过剪贴板获取题目信息 (HTML模式)...")
    # 模拟键盘操作，确保题目区域被选中并复制
    pyautogui.hotkey('ctrl', 'a'); time.sleep(DELAY_AFTER_SELECT_ALL)
    pyautogui.hotkey('ctrl', 'c'); time.sleep(DELAY_AFTER_COPY)
    
    html_content = _get_html_from_clipboard()
    if not html_content:
        logger.error("❌ 未能从剪贴板获取HTML内容。请确保目标窗口支持HTML复制。")
        return None
        
    parsed_data = _parse_html_data(html_content)
    if parsed_data:
        logger.info(f"✅ [HTML解析成功] 题目: {parsed_data['q_num']}, 已选: {parsed_data['selected_options'] or '无'}")
        return parsed_data
    else:
        logger.error("❌ HTML内容解析失败，无法获取题目信息。")
        # 将解析失败的HTML内容保存到文件，以便于调试分析问题
        failed_html_path = os.path.join(LOG_DIR, f"failed_parse_{RUN_TIMESTAMP}.html")
        with open(failed_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.error(f"失败的HTML内容已保存至: {failed_html_path}")
        return None

# --- 逻辑函数 ---

def find_submit_button_with_scroll(q_num, screenshot_dir):
    """
    在屏幕上查找“提交”按钮，如果找不到，则尝试滚动页面后再次查找。

    Args:
        q_num (str): 当前题号，用于命名截图文件。
        screenshot_dir (str): 保存截图的目录。

    Returns:
        tuple: (坐标, 是否滚动过)，如果找到按钮，返回其在区域内的相对坐标和是否经过滚动；
               如果最终没找到，返回 (None, True)。
    """
    # 清理题号中的非法文件名字符
    safe_q_num = re.sub(r'[\\/*?:"<>|]', "_", q_num) if q_num else "unknown_q"
    screenshot_path_1 = os.path.join(screenshot_dir, f"{safe_q_num}_1_find_submit.png")
    
    # 第一次尝试，不滚动
    screen_img = capture_region(filename=screenshot_path_1)
    submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
    if submit_pos:
        return submit_pos, False # 找到了，且未滚动

    logger.info(f"未找到[提交按钮]，开始滚动查找...")
    for i in range(MAX_SCROLL_ATTEMPTS):
        scroll_in_region()
        time.sleep(POST_SCROLL_DELAY)
        screen_img = capture_region() # 滚动后重新截图
        submit_pos = TEMPLATE_SUBMIT.match_in(screen_img)
        if submit_pos:
            screenshot_path_2 = os.path.join(screenshot_dir, f"{safe_q_num}_2_scrolled_submit.png")
            cv2.imwrite(screenshot_path_2, screen_img) # 保存找到按钮的截图
            logger.info(f"滚动后找到[提交按钮]。已保存滚动后的截图: {screenshot_path_2}")
            return submit_pos, True # 找到了，且滚动过
            
    logger.warning(f"滚动 {MAX_SCROLL_ATTEMPTS} 次后仍未找到[提交按钮]！")
    return None, True # 最终没找到

def find_available_options():
    """
    在当前屏幕截图中查找所有可见的选项标识 (A, B, C, D)。

    Returns:
        dict: 一个字典，键为选项名 ('A', 'B', ...)，值为其在区域内的相对坐标。
    """
    available = {}
    screen_img = capture_region()
    # 遍历所有选项模板进行匹配
    for name, template_list in sorted(TEMPLATE_OPTIONS.items()):
        for template in template_list:
            pos = template.match_in(screen_img)
            if pos:
                available[name] = pos
                break # 找到一个匹配的模板后，就不用再试这个选项的其他模板了
    if not available:
        logger.warning("在当前屏幕上未找到任何选项标识 (A, B, C, D)。")
    return available

def validate_all_options_visible():
    """
    脚本启动时的预检函数。检查是否能识别出所有必需的选项模板 (A,B,C,D)。
    这有助于在脚本开始长时间运行前，发现模板问题或环境问题。

    Returns:
        bool: 如果所有选项都成功匹配，返回True；否则返回False。
    """
    logger.info("="*20 + " 开始初始环境校验 " + "="*20)
    logger.info(f"脚本将在{INITIAL_VALIDATION_DELAY}秒后进行屏幕选项校验...")
    time.sleep(INITIAL_VALIDATION_DELAY)
    
    screen_img = capture_region(filename=os.path.join(SCREENSHOT_RUN_DIR, "validation_screenshot.png"))
    expected_options = set(TEMPLATE_OPTIONS.keys())
    found_options_map = find_available_options() # 直接复用查找函数
    found_options = set(found_options_map.keys())

    if expected_options.issubset(found_options):
        logger.info("✅ [校验通过] 所有必需的选项模板 (A, B, C, D) 均已成功匹配。")
        return True
    else:
        missing_options = expected_options - found_options
        logger.critical(f"❌ [校验失败] 未能匹配到所有必需的选项模板！缺失的选项: {sorted(list(missing_options))}")
        logger.critical("请检查 'templates' 文件夹中的图片是否正确，或者调整配置中的相似度阈值。")
        return False

def initialize_and_activate():
    """
    初始化函数，尝试点击一次“提交”按钮来激活目标窗口，确保后续操作有效。
    
    Returns:
        bool: 激活成功返回 True, 否则 False。
    """
    logger.info("正在进行初始化操作：激活窗口...")
    submit_pos, _ = find_submit_button_with_scroll("initial_check", SCREENSHOT_RUN_DIR)
    if submit_pos:
        logger.info("找到[提交按钮]，点击一次以激活窗口。")
        click_at_region_pos(submit_pos)
        time.sleep(POST_ACTIVATION_CLICK_DELAY) # 等待可能的弹窗或反应
        return True
    else:
        logger.error("初始化失败：未能找到[提交按钮]来激活窗口。请确保目标答题界面已在前台。")
        return False

def load_qa_bank():
    """在脚本启动时从JSON文件加载题库数据到全局变量 qa_bank。"""
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
    """
    在提交答案后，等待并检查题目是否已经刷新。

    Args:
        current_q_text (str): 当前问题的文本，用于对比。

    Returns:
        bool: 如果题目已刷新，返回True；否则返回False。
    """
    logger.info(f"等待 {FIXED_POST_SUBMIT_DELAY} 秒后检查题目是否刷新...")
    time.sleep(FIXED_POST_SUBMIT_DELAY)
    new_q_info = get_clipboard_data_robust()
    # 如果能获取到新题目信息，并且题目文本与之前不同，则认为刷新成功
    return new_q_info and new_q_info.get('q_text') != current_q_text

def write_solution_map_to_file():
    """在脚本结束时，将本次运行解出的所有题目和答案写入一个JSON文件。"""
    if not solved_questions:
        logger.info("没有成功解答任何题目，无需生成答案映射文件。")
        return
    map_file_path = os.path.join(SCREENSHOT_RUN_DIR, "solution_map.json")
    logger.info(f"正在将 {len(solved_questions)} 条解题记录写入答案映射文件: {map_file_path}")
    try:
        with open(map_file_path, 'w', encoding='utf-8') as f:
            # 使用 atexit 注册的函数会在程序退出时调用
            # indent=4 使得json文件格式化，易于阅读
            json.dump(solved_questions, f, ensure_ascii=False, indent=4)
        logger.info("答案映射文件写入成功。")
    except Exception as e:
        logger.error(f"写入答案映射文件失败: {e}")

# ============================ 【核心升级】带验证的解答函数 ============================

def verify_and_click(options_to_select, options_pos, max_retries=2):
    """
    【高可靠性点击函数】点击指定选项后，通过读取剪贴板HTML来验证是否真的选中成功。
    如果验证失败，会进行重试。这是确保多选题正确选择的关键。

    Args:
        options_to_select (list): 期望被选中的选项列表，例如 ['A', 'C']。
        options_pos (dict): 各选项的屏幕坐标字典。
        max_retries (int, optional): 最大重试次数。 Defaults to 2.

    Returns:
        bool: 如果最终验证成功，返回True；否则返回False。
    """
    # 如果环境不支持HTML验证，则退化为直接点击，并假定成功。
    if not IS_WINDOWS:
        for opt in options_to_select:
            click_at_region_pos(options_pos.get(opt))
            time.sleep(POST_TOUCH_DELAY)
        return True

    expected_selection = set(options_to_select)
    
    for attempt in range(max_retries):
        logger.info(f"  -> 第 {attempt+1}/{max_retries} 次尝试点击并验证: {options_to_select}")
        
        # 1. 先获取当前的选中状态
        current_data = get_clipboard_data_robust()
        if not current_data:
            logger.warning("  -> 点击前无法获取剪贴板数据，将直接执行点击。")
            current_selection = set()
        else:
            current_selection = set(current_data.get('selected_options', []))
        
        # 2. 智能计算需要点击的选项
        #    - to_select: 期望选中但当前未选中的 (需要点击)
        #    - to_deselect: 当前选中但期望不选中的 (需要再次点击以取消)
        to_select = expected_selection - current_selection
        to_deselect = current_selection - expected_selection
        
        # 先取消多余的，再选中需要的
        for opt in (list(to_deselect) + list(to_select)):
            click_at_region_pos(options_pos.get(opt))
            time.sleep(POST_TOUCH_DELAY)
        
        # 3. 验证结果
        time.sleep(DELAY_BEFORE_VERIFY_CLICK) # 等待UI反应
        verified_data = get_clipboard_data_robust()
        actual_selection = set(verified_data.get('selected_options', [])) if verified_data else set()

        if actual_selection == expected_selection:
            logger.info(f"  -> ✅ 验证成功，选项 {sorted(list(expected_selection))} 已被正确选中。")
            return True
        else:
            logger.warning(f"  -> ❌ 验证失败。期望选中: {sorted(list(expected_selection))}, 实际选中: {sorted(list(actual_selection))}")
    
    logger.error(f"  -> ❌ 经过 {max_retries} 次尝试后，仍无法正确选中选项 {options_to_select}。")
    return False

def solve_with_qa_bank(q_info, options_pos, submit_pos):
    """
    使用已加载的题库尝试解答问题。
    它会先匹配问题文本，如果匹配成功，再匹配当前屏幕上的选项集合是否与题库中记录的一致。
    这种方式可以处理同一问题有不同选项顺序或内容变体的情况。

    Args:
        q_info (dict): 当前题目的信息。
        options_pos (dict): 可见选项的坐标。
        submit_pos (tuple): 提交按钮的坐标。

    Returns:
        str or list: 如果解答成功，返回正确答案列表。如果题库无答案或答案错误，返回 'FALLBACK' 请求使用遍历模式。
    """
    q_text = q_info['q_text']
    
    # 1. 检查题库中是否存在该问题文本
    if q_text not in qa_bank:
        logger.info(f"题库中未找到题目: '{q_text[:30]}...'")
        return 'FALLBACK'

    # 2. 获取当前屏幕上的选项内容集合，用于匹配
    current_options_set = set(q_info['options'].values())
    
    # 3. 遍历该问题的所有已知答案变种 (variants)
    for variant in qa_bank[q_text]:
        known_options_set = set(variant['options'])
        
        # 4. 如果当前选项集合与题库中某个变种的选项集合完全匹配
        if current_options_set == known_options_set:
            correct_answer_texts = variant['answer']
            logger.info(f"✅ 在题库中找到题目和完全匹配的选项集，预设答案: {correct_answer_texts}")

            # 将答案文本反向映射回选项字母 (A, B, C, D)
            options_text_to_letter = {v: k for k, v in q_info['options'].items()}
            letters_to_click = [options_text_to_letter[ans] for ans in correct_answer_texts if ans in options_text_to_letter]
            
            if not letters_to_click or len(letters_to_click) != len(correct_answer_texts):
                logger.error("严重错误：题库答案与当前选项无法完全对应，这不应该发生。")
                return 'FALLBACK'

            logger.info(f"--- [题库模式] 尝试解答，点击选项: {letters_to_click} ---")
            # 使用带验证的点击函数
            if verify_and_click(letters_to_click, options_pos):
                click_at_region_pos(submit_pos)
                if wait_for_next_question(q_text):
                    logger.info(f"🎉 [题库模式] 解答成功！")
                    return correct_answer_texts # 返回正确答案
                else:
                    logger.warning(f"[题库模式] 提交后题目未刷新，题库答案可能已失效或错误。")
            
            # 如果题库答案错误，则回退到遍历模式
            logger.error(f"[题库模式] 解答失败。将回退到遍历模式。")
            return 'FALLBACK'
    
    # 遍历完所有变种，没有找到匹配的选项集
    logger.info(f"题库中虽有同名问题，但选项集不匹配。这是一个新变种，将使用遍历模式解答。")
    return 'FALLBACK'

def solve_single_choice(q_info, options_pos, submit_pos):
    """
    【遍历模式】解答单选题。依次尝试每个选项，直到成功。

    Args:
        q_info (dict): 当前题目信息。
        options_pos (dict): 可见选项坐标。
        submit_pos (tuple): 提交按钮坐标。

    Returns:
        list or None: 成功则返回包含正确答案文本的列表，失败则返回None。
    """
    logger.info(f"--- [遍历模式] 开始解答单选题: {q_info['q_num']} ---")
    # 按字母顺序尝试
    for option_name in sorted(options_pos.keys()):
        logger.info(f"尝试单选项 [{option_name}]...")
        # 使用带验证的点击
        if verify_and_click([option_name], options_pos):
            click_at_region_pos(submit_pos)
            if wait_for_next_question(q_info['q_text']):
                correct_answer_text = q_info['options'][option_name]
                logger.info(f"🎉 [遍历模式] 单选题 [{q_info['q_num']}] 的正确答案是: [{correct_answer_text}]")
                return [correct_answer_text] # 以列表形式返回
            else:
                logger.info(f"选项 [{option_name}] 错误，继续...")
    logger.error(f"单选题 {q_info['q_text']} 在所有尝试后仍未解决。")
    return None

def solve_multiple_choice(q_info, options_pos, submit_pos):
    """
    【遍历模式】解答多选题。从2个选项的组合开始，依次尝试所有可能的组合。

    Args:
        q_info (dict): 当前题目信息。
        options_pos (dict): 可见选项坐标。
        submit_pos (tuple): 提交按钮坐标。

    Returns:
        list or None: 成功则返回包含所有正确答案文本的列表，失败则返回None。
    """
    logger.info(f"--- [遍历模式] 开始解答多选题: {q_info['q_num']} ---")
    option_letters = sorted(options_pos.keys())
    # 多选题至少选2个，最多全选
    start_size = 2 if len(option_letters) > 1 else 1
    
    for i in range(start_size, len(option_letters) + 1):
        # 生成所有长度为 i 的组合
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

# ============================ 主循环 (已集成重试机制) ============================
def main_loop():
    """脚本的主执行循环，集成了题目解答的重试机制。"""
    last_question_text = "初始化占位符"
    
    while True:
        logger.info("\n" + "="*20 + " 新一轮检测循环 " + "="*20)
        q_info = get_clipboard_data_robust()
        
        if not q_info or not q_info.get('q_text'):
            logger.error(f"无法获取或解析当前题目信息，脚本可能卡住或已结束。等待{RETRY_DELAY_ON_ERROR}秒后重试..."); 
            time.sleep(RETRY_DELAY_ON_ERROR)
            continue
        
        current_q_text = q_info['q_text']
        
        # 只有当题目文本发生变化时，才开始新一轮的解答
        if current_q_text != last_question_text:
            logger.info(f"检测到新题目: {q_info['q_num']} - {current_q_text}")
            
            # 检查是否到达预设的停止题号
            if STOP_AT_QUESTION_NUM and q_info.get('q_num') == STOP_AT_QUESTION_NUM:
                logger.info(f"已到达预设的停止题号: {STOP_AT_QUESTION_NUM}。脚本将正常停止。")
                capture_region(filename=os.path.join(SCREENSHOT_RUN_DIR, f"{q_info['q_num']}_stop_screenshot.png"))
                break

            correct_answer = None
            # ======================= 新增：重试循环 =======================
            for attempt in range(MAX_SOLVE_ATTEMPTS):
                logger.info(f"--- 开始第 {attempt + 1}/{MAX_SOLVE_ATTEMPTS} 次尝试解答 [{q_info['q_num']}] ---")

                # 寻找提交按钮和可用选项
                submit_pos, _ = find_submit_button_with_scroll(q_info['q_num'], SCREENSHOT_RUN_DIR)
                if not submit_pos:
                    logger.error(f"在题目 {q_info['q_num']} 找不到[提交按钮]，此次尝试失败。");
                    time.sleep(RETRY_DELAY_BETWEEN_ATTEMPTS)
                    continue # 继续下一次重试
                
                options_pos = find_available_options()
                if not options_pos:
                    logger.error(f"在题目 {q_info['q_num']} 找不到任何选项，此次尝试失败。");
                    time.sleep(RETRY_DELAY_BETWEEN_ATTEMPTS)
                    continue # 继续下一次重试
                
                # 开始解题
                use_fallback = False
                # 如果启用题库，优先使用题库
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
                    else: # 默认为多选题
                        correct_answer = solve_multiple_choice(q_info, options_pos, submit_pos)

                # 如果成功解出答案，则跳出重试循环
                if correct_answer:
                    logger.info(f"🎉 在第 {attempt + 1} 次尝试中成功解答 [{q_info['q_num']}]！")
                    break
                else:
                    logger.warning(f"第 {attempt + 1} 次尝试解答失败。将在 {RETRY_DELAY_BETWEEN_ATTEMPTS} 秒后重试...")
                    time.sleep(RETRY_DELAY_BETWEEN_ATTEMPTS)
            # ======================= 重试循环结束 =======================

            # 在所有重试结束后，检查最终是否成功
            if correct_answer:
                # ------ 【核心记录逻辑】 ------
                q_text = q_info['q_text']
                current_options_sorted = sorted(list(q_info['options'].values()))
                new_entry = {"options": current_options_sorted, "answer": correct_answer}
                if q_text not in solved_questions:
                    solved_questions[q_text] = []
                is_existing_variant = any(
                    entry["options"] == current_options_sorted for entry in solved_questions[q_text]
                )
                if not is_existing_variant:
                    solved_questions[q_text].append(new_entry)
                # ------ 【记录逻辑结束】 ------

                # 更新上一题文本，防止重复解答
                last_question_text = current_q_text
            else:
                # 如果所有重试都失败了，才终止脚本
                logger.critical(f"题目 {q_info['q_num']} 在 {MAX_SOLVE_ATTEMPTS} 次尝试后仍未能成功解答，脚本终止！")
                break
        else:
            logger.info(f"题目未变({q_info.get('q_num', '未知')})，等待{POLLING_INTERVAL_NO_CHANGE}秒..."); 
            time.sleep(POLLING_INTERVAL_NO_CHANGE)

# ============================ 程序入口 ============================
if __name__ == "__main__":
    try:
        # 1. 加载题库（如果启用）
        load_qa_bank()

        # 2. 初始化并激活窗口
        if not initialize_and_activate():
            exit()

        # 3. 运行环境预检
        if not validate_all_options_visible():
            exit()
        
        # 4. 进入主循环
        main_loop()

    except pyautogui.FailSafeException:
        # pyautogui的紧急停止机制：将鼠标快速移动到屏幕左上角
        logger.critical("Fail-Safe触发！鼠标移动到屏幕左上角，脚本已紧急停止。")
    except Exception as e:
        # 捕获所有其他未预料到的异常
        logger.exception("脚本运行过程中发生未处理的异常！")
    finally:
        # 无论脚本是正常结束还是异常中断，都尝试保存已解出的答案
        write_solution_map_to_file()
        logger.info("脚本执行结束。")