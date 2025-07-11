# get_region_tool.py
import pyautogui
import time

print("--- 屏幕区域坐标获取工具 ---")
print("请将鼠标移动到你手机投屏区域的 [左上角]，然后按下 Enter 键。")
input("按 Enter 键继续...")
pos1 = pyautogui.position()
print(f"已记录左上角坐标: {pos1}")



print("\n请将鼠标移动到你手机投屏区域的 [右下角]，然后按下 Enter 键。")
input("按 Enter 键继续...")
pos2 = pyautogui.position()
print(f"已记录右下角坐标: {pos2}")

left = pos1.x
top = pos1.y
width = pos2.x - pos1.x
height = pos2.y - pos1.y

if width < 0 or height < 0:
    print("\n错误：右下角的坐标必须大于左上角的坐标！请重新运行。")
else:
    region_tuple = (left, top, width, height)
    print("\n获取成功！")
    print("请将下面这行代码复制到你的主脚本配置区：")
    print(f"\nSCREEN_REGION = {region_tuple}\n")