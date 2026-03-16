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
* `03/12`优化显示逻辑，优先显示未完成的日程，已完成的日程划线表示；优化字体显示，统一微软雅黑；优化详细日程窗口大小，实现自动伸缩；优化详细日志的文本编辑；优化日历界面，边框高亮当日。
* `03/16`平均日期窗口的尺寸；优化颜色逻辑；增加LLM概括方案。

# TODO
日期窗口的尺寸受到自动伸缩和内容的影响，需寻求更好的解决方案