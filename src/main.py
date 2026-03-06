"""日程管理工具（按天管理，支持完成/未完成状态）。

用法示例：
  python main.py view 2026-03-06
  python main.py add 2026-03-06 "买菜"
  python main.py done 2026-03-06 2
  python main.py list-dates

日程数据保存在 `schedules.json`。
"""

import argparse
import calendar
import json
import os
import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime, timedelta
from typing import Dict, List, Any
import customtkinter as ctk


DATA_FILE = os.path.join(os.path.dirname(__file__), '../log' ,"schedules.json")


def _ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def load_data() -> Dict[str, List[Dict[str, Any]]]:
    _ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_data(data: Dict[str, List[Dict[str, Any]]]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_date(date_str: str) -> str:
    """将日期标准化为 YYYY-MM-DD 格式。"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("日期格式不正确，请使用 YYYY-MM-DD，例如 2026-03-06。")


def list_dates(data: Dict[str, List[Dict[str, Any]]]) -> None:
    if not data:
        print("没有任何日程。")
        return

    for date in sorted(data.keys()):
        todo_count = len(data[date])
        done_count = sum(1 for item in data[date] if item.get("done"))
        print(f"{date}: {todo_count} 条（已完成 {done_count}/{todo_count}）")


def list_tasks(data: Dict[str, List[Dict[str, Any]]], date: str) -> None:
    date = normalize_date(date)
    tasks = data.get(date, [])
    if not tasks:
        print(f"{date} 没有日程。")
        return

    print(f"{date} 的日程（共 {len(tasks)} 条）：")
    for idx, task in enumerate(tasks, start=1):
        status = "✔" if task.get("done") else " "
        print(f"  {idx:>2}. [{status}] {task.get('text')}")


def add_task(data: Dict[str, List[Dict[str, Any]]], date: str, text: str) -> None:
    date = normalize_date(date)
    tasks = data.setdefault(date, [])
    tasks.append({"text": text, "done": False})
    save_data(data)
    print(f"已添加 ({date})：{text}")


def _set_done(data: Dict[str, List[Dict[str, Any]]], date: str, index: int, done: bool) -> None:
    date = normalize_date(date)
    tasks = data.get(date, [])
    if index < 1 or index > len(tasks):
        raise IndexError("任务编号超出范围")
    tasks[index - 1]["done"] = done
    save_data(data)
    state = "完成" if done else "未完成"
    print(f"已标记第 {index} 条为{state}：{tasks[index - 1]['text']}")


def remove_task(data: Dict[str, List[Dict[str, Any]]], date: str, index: int) -> None:
    date = normalize_date(date)
    tasks = data.get(date, [])
    if index < 1 or index > len(tasks):
        raise IndexError("任务编号超出范围")
    removed = tasks.pop(index - 1)
    if not tasks:
        data.pop(date, None)
    save_data(data)
    print(f"已删除：{removed.get('text')}")


def clear_date(data: Dict[str, List[Dict[str, Any]]], date: str) -> None:
    date = normalize_date(date)
    if date in data:
        data.pop(date)
        save_data(data)
        print(f"已清空 {date} 的所有日程。")
    else:
        print(f"{date} 没有日程可清空。")


def _format_task(task: Dict[str, Any]) -> str:
    status = "✔" if task.get("done") else " "
    return f"[{status}] {task.get('text')}"


def run_gui() -> None:
    """使用 customtkinter 提供可视化操作界面。"""
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("green")

    data = load_data()

    root = ctk.CTk()
    root.title("日程管理")
    root.geometry("800x600")

    # 当前展示的月份（第一天）
    display_month = datetime.today().date().replace(day=1)
    selected_date = tk.StringVar(value=datetime.today().date().isoformat())

    def _format_cell_text(text: str, max_len: int = 12) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _day_summary(date_str: str) -> str:
        tasks = data.get(date_str, [])
        if not tasks:
            return ""
        first = _format_cell_text(tasks[0].get("text", ""))
        extra = len(tasks) - 1
        if extra > 0:
            return f"{first}\n+{extra}"
        return first

    def _refresh_detail():
        date_str = selected_date.get()
        detail_date_label.configure(text=date_str)
        detail_listbox.delete(0, "end")
        for idx, task in enumerate(data.get(date_str, []), start=1):
            prefix = "✔ " if task.get("done") else "  "
            detail_listbox.insert("end", f"{idx:>2}. {prefix}{task.get('text')}")

    def _add_task_detail():
        date_str = selected_date.get()
        text = detail_entry.get().strip()
        if not text:
            return
        add_task(data, date_str, text)
        detail_entry.delete(0, "end")
        _refresh_detail()
        _refresh_calendar()

    def _operate_task(action: str):
        date_str = selected_date.get()
        sel = detail_listbox.curselection()
        if not sel:
            return
        idx = sel[0] + 1
        if action == "done":
            _set_done(data, date_str, idx, True)
        elif action == "undone":
            _set_done(data, date_str, idx, False)
        elif action == "remove":
            remove_task(data, date_str, idx)
        _refresh_detail()
        _refresh_calendar()

    def _select_date(date_str: str):
        normalized = normalize_date(date_str)
        selected_date.set(normalized)
        # 不自动在数据中创建空日期记录，仅在添加任务时才写入。
        _refresh_detail()
        _refresh_calendar()

    def _refresh_calendar():
        for child in calendar_frame.winfo_children():
            child.destroy()

        # 星期标题
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, name in enumerate(weekdays):
            ctk.CTkLabel(calendar_frame, text=name, font=ctk.CTkFont(weight="bold")).grid(row=0, column=col, padx=2, pady=2)

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(display_month.year, display_month.month)

        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                day_str = day.isoformat()
                is_current_month = day.month == display_month.month
                is_selected = day_str == selected_date.get()

                # 颜色规则：当月/不当月 + 是否有任务
                if is_current_month:
                    if day_str in data:
                        fg_color = "#2ab6c3"
                    else:
                        fg_color = "#2ac3a7"
                else:
                    if day_str in data:
                        fg_color = "#7a7a7a"
                    else:
                        fg_color = "#3b3b3b"

                frame = ctk.CTkFrame(calendar_frame, fg_color=fg_color, corner_radius=8, border_width=2, border_color="#000000")
                frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

                # 选中高亮
                if is_selected:
                    frame.configure(border_color="#ffde59", border_width=3)

                # 日期
                ctk.CTkLabel(
                    frame,
                    text=str(day.day),
                    text_color="#ffffff" if is_current_month else "#cccccc",
                    font=ctk.CTkFont(weight="bold"),
                ).pack(anchor="nw", padx=6, pady=4)

                # 日程摘要
                summary = _day_summary(day_str)
                if summary:
                    ctk.CTkLabel(
                        frame,
                        text=summary,
                        text_color="#ffffff" if is_current_month else "#dddddd",
                        justify="left",
                        wraplength=110,
                    ).pack(anchor="nw", padx=6, pady=(0, 4))

                frame.bind("<Button-1>", lambda e, d=day_str: _select_date(d))

        # 均分行高列宽
        for row in range(1, len(weeks) + 1):
            calendar_frame.grid_rowconfigure(row, weight=1)
        for col in range(7):
            calendar_frame.grid_columnconfigure(col, weight=1)

    # 头部：月份导航
    header = ctk.CTkFrame(root)
    header.pack(fill="x", padx=10, pady=10)

    def _change_month(delta: int):
        nonlocal display_month
        year = display_month.year + ((display_month.month - 1 + delta) // 12)
        month = (display_month.month - 1 + delta) % 12 + 1
        display_month = display_month.replace(year=year, month=month, day=1)
        month_label.configure(text=display_month.strftime("%Y-%m"))
        _refresh_calendar()

    ctk.CTkButton(header, text="<<", width=40, command=lambda: _change_month(-1)).pack(side="left", padx=4)
    month_label = ctk.CTkLabel(header, text=display_month.strftime("%Y-%m"), font=ctk.CTkFont(size=16, weight="bold"))
    month_label.pack(side="left", padx=8)
    ctk.CTkButton(header, text=">>", width=40, command=lambda: _change_month(1)).pack(side="left", padx=4)

    # 日历区域
    calendar_frame = ctk.CTkFrame(root)
    calendar_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # 日程详情区
    detail_frame = ctk.CTkFrame(root)
    detail_frame.pack(fill="x", padx=10, pady=(0, 10))

    detail_date_label = ctk.CTkLabel(detail_frame, text=selected_date.get(), font=ctk.CTkFont(size=16, weight="bold"))
    detail_date_label.pack(anchor="w", pady=(8, 4))

    detail_listbox = tk.Listbox(detail_frame, activestyle="none", height=6, font=("Arial", 18))
    detail_listbox.pack(fill="x", pady=(0, 4))
    detail_scroll = tk.Scrollbar(detail_frame, command=detail_listbox.yview)
    detail_listbox.config(yscrollcommand=detail_scroll.set)
    detail_scroll.pack(side="right", fill="y")

    detail_entry = ctk.CTkEntry(detail_frame, placeholder_text="在此输入新任务并回车")
    detail_entry.pack(fill="x", pady=(0, 4))
    detail_entry.bind("<Return>", lambda e: _add_task_detail())

    btns = ctk.CTkFrame(detail_frame)
    btns.pack(fill="x", pady=(0, 6))
    ctk.CTkButton(btns, text="添加", command=_add_task_detail).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="完成", command=lambda: _operate_task("done")).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="未完成", command=lambda: _operate_task("undone")).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="删除", fg_color="#d9534f", hover_color="#c9302c", command=lambda: _operate_task("remove")).pack(side="left", expand=True, padx=4)

    _refresh_calendar()
    _refresh_detail()

    root.mainloop()


def main():
    run_gui()


if __name__ == "__main__":
    main()
