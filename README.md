# Daily
> schedule manage

## 使用说明

本项目实现了一个按天管理的日程工具，支持为每个日程添加「完成/未完成」状态。

### 运行方式

```bash
python src/main.py list-dates
python src/main.py view 2026-03-06
python src/main.py add 2026-03-06 "买菜"
python src/main.py done 2026-03-06 1
python src/main.py undone 2026-03-06 1
python src/main.py remove 2026-03-06 1
python src/main.py clear 2026-03-06
python src/main.py gui
```

> GUI 版本依赖 customtkinter：
> ```bash
> pip install customtkinter
> ```
>
> GUI 支持在当前日期前后一个月范围内直接选择日期，并可通过界面按钮切换范围。

日程数据存储在 `log/schedules.json`。

# Logs

* `03/06`按天管理日程，支持完成/未完成状态。
