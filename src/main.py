"""日程管理工具（按天管理，支持完成/未完成状态）。

日程数据保存在 `schedules.json`。
"""

import argparse
import calendar
import hashlib
import json
import os
import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime, time, timedelta
from typing import Dict, List, Any
import customtkinter as ctk
import requests
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)
API_KEY = os.getenv("API_KEY")

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


def _compute_tasks_hash(tasks: List[Dict[str, Any]]) -> str:
    """对未完成任务列表计算稳定哈希，便于判断内容是否变更。"""
    normalized = json.dumps(
        sorted(
            [{"text": t.get("text", ""), "done": bool(t.get("done"))} for t in tasks],
            key=lambda x: (x["text"], x["done"]),
        ),
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _generate_llm_suggestion(date_str: str, tasks: List[Dict[str, Any]]) -> str:
    """调用LLM获取简短建议，如果失败则返回占位提示。"""
    prompt_tasks = "\n".join([f"- {t.get('text', '')}" for t in tasks])
    prompt = (
        f"你是一个日程助理。请针对 {date_str} 的以下未完成任务，给出1-2句简短可执行建议：\n{prompt_tasks}\n"
        "只要给出建议，不要其他多余说明。"
    )

    url = "https://models.sjtu.edu.cn/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    messages = [{"role": "user", "content": f"{prompt}"}]
    data = {
        "messages": messages,
        "stream": False,
        "do_sample": True,
        "repetition_penalty": 1.00,
        "temperature": 1e-5,
        "top_k": 20,
        "model": "deepseek-v3",  # Model name
    }
    try:
        while True:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content'].strip()
            else:
                time.sleep(5)
                print(f"LLM 请求失败（状态码 {response.status_code}），5秒后重试...")
                continue
    except Exception as e:
        return f"[LLM 调用失败：{e}]"


def update_llm_suggestions(data: Dict[str, Any]) -> Dict[str, Any]:
    """每次运行时，针对每个有未完成日程的日期，判断是否需要重新调用 LLM，生成建议并缓存。"""
    if not isinstance(data, dict):
        return {}

    cache: Dict[str, Any] = data.setdefault("_llm_cache", {})

    dates_with_pending = [
        d for d, tasks in data.items()
        if d != "_llm_cache" and isinstance(tasks, list) and any(not t.get("done") for t in tasks)
    ]

    # 删除已无未完成任务的缓存
    removed = [d for d in list(cache.keys()) if d not in dates_with_pending]
    for d in removed:
        cache.pop(d, None)

    for date in sorted(dates_with_pending):
        pending_tasks = [t for t in data.get(date, []) if not t.get("done")]
        if not pending_tasks:
            continue

        current_hash = _compute_tasks_hash(pending_tasks)
        entry = cache.get(date, {})

        if entry.get("hash") == current_hash and entry.get("suggestion"):
            continue

        suggestion = _generate_llm_suggestion(date, pending_tasks)
        cache[date] = {
            "hash": current_hash,
            "suggestion": suggestion,
            "updated_at": datetime.now().isoformat(),
        }

    data["_llm_cache"] = cache
    save_data(data)
    return cache


def list_dates(data: Dict[str, List[Dict[str, Any]]]) -> None:
    # 忽略 _llm_cache 等元数据
    dates = [d for d in data.keys() if d != "_llm_cache"]
    if not dates:
        print("没有任何日程。")
        return

    for date in sorted(dates):
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
    update_llm_suggestions(data)

    root = ctk.CTk()
    root.title("日程管理")
    root.geometry("1080x720")
    # 保证窗口在缩小时仍能完整显示底部按钮
    root.minsize(640, 540)

    # 当前展示的月份（第一天）
    display_month = datetime.today().date().replace(day=1)
    selected_date = tk.StringVar(value=datetime.today().date().isoformat())

    def _format_cell_text(text: str, max_len: int = 12) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _day_summary(date_str: str) -> tuple[str, bool]:
        """返回 (显示文本, 是否完成) """
        tasks = data.get(date_str, [])
        if not tasks:
            return "", False
        # 优先展示未完成的日程，其次展示第一条。
        unfinished = [t for t in tasks if not t.get("done")]
        primary = unfinished[0] if unfinished else tasks[0]
        first = _format_cell_text(primary.get("text", ""), max_len=8)
        extra = len(tasks) - 1
        text = f"{first} (+{extra})" if extra > 0 else first
        return text, bool(primary.get("done"))

    selected_task_index: int | None = None

    def _refresh_detail():
        nonlocal selected_task_index
        date_str = selected_date.get()
        detail_date_label.configure(text=date_str)
        detail_text.configure(state="normal")

        # 清理并重新填充内容
        detail_text.delete("1.0", "end")
        detail_text.tag_remove("selected", "1.0", "end")

        tasks = data.get(date_str, [])
        if selected_task_index is not None and (selected_task_index < 0 or selected_task_index >= len(tasks)):
            # 超出范围时取消选中
            selected_task_index = None

        for idx, task in enumerate(tasks, start=1):
            prefix = "✔ " if task.get("done") else "  "
            line = f"{idx:>2}. {prefix}{task.get('text')}\n"
            detail_text.insert("end", line)
            if task.get("done"):
                detail_text.tag_add("done", f"{idx}.0", f"{idx}.end")
            if selected_task_index is not None and idx - 1 == selected_task_index:
                detail_text.tag_add("selected", f"{idx}.0", f"{idx}.end")

        detail_text.configure(state="disabled")

        suggestion = data.get("_llm_cache", {}).get(date_str, {}).get("suggestion", "(无建议)")
        detail_suggestion_label.configure(text=f"建议：{suggestion}")

    def _select_line(event):
        nonlocal selected_task_index
        index = detail_text.index(f"@{event.x},{event.y}")
        line = int(index.split(".")[0])
        selected_task_index = line - 1
        _refresh_detail()

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
        if selected_task_index is None:
            return
        idx = selected_task_index + 1
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
            ctk.CTkLabel(calendar_frame, text=name, font=ctk.CTkFont(family="Microsoft YaHei", weight="bold")).grid(row=0, column=col, padx=2, pady=2)

        cal = calendar.Calendar(firstweekday=0)
        weeks = cal.monthdatescalendar(display_month.year, display_month.month)

        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                day_str = day.isoformat()
                is_current_month = day.month == display_month.month
                is_selected = day_str == selected_date.get()

                # 当月有任务：亮蓝；当月无任务或任务已完成：暗蓝；不当月有任务：灰色；不当月无任务或任务已完成：深灰。
                if is_current_month:
                    if day_str in data and any(not t.get("done") for t in data[day_str]):
                        fg_color = "#2ab6c3"
                    else:
                        fg_color = "#2ac3a7"
                else:
                    if day_str in data and any(not t.get("done") for t in data[day_str]):
                        fg_color = "#7a7a7a"
                    else:
                        fg_color = "#3b3b3b"

                cell_width = 130
                cell_height = 90
                frame = ctk.CTkFrame(calendar_frame, fg_color=fg_color, corner_radius=8, border_width=2, border_color="#000000", width=cell_width, height=cell_height)
                frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                frame.grid_propagate(False)

                # 选中高亮
                if is_selected:
                    frame.configure(border_color="#ffde59", border_width=3)

                # 日期
                ctk.CTkLabel(
                    frame,
                    text=str(day.day),
                    text_color="#ffffff" if is_current_month else "#cccccc",
                    font=ctk.CTkFont(family="Microsoft YaHei", weight="bold"),
                ).pack(anchor="nw", padx=6, pady=4)

                # 日程摘要
                summary_text, summary_done = _day_summary(day_str)
                if summary_text:
                    font_kwargs = {}
                    if summary_done:
                        font_kwargs["overstrike"] = 1

                    ctk.CTkLabel(
                        frame,
                        text=summary_text,
                        text_color="#ffffff" if is_current_month else "#dddddd",
                        justify="left",
                        wraplength=cell_width - 5,
                        font=ctk.CTkFont(family="Microsoft YaHei", **font_kwargs) if font_kwargs else ctk.CTkFont(family="Microsoft YaHei"),
                    ).pack(anchor="nw", padx=6, pady=(0, 4))

                frame.bind("<Button-1>", lambda e, d=day_str: _select_date(d))

        # 均分行高列宽，并设定最小高度/最小宽度，避免单元格因文本内容浮动
        for row in range(1, len(weeks) + 1):
            calendar_frame.grid_rowconfigure(row, weight=1, minsize=95)
        for col in range(7):
            calendar_frame.grid_columnconfigure(col, weight=1, minsize=130)

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
    month_label = ctk.CTkLabel(header, text=display_month.strftime("%Y-%m"), font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"))
    month_label.pack(side="left", padx=8)
    ctk.CTkButton(header, text=">>", width=40, command=lambda: _change_month(1)).pack(side="left", padx=4)

    # 日历区域
    calendar_frame = ctk.CTkFrame(root)
    calendar_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # 日程详情区
    detail_frame = ctk.CTkFrame(root)
    detail_frame.pack(fill="both", padx=10, pady=(0, 10))

    # 使用 grid 布局，保证在窗口缩小时：
    # 1) 详情文本区域可缩放；
    # 2) 底部按钮区始终可见。
    detail_frame.grid_rowconfigure(2, weight=1)
    detail_frame.grid_columnconfigure(0, weight=1)

    detail_date_label = ctk.CTkLabel(detail_frame, text=selected_date.get(), font=ctk.CTkFont(family="Microsoft YaHei", size=16, weight="bold"))
    detail_date_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(8, 4))

    detail_suggestion_label = ctk.CTkLabel(detail_frame, text="", fg_color="#fff7d6", text_color="#5a3e00", corner_radius=8, anchor="w", padx=8, pady=4)
    detail_suggestion_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 8))

    # 不指定固定高度，让窗口缩小时顶部内容可收缩，确保按钮区域始终可见
    detail_text = tk.Text(detail_frame, wrap="word", borderwidth=0, highlightthickness=0, font=("Microsoft YaHei", 14))
    detail_text.grid(row=2, column=0, sticky="nsew", pady=(0, 4))

    detail_scroll = tk.Scrollbar(detail_frame, command=detail_text.yview)
    detail_text.configure(yscrollcommand=detail_scroll.set)
    detail_scroll.grid(row=2, column=1, sticky="ns", pady=(0, 4))

    detail_text.tag_configure("done", overstrike=1, foreground="#888888")
    detail_text.tag_configure("selected", background="#f0f0f0")
    detail_text.bind("<Button-1>", _select_line)

    detail_entry = ctk.CTkEntry(detail_frame, placeholder_text="在此输入新任务并回车")
    detail_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 4))
    detail_entry.bind("<Return>", lambda e: _add_task_detail())

    btns = ctk.CTkFrame(detail_frame)
    btns.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6))

    # 1. 定义字体对象
    # family: 字体名称 (如 "Microsoft YaHei", "Arial")
    # size: 字号
    # weight: 粗细 ("bold", "normal")
    button_font = ctk.CTkFont(family="Microsoft YaHei", size=14, weight="bold")
    # 2. 在按钮中应用
    ctk.CTkButton(btns, text="添加", font=button_font, command=_add_task_detail).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="完成", font=button_font, command=lambda: _operate_task("done")).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="未完成", font=button_font, command=lambda: _operate_task("undone")).pack(side="left", expand=True, padx=4)
    ctk.CTkButton(btns, text="删除", font=button_font, fg_color="#d9534f", hover_color="#c9302c", command=lambda: _operate_task("remove")).pack(side="left", expand=True, padx=4)

    _refresh_calendar()
    _refresh_detail()

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Daily 日程管理")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("list-dates", help="列出所有有日程的日期")
    view_parser = subparsers.add_parser("view", help="查看某天日程")
    view_parser.add_argument("date")
    add_parser = subparsers.add_parser("add", help="增加某天日程")
    add_parser.add_argument("date")
    add_parser.add_argument("text")
    done_parser = subparsers.add_parser("done", help="标记任务完成")
    done_parser.add_argument("date")
    done_parser.add_argument("index", type=int)
    undone_parser = subparsers.add_parser("undone", help="标记任务未完成")
    undone_parser.add_argument("date")
    undone_parser.add_argument("index", type=int)
    remove_parser = subparsers.add_parser("remove", help="删除任务")
    remove_parser.add_argument("date")
    remove_parser.add_argument("index", type=int)
    clear_parser = subparsers.add_parser("clear", help="清空某天日程")
    clear_parser.add_argument("date")
    subparsers.add_parser("gui", help="启动 GUI")
    subparsers.add_parser("suggest", help="触发 LLM 建议并输出")

    args = parser.parse_args()

    data = load_data()
    cache = update_llm_suggestions(data)

    if not args.command or args.command == "gui":
        run_gui()
        return

    if args.command == "list-dates":
        list_dates(data)
    elif args.command == "view":
        list_tasks(data, args.date)
        suggestion = cache.get(args.date, {}).get("suggestion")
        if suggestion:
            print(f"建议：{suggestion}")
    elif args.command == "add":
        add_task(data, args.date, args.text)
    elif args.command == "done":
        _set_done(data, args.date, args.index, True)
    elif args.command == "undone":
        _set_done(data, args.date, args.index, False)
    elif args.command == "remove":
        remove_task(data, args.date, args.index)
    elif args.command == "clear":
        clear_date(data, args.date)
    elif args.command == "suggest":
        if not cache:
            print("当前没有待处理的未完成日程。")
        for d, item in sorted(cache.items()):
            print(f"{d}: {item.get('suggestion', '(无建议)')}")


if __name__ == "__main__":
    main()
