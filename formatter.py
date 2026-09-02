from datetime import datetime

WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

def format_schedule_response(parsed_data, today_only=False):
    if not parsed_data:
        return "⚠️ Не удалось получить данные с сайта."

    now = datetime.now()
    target_short = now.strftime("%d.%m")

    if today_only:
        today_data = None
        for day in parsed_data:
            if day.get("date") == target_short:
                today_data = day
                break

        if not today_data:
            weekday_name = WEEKDAYS[now.weekday()]
            today_full = now.strftime("%d.%m.%Y")
            return (
                f"📅 Сегодня <b>{weekday_name} ({today_full})</b>.\n\n"
                f"⚠️ На сайте УКСиВТ пока нет расписания на этот день."
            )

        return render_day_block(today_data)

    text_blocks = []
    for day in parsed_data:
        text_blocks.append(render_day_block(day))

    return "\n\n➖➖➖➖➖➖➖➖➖➖\n\n".join(text_blocks)


def render_day_block(day_data):
    header = day_data.get("day_full", day_data.get("date", "Расписание"))
    lessons = day_data.get("lessons", [])

    lines = [f"📅 <b>{header}</b>\n"]

    if not lessons:
        lines.append("<i>Занятий нет</i>")
    else:
        for lesson in lessons:
            num = lesson.get("num", "")
            time = lesson.get("time", "")
            title = lesson.get("title", "")
            teacher = lesson.get("teacher", "")
            cabinet = lesson.get("cabinet", "")


            item_text = (
                f"{num}: 🕓 {time}, <b>{title}</b>\n"
                f"Кабинет: {cabinet}\n"
                f"Преподаватель: {teacher}"
            )
            lines.append(item_text)

    return "\n\n".join(lines)