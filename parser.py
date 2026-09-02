import re
import datetime
from typing import Dict, List, Any
import aiohttp
from bs4 import BeautifulSoup


class UksivtParser:
    def __init__(self, group_id: int = 49):
        self.group_id = group_id

    @property
    def base_url(self) -> str:
        return f"https://schedule.uksivt.ru/public?mode=group&id={self.group_id}"

    async def fetch_html(self) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self.base_url) as response:
                response.raise_for_status()
                return await response.text()

    def parse_current_week(self, soup: BeautifulSoup) -> str:
        """Определяет чётность недели из контейнера div.weeknow"""
        week_span = soup.select_one('div.weeknow span.badge.num')
        if week_span:
            text = week_span.get_text().strip().lower()
            if 'нечёт' in text:
                return 'odd'
            elif 'чёт' in text:
                return 'even'
        return 'unknown'

    def is_lesson_active(self, lesson_element, current_week: str) -> bool:
        """Фильтрация пар по чётности недели и заменам"""
        lesson_text = lesson_element.get_text().lower()

        if 'замена' in lesson_text:
            return True

        if 'нечёт' in lesson_text:
            return current_week == 'odd'

        if 'чёт' in lesson_text:
            return current_week == 'even'

        return True

    def parse_replacements(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Сбор официального блока замен над таблицей"""
        replacements = {}

        replacement_block = soup.find(
            lambda tag: tag.name in ["div", "section", "article", "td", "table"]
                        and "замен" in tag.text.lower()
        )

        if not replacement_block:
            return replacements

        items = replacement_block.find_all(["li", "p", "tr"])
        if not items:
            items = [replacement_block]

        for item in items:
            text = " ".join(item.get_text().split())
            match = re.search(r"(\d{2}\.\d{2})[,\s]+(\d+)[-я\s]*пара\s*—\s*(.+)", text, re.IGNORECASE)
            if match:
                date_str, pair_num, details = match.groups()
                key = f"{date_str}_{pair_num.strip()}"
                replacements[key] = details.strip()

        return replacements

    def clean_garbage_text(self, text: str) -> str:
        """Очистка системных мусорных фраз и тройных повторов верстки сайта"""
        text = re.sub(r"\d{2}:\d{2}[\s–—-]+\d{2}:\d{2}", "", text)

        text = re.sub(r"\d{1,2}\s+[а-яА-Я]+\s*—\s*замена", "", text, flags=re.IGNORECASE)
        text = re.sub(r"вместо\s*«[^»]*»\s*→\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"«[^»]*»\s*—\s*пары не будет", "пары не будет", text, flags=re.IGNORECASE)
        text = re.sub(r"\d{2}\.\d{2}(\.\d{2,4})?", "", text)
        text = re.sub(r"\bкаб\.?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[→·«»]", " ", text)
        text = re.sub(r"\b(нечёт|чёт)\b", "", text, flags=re.IGNORECASE)

        cleaned = " ".join(text.split()).strip(" ,.-")

        words = cleaned.split()
        if len(words) >= 2:
            if len(words) % 3 == 0:
                third = len(words) // 3
                if words[:third] == words[third:third * 2] == words[third * 2:]:
                    return " ".join(words[:third])

            if len(words) % 2 == 0:
                half = len(words) // 2
                if words[:half] == words[half:half * 2]:
                    return " ".join(words[:half])

        return cleaned

    def parse_single_entity(self, raw_text: str):
        """Извлечение названия, преподавателя и полного кабинета"""
        teacher = "Не указан"
        cabinet = "Не указан"

        if "пары не будет" in raw_text.lower():
            return "❌ Пары не будет", "—", "—"

        teacher_pattern = r"([А-Яа-яЁё\-]+\s+[А-Я]\.\s*[А-Я]\.|Резерв[_\-\w]*|Вакантно)"
        cabinet_pattern = r"(Общежитие[^\n·]*Читальный\s*зал|Читальный\s*зал|Общежитие[^\n·,]*|\b\d{3}[а-яА-Я]?\b|Учебный корпус[^\n·]*|Гимнаст[^\n·]*зал|Спорт[^\n·]*зал)"

        t_match = re.search(teacher_pattern, raw_text, re.IGNORECASE)
        if t_match:
            teacher = t_match.group(1).strip()
            raw_text = raw_text.replace(t_match.group(0), "")

        c_match = re.search(cabinet_pattern, raw_text, re.IGNORECASE)
        if c_match:
            cabinet = c_match.group(0).strip(" ,.-")
            raw_text = raw_text.replace(c_match.group(0), "")

        title = self.clean_garbage_text(raw_text)

        return title, teacher, cabinet

    async def parse_schedule(self) -> List[Dict[str, Any]]:
        html = await self.fetch_html()
        soup = BeautifulSoup(html, "lxml")

        current_week = self.parse_current_week(soup)
        replacements = self.parse_replacements(soup)

        table = soup.find("table")
        if not table:
            return []

        rows = table.find_all("tr")
        if not rows:
            return []

        header_row = rows[0]
        header_cols = header_row.find_all(["th", "td"])

        days_headers = []
        days_keywords = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

        now = datetime.datetime.now()
        monday = now - datetime.timedelta(days=now.weekday())
        week_dates = {}
        for i, d in enumerate(days_keywords):
            week_dates[d] = (monday + datetime.timedelta(days=i)).strftime("%d.%m")

        for idx, col in enumerate(header_cols):
            text = " ".join(col.get_text().split())
            for day_kw in days_keywords:
                if day_kw in text:
                    clean_day = re.sub(r"(другие звонки|звонки|расписание)", "", text, flags=re.IGNORECASE).strip()
                    days_headers.append((idx, clean_day))
                    break

        if not days_headers and len(header_cols) > 1:
            for idx in range(1, len(header_cols)):
                text = " ".join(header_cols[idx].get_text().split())
                if text:
                    days_headers.append((idx, text))

        if not days_headers:
            return []

        days_data = {h_text: [] for _, h_text in days_headers}

        for row in rows[1:]:
            cols = row.find_all(["td", "th"])
            if not cols:
                continue

            raw_first_col = " ".join(cols[0].get_text().split())
            if not raw_first_col:
                continue

            pair_match = re.search(r"\d", raw_first_col)
            if not pair_match:
                continue

            pair_num = pair_match.group(0)

            time_match = re.findall(r"\d{2}:\d{2}", raw_first_col)
            if len(time_match) >= 2:
                pair_time = f"{time_match[0]} - {time_match[1]}"
            else:
                pair_time = "Время не указано"

            for col_idx, day_name in days_headers:
                if col_idx < len(cols):
                    cell = cols[col_idx]

                    if not self.is_lesson_active(cell, current_week):
                        continue

                    cell_text = " ".join(cell.get_text().split())

                    if not cell_text or cell_text == "-" or cell_text == "—":
                        continue

                    date_match = re.search(r"\d{2}\.\d{2}", day_name) or re.search(r"\d{2}\.\d{2}", cell_text)
                    if date_match:
                        current_date = date_match.group(0)
                    else:
                        day_kw = next((d for d in days_keywords if d in day_name), None)
                        current_date = week_dates.get(day_kw, "")

                    # Сверяем со списком замен из шапки
                    global_replacement = None
                    if current_date:
                        replacement_key = f"{current_date}_{pair_num}"
                        global_replacement = replacements.get(replacement_key)

                    o_title, o_t, o_c = self.parse_single_entity(cell_text)

                    if global_replacement:
                        r_title, r_t, r_c = self.parse_single_entity(global_replacement)
                        clean_o = re.sub(r"[^\w\s]", "", o_title).strip().lower()
                        clean_r = re.sub(r"[^\w\s]", "", r_title).strip().lower()

                        if "пары не будет" in clean_r:
                            title = "🔄 <b>❌ Пары не будет</b>"
                            teacher = "—"
                            cabinet = "—"
                        elif clean_r != clean_o and clean_r != "":
                            if clean_r in clean_o:
                                title = f"🔄 <b>{r_title}</b>"
                            else:
                                title = f"<s>{o_title}</s> 🔄 <b>{r_title}</b>"
                            teacher = r_t if r_t != "Не указан" else o_t
                            cabinet = r_c if r_c != "Не указан" else o_c
                        else:
                            title, teacher, cabinet = o_title, o_t, o_c
                    else:
                        title, teacher, cabinet = o_title, o_t, o_c

                    days_data[day_name].append({
                        "num": pair_num,
                        "time": pair_time,
                        "title": title,
                        "teacher": teacher,
                        "cabinet": cabinet,
                        "lesson_date": current_date
                    })

        result = []
        for day_name, lessons in days_data.items():
            if lessons:
                clean_date = lessons[0].get("lesson_date", "")

                result.append({
                    "date": clean_date,
                    "day_full": day_name,
                    "lessons": lessons
                })

        return result