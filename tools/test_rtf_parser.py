# clipboard_omni_dumper.py (剪贴板全格式转储工具)
"""
这是一个终极的剪贴板诊断和捕获工具。

它会监控剪贴板的任何变化，然后：
1. 列出剪贴板上所有可用的数据格式。
2. 遍历所有这些格式，并尝试将每一种格式的内容都保存为一个独立的文件。
3. 根据格式类型，自动使用正确的扩展名（.html, .txt, .dat等）。

这能确保我们不会遗漏任何有用的数据。
"""
import os
import time
import re

try:
    import win32clipboard
    import win32con
    import pywintypes
except ImportError:
    print("=" * 60)
    print("错误：未安装 'pywin32' 库。")
    print("请运行以下命令进行安装: pip install pywin32")
    print("=" * 60)
    exit()

# --- 配置 ---
OUTPUT_DIR = "clipboard_captures_all"  # 使用一个全新的目录
POLL_INTERVAL = 1.0

# --- 格式注册与映射 ---
# 预先定义已知格式ID到名称和扩展名的映射
# 这让我们的代码更清晰、更易于扩展
FORMAT_MAP = {
    # 标准格式
    win32con.CF_TEXT: {"name": "CF_TEXT (ANSI 纯文本)", "ext": "txt"},
    win32con.CF_UNICODETEXT: {"name": "CF_UNICODETEXT (Unicode 纯文本)", "ext": "txt"},
    win32con.CF_DIB: {"name": "CF_DIB (位图)", "ext": "bmp", "savable": False}, # 位图是句柄，不能直接保存
    win32con.CF_HDROP: {"name": "CF_HDROP (文件路径列表)", "ext": "txt", "savable": False}, # 文件列表是句柄
}

# 动态注册的格式，因为它们的ID不是固定的
try:
    CF_RTF = win32clipboard.RegisterClipboardFormat("Rich Text Format")
    FORMAT_MAP[CF_RTF] = {"name": "Rich Text Format", "ext": "rtf", "savable": True}
    
    CF_HTML = win32clipboard.RegisterClipboardFormat("HTML Format")
    FORMAT_MAP[CF_HTML] = {"name": "HTML Format", "ext": "html", "savable": True}
except Exception as e:
    print(f"[-] 警告：注册某些剪贴板格式时出错: {e}")

def sanitize_filename(name):
    """清理字符串，使其可以安全地用作文件名的一部分。"""
    # 移除非法字符，并将空格替换为下划线
    name = re.sub(r'[\\/*?:"<>|()]', "", name)
    name = name.replace(" ", "_")
    return name

def get_all_formats_info():
    """获取剪贴板上所有可用格式的ID和名称。"""
    available_formats = {}
    try:
        win32clipboard.OpenClipboard()
        fmt = win32clipboard.EnumClipboardFormats(0)
        while fmt:
            # 优先从我们的映射中查找名称
            name = FORMAT_MAP.get(fmt, {}).get("name")
            
            # 如果找不到，再尝试用API获取其注册名称
            if not name:
                try:
                    name = win32clipboard.GetClipboardFormatName(fmt)
                except pywintypes.error:
                    name = f"未知格式ID_{fmt}"
            
            available_formats[fmt] = name
            fmt = win32clipboard.EnumClipboardFormats(fmt)
    except pywintypes.error:
        pass
    finally:
        try: win32clipboard.CloseClipboard()
        except: pass
    return available_formats


def main():
    print("=" * 60)
    print("剪贴板全格式转储工具")
    print("=" * 60)
    print("[*] 正在监控剪贴板... 请进行一次复制操作。")
    print(f"[*] 捕获的文件将保存在 '{OUTPUT_DIR}' 文件夹中。")
    print("[*] 按 Ctrl+C 停止脚本。")
    print("-" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    last_clipboard_seq = 0
    capture_count = 0

    try:
        while True:
            current_seq = win32clipboard.GetClipboardSequenceNumber()
            if current_seq != last_clipboard_seq:
                last_clipboard_seq = current_seq
                capture_count += 1
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{timestamp}] 检测到剪贴板变化！ (捕获事件 #{capture_count})")

                # 获取所有可用格式
                all_formats = get_all_formats_info()
                print("[+] 剪贴板上所有可用的格式为:")
                for fmt_name in all_formats.values():
                    print(f"    - {fmt_name}")
                
                print("[+] 正在尝试保存所有可读格式...")
                
                try:
                    win32clipboard.OpenClipboard()
                    for fmt_id, fmt_name in all_formats.items():
                        try:
                            # 检查是否为我们已知的不支持直接保存的格式
                            if not FORMAT_MAP.get(fmt_id, {}).get("savable", True):
                                print(f"    - 跳过 '{fmt_name}': 此格式类型不支持直接保存。")
                                continue

                            # 获取数据
                            data = win32clipboard.GetClipboardData(fmt_id)
                            
                            # 根据数据类型处理并准备保存
                            content_to_save = None
                            if isinstance(data, str):
                                # 字符串需要编码为字节
                                content_to_save = data.encode('utf-8')
                            elif isinstance(data, bytes):
                                # 字节数据可以直接使用
                                content_to_save = data
                            else:
                                # 其他类型（如int句柄）我们无法直接保存
                                print(f"    - 跳过 '{fmt_name}': 数据类型为 {type(data).__name__}，无法直接保存。")
                                continue

                            # 准备文件名
                            ext = FORMAT_MAP.get(fmt_id, {}).get("ext", "dat") # 未知格式用 .dat
                            clean_name = sanitize_filename(fmt_name)
                            filename = os.path.join(OUTPUT_DIR, f"capture_{capture_count}_{clean_name}.{ext}")
                            
                            # 写入文件
                            with open(filename, "wb") as f:
                                f.write(content_to_save)
                            print(f"    - 成功: 已保存 '{fmt_name}' 到 {filename}")

                        except Exception as e:
                            print(f"    - 失败: 无法读取或保存格式 '{fmt_name}'. 原因: {e}")
                finally:
                    try: win32clipboard.CloseClipboard()
                    except: pass

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("脚本已被用户停止。")
        print(f"在 {capture_count} 次捕获事件中产生的文件已保存至 '{OUTPUT_DIR}' 目录。")
        print("=" * 60)


if __name__ == "__main__":
    main()