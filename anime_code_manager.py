import csv
import json
import random
import shutil
import sqlite3
import string
import tkinter as tk
import uuid
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "anime_codes.db"
MEDIA_DIR = APP_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)
DIGITS = string.digits


class AnimeCodeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Anime Publish Manager")
        self.root.geometry("1280x780")
        self.conn = sqlite3.connect(DB_PATH)
        self.checked_ids = set()
        self.create_tables()
        self.build_ui()
        self.refresh_table()

    # ---------- DB ----------
    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS anime_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                anime_title TEXT NOT NULL,
                note TEXT,
                image_path TEXT,
                video_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()
        self.ensure_column_exists("anime_codes", "image_path", "TEXT")
        self.ensure_column_exists("anime_codes", "video_path", "TEXT")

    def ensure_column_exists(self, table_name: str, column_name: str, column_type: str):
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cur.fetchall()}
        if column_name not in columns:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            self.conn.commit()

    # ---------- UI ----------
    def build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_add = ttk.Frame(notebook)
        self.tab_search = ttk.Frame(notebook)
        self.tab_bulk = ttk.Frame(notebook)
        self.tab_list = ttk.Frame(notebook)

        notebook.add(self.tab_add, text="Добавить")
        notebook.add(self.tab_search, text="Поиск")
        notebook.add(self.tab_bulk, text="Импорт / Экспорт")
        notebook.add(self.tab_list, text="База")

        self.build_add_tab()
        self.build_search_tab()
        self.build_bulk_tab()
        self.build_list_tab()

    def build_add_tab(self):
        frame = ttk.Frame(self.tab_add, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Название аниме:").grid(row=0, column=0, sticky="w", pady=6)
        self.title_entry = ttk.Entry(frame, width=76)
        self.title_entry.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Комментарий / сезон / серия:").grid(row=1, column=0, sticky="w", pady=6)
        self.note_entry = ttk.Entry(frame, width=76)
        self.note_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Картинка:").grid(row=2, column=0, sticky="w", pady=6)
        image_row = ttk.Frame(frame)
        image_row.grid(row=2, column=1, sticky="ew", pady=6)
        self.image_path_var = tk.StringVar(value="")
        ttk.Entry(image_row, textvariable=self.image_path_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(image_row, text="Выбрать", command=self.pick_image_for_add).pack(side="left", padx=8)
        ttk.Button(image_row, text="Очистить", command=lambda: self.image_path_var.set("")).pack(side="left")

        ttk.Label(frame, text="Видео:").grid(row=3, column=0, sticky="w", pady=6)
        video_row = ttk.Frame(frame)
        video_row.grid(row=3, column=1, sticky="ew", pady=6)
        self.video_path_var = tk.StringVar(value="")
        ttk.Entry(video_row, textvariable=self.video_path_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(video_row, text="Выбрать", command=self.pick_video_for_add).pack(side="left", padx=8)
        ttk.Button(video_row, text="Очистить", command=lambda: self.video_path_var.set("")).pack(side="left")

        ttk.Label(frame, text="Длина цифрового кода:").grid(row=4, column=0, sticky="w", pady=6)
        self.length_var = tk.IntVar(value=6)
        ttk.Spinbox(frame, from_=4, to=12, textvariable=self.length_var, width=8).grid(row=4, column=1, sticky="w", pady=6)

        btns = ttk.Frame(frame)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(btns, text="Сгенерировать и сохранить", command=self.add_single).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Очистить форму", command=self.clear_add_form).pack(side="left")

        ttk.Label(frame, text="Последний созданный код:").grid(row=6, column=0, sticky="w", pady=6)
        self.last_code_var = tk.StringVar(value="—")
        ttk.Entry(frame, textvariable=self.last_code_var, width=30, state="readonly").grid(row=6, column=1, sticky="w", pady=6)

        self.add_result = tk.Text(frame, height=12, wrap="word")
        self.add_result.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(7, weight=1)

    def build_search_tab(self):
        frame = ttk.Frame(self.tab_search, padding=16)
        frame.pack(fill="both", expand=True)

        search_row = ttk.Frame(frame)
        search_row.pack(fill="x", pady=(0, 10))

        ttk.Label(search_row, text="Код или название:").pack(side="left")
        self.search_entry = ttk.Entry(search_row, width=50)
        self.search_entry.pack(side="left", padx=8)
        ttk.Button(search_row, text="Найти", command=self.search_records).pack(side="left")

        self.search_result = tk.Text(frame, wrap="word")
        self.search_result.pack(fill="both", expand=True)

    def build_bulk_tab(self):
        frame = ttk.Frame(self.tab_bulk, padding=16)
        frame.pack(fill="both", expand=True)

        info = (
            "Импорт CSV: колонки code (необязательно), anime_title/title, note (необязательно), "
            "image_path (необязательно), video_path (необязательно).\n"
            "Экспорт делает ZIP-пакет для бота/автопостинга: JSON + media."
        )
        ttk.Label(frame, text=info, wraplength=1080).pack(anchor="w", pady=(0, 12))

        manual_box = ttk.LabelFrame(frame, text="Быстрое массовое добавление по строкам", padding=10)
        manual_box.pack(fill="both", expand=True)
        ttk.Label(manual_box, text="Каждая строка = одно название аниме. Коды будут только из цифр.").pack(anchor="w", pady=(0, 8))
        self.bulk_text = tk.Text(manual_box, height=12, wrap="word")
        self.bulk_text.pack(fill="both", expand=True)

        controls = ttk.Frame(manual_box)
        controls.pack(fill="x", pady=10)
        ttk.Label(controls, text="Длина кода:").pack(side="left")
        self.bulk_length_var = tk.IntVar(value=6)
        ttk.Spinbox(controls, from_=4, to=12, textvariable=self.bulk_length_var, width=8).pack(side="left", padx=(8, 16))
        ttk.Button(controls, text="Создать коды", command=self.bulk_add_from_lines).pack(side="left")

        file_box = ttk.LabelFrame(frame, text="Файлы", padding=10)
        file_box.pack(fill="x", pady=(14, 0))

        file_controls = ttk.Frame(file_box)
        file_controls.pack(fill="x")
        ttk.Button(file_controls, text="Импорт CSV", command=self.import_csv).pack(side="left")
        ttk.Button(file_controls, text="Импорт ZIP пакета", command=self.import_zip_package).pack(side="left", padx=8)
        ttk.Button(file_controls, text="Экспорт CSV", command=self.export_csv).pack(side="left")
        ttk.Button(file_controls, text="Экспорт ZIP для публикации", command=self.export_publish_zip).pack(side="left", padx=8)

        self.bulk_status_var = tk.StringVar(value="")
        ttk.Label(file_box, textvariable=self.bulk_status_var, wraplength=1080).pack(anchor="w", pady=(10, 0))

    def build_list_tab(self):
        frame = ttk.Frame(self.tab_list, padding=10)
        frame.pack(fill="both", expand=True)

        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Обновить", command=self.refresh_table).pack(side="left")
        ttk.Button(top, text="Выделить все", command=self.check_all_rows).pack(side="left", padx=8)
        ttk.Button(top, text="Снять выделение", command=self.uncheck_all_rows).pack(side="left")
        ttk.Button(top, text="Удалить отмеченные", command=self.delete_checked_rows).pack(side="left", padx=8)
        ttk.Button(top, text="Экспорт ZIP для публикации", command=self.export_publish_zip).pack(side="left")

        columns = ("select", "code", "anime_title", "note", "image_path", "video_path", "created_at")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("select", text="✓")
        self.tree.heading("code", text="Код")
        self.tree.heading("anime_title", text="Название")
        self.tree.heading("note", text="Комментарий")
        self.tree.heading("image_path", text="Картинка")
        self.tree.heading("video_path", text="Видео")
        self.tree.heading("created_at", text="Создан")

        self.tree.column("select", width=44, anchor="center")
        self.tree.column("code", width=90, anchor="center")
        self.tree.column("anime_title", width=250)
        self.tree.column("note", width=180)
        self.tree.column("image_path", width=210)
        self.tree.column("video_path", width=210)
        self.tree.column("created_at", width=165, anchor="center")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self.handle_tree_click)

    # ---------- Helpers ----------
    def generate_unique_code(self, length: int) -> str:
        cur = self.conn.cursor()
        while True:
            code = "".join(random.choices(DIGITS, k=length))
            cur.execute("SELECT 1 FROM anime_codes WHERE code = ?", (code,))
            if not cur.fetchone():
                return code

    def normalize_code(self, raw_code: str | None, fallback_length: int = 6) -> str:
        if raw_code:
            code = "".join(ch for ch in str(raw_code) if ch.isdigit())
            if code:
                cur = self.conn.cursor()
                cur.execute("SELECT 1 FROM anime_codes WHERE code = ?", (code,))
                if not cur.fetchone():
                    return code
        return self.generate_unique_code(fallback_length)

    def copy_media_file(self, source_path: str | None) -> str:
        if not source_path:
            return ""
        src = Path(source_path)
        if not src.exists() or not src.is_file():
            return ""
        new_name = f"{uuid.uuid4().hex}{src.suffix.lower()}"
        dst = MEDIA_DIR / new_name
        shutil.copy2(src, dst)
        return str(dst)

    def build_publish_text(self, title: str, code: str, note: str = "") -> str:
        parts = [title.strip(), f"Код: {code}"]
        if note.strip():
            parts.append(note.strip())
        return "\n".join(parts)

    def create_record(self, title: str, note: str = "", image_source_path: str = "", video_source_path: str = "", code: str | None = None, code_length: int = 6):
        title = title.strip()
        note = note.strip()
        if not title:
            return None
        final_code = self.normalize_code(code, code_length)
        stored_image = self.copy_media_file(image_source_path) if image_source_path else ""
        stored_video = self.copy_media_file(video_source_path) if video_source_path else ""

        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO anime_codes (code, anime_title, note, image_path, video_path) VALUES (?, ?, ?, ?, ?)",
            (final_code, title, note, stored_image, stored_video),
        )
        self.conn.commit()
        return final_code, stored_image, stored_video

    # ---------- Single add ----------
    def pick_image_for_add(self):
        path = filedialog.askopenfilename(
            title="Выбери картинку",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("All files", "*.*")],
        )
        if path:
            self.image_path_var.set(path)

    def pick_video_for_add(self):
        path = filedialog.askopenfilename(
            title="Выбери видео",
            filetypes=[("Videos", "*.mp4 *.mov *.avi *.mkv *.webm"), ("All files", "*.*")],
        )
        if path:
            self.video_path_var.set(path)

    def add_single(self):
        title = self.title_entry.get().strip()
        note = self.note_entry.get().strip()
        image_source = self.image_path_var.get().strip()
        video_source = self.video_path_var.get().strip()
        length = self.length_var.get()

        if not title:
            messagebox.showwarning("Пустое поле", "Введи название аниме.")
            return

        result = self.create_record(
            title=title,
            note=note,
            image_source_path=image_source,
            video_source_path=video_source,
            code_length=length,
        )
        if not result:
            messagebox.showwarning("Ошибка", "Не удалось добавить запись.")
            return

        code, stored_image, stored_video = result
        self.last_code_var.set(code)
        self.add_result.delete("1.0", tk.END)
        self.add_result.insert(
            tk.END,
            f"Запись создана успешно.\n\n"
            f"Код: {code}\n"
            f"Аниме: {title}\n"
            f"Комментарий: {note or '—'}\n"
            f"Картинка: {stored_image or '—'}\n"
            f"Видео: {stored_video or '—'}\n\n"
            f"Текст публикации:\n{self.build_publish_text(title, code, note)}"
        )
        self.refresh_table()

    def clear_add_form(self):
        self.title_entry.delete(0, tk.END)
        self.note_entry.delete(0, tk.END)
        self.image_path_var.set("")
        self.video_path_var.set("")
        self.last_code_var.set("—")
        self.add_result.delete("1.0", tk.END)

    # ---------- Bulk / import / export ----------
    def bulk_add_from_lines(self):
        lines = [line.strip() for line in self.bulk_text.get("1.0", tk.END).splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning("Пустой список", "Добавь хотя бы одно название.")
            return

        length = self.bulk_length_var.get()
        created = 0
        for title in lines:
            if self.create_record(title=title, code_length=length):
                created += 1

        self.bulk_status_var.set(f"Готово: создано {created} записей с цифровыми кодами.")
        self.refresh_table()

    def detect_csv_delimiter(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                sample = f.read(2048)
                return csv.Sniffer().sniff(sample, delimiters=';,\t,').delimiter
        except Exception:
            return ";"

    def import_csv(self):
        file_path = filedialog.askopenfilename(
            title="Импорт CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        created = 0
        with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=self.detect_csv_delimiter(file_path))
            for row in reader:
                title = (row.get("anime_title") or row.get("title") or "").strip()
                note = (row.get("note") or "").strip()
                image_path = (row.get("image_path") or "").strip()
                video_path = (row.get("video_path") or "").strip()
                code = (row.get("code") or "").strip()
                if title and self.create_record(
                    title=title,
                    note=note,
                    image_source_path=image_path,
                    video_source_path=video_path,
                    code=code,
                ):
                    created += 1

        self.bulk_status_var.set(f"Импорт CSV завершён. Добавлено записей: {created}.")
        self.refresh_table()

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Сохранить базу как CSV",
        )
        if not file_path:
            return

        cur = self.conn.cursor()
        cur.execute(
            "SELECT code, anime_title, note, image_path, video_path, created_at FROM anime_codes ORDER BY created_at DESC"
        )
        rows = cur.fetchall()

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["code", "anime_title", "note", "image_path", "video_path", "created_at"])
            writer.writerows(rows)

        self.bulk_status_var.set(f"CSV сохранён: {file_path}")
        messagebox.showinfo("Экспорт", f"CSV файл сохранён:\n{file_path}")

    def export_publish_zip(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
            title="Сохранить пакет для публикации",
        )
        if not file_path:
            return

        cur = self.conn.cursor()
        cur.execute(
            "SELECT code, anime_title, note, image_path, video_path, created_at FROM anime_codes ORDER BY created_at DESC"
        )
        rows = cur.fetchall()

        payload = []
        with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for index, (code, title, note, image_path, video_path, created_at) in enumerate(rows, start=1):
                item = {
                    "code": code,
                    "title": title,
                    "note": note,
                    "created_at": created_at,
                    "image": "",
                    "video": "",
                    "publish_text": self.build_publish_text(title, code, note),
                    "caption": self.build_publish_text(title, code, note),
                }

                if image_path:
                    img_path = Path(image_path)
                    if img_path.exists() and img_path.is_file():
                        arcname = f"media/{index:04d}_image{img_path.suffix.lower()}"
                        zf.write(img_path, arcname=arcname)
                        item["image"] = arcname

                if video_path:
                    vid_path = Path(video_path)
                    if vid_path.exists() and vid_path.is_file():
                        arcname = f"media/{index:04d}_video{vid_path.suffix.lower()}"
                        zf.write(vid_path, arcname=arcname)
                        item["video"] = arcname

                payload.append(item)

            manifest = {
                "version": 1,
                "format": "anime_publish_import",
                "items": payload,
            }
            manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
            zf.writestr("publish_import.json", manifest_json)
            zf.writestr("bot_import.json", manifest_json)
            zf.writestr(
                "README.txt",
                "Пакет для Telegram-бота / мульти-мессенджер бота.\n"
                "Главный файл: publish_import.json\n"
                "Внутри items[].\n"
                "Поля: code, title, note, image, video, publish_text, caption, created_at.\n"
                "Если есть video, бот может публиковать видео с caption. Если видео нет, но есть image — публикует картинку.\n"
                "Если нет медиа, публикует только текст из publish_text.\n",
            )

        self.bulk_status_var.set(f"ZIP-пакет для публикации сохранён: {file_path}")
        messagebox.showinfo("Экспорт", f"ZIP пакет сохранён:\n{file_path}")

    def import_zip_package(self):
        file_path = filedialog.askopenfilename(
            title="Импорт ZIP пакета",
            filetypes=[("ZIP files", "*.zip")],
        )
        if not file_path:
            return

        created = 0
        with zipfile.ZipFile(file_path, "r") as zf:
            manifest_name = None
            for candidate in ("publish_import.json", "bot_import.json"):
                if candidate in zf.namelist():
                    manifest_name = candidate
                    break
            if not manifest_name:
                messagebox.showerror("Ошибка", "В архиве нет publish_import.json или bot_import.json")
                return

            manifest = json.loads(zf.read(manifest_name).decode("utf-8"))
            items = manifest.get("items", manifest if isinstance(manifest, list) else [])
            temp_dir = APP_DIR / "_import_temp"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)

            try:
                for item in items:
                    image_src = ""
                    video_src = ""

                    image_name = item.get("image") or ""
                    if image_name and image_name in zf.namelist():
                        extracted = temp_dir / Path(image_name).name
                        with zf.open(image_name) as src, open(extracted, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        image_src = str(extracted)

                    video_name = item.get("video") or ""
                    if video_name and video_name in zf.namelist():
                        extracted = temp_dir / Path(video_name).name
                        with zf.open(video_name) as src, open(extracted, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        video_src = str(extracted)

                    if self.create_record(
                        title=item.get("title", ""),
                        note=item.get("note", ""),
                        image_source_path=image_src,
                        video_source_path=video_src,
                        code=item.get("code", ""),
                    ):
                        created += 1
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        self.bulk_status_var.set(f"Импорт ZIP завершён. Добавлено записей: {created}.")
        self.refresh_table()

    # ---------- Search ----------
    def search_records(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showinfo("Поиск", "Введи код или название.")
            return

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT code, anime_title, note, image_path, video_path, created_at
            FROM anime_codes
            WHERE code = ? OR anime_title LIKE ?
            ORDER BY created_at DESC
            """,
            ("".join(ch for ch in query if ch.isdigit()), f"%{query}%"),
        )
        rows = cur.fetchall()

        self.search_result.delete("1.0", tk.END)
        if not rows:
            self.search_result.insert(tk.END, "Ничего не найдено.")
            return

        for code, title, note, image_path, video_path, created_at in rows:
            self.search_result.insert(
                tk.END,
                f"Код: {code}\n"
                f"Аниме: {title}\n"
                f"Комментарий: {note or '—'}\n"
                f"Картинка: {image_path or '—'}\n"
                f"Видео: {video_path or '—'}\n"
                f"Текст публикации: {self.build_publish_text(title, code, note)}\n"
                f"Создан: {created_at}\n\n",
            )

    # ---------- Table / checkboxes ----------
    def handle_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if column == "#1" and row_id:
            if row_id in self.checked_ids:
                self.checked_ids.remove(row_id)
            else:
                self.checked_ids.add(row_id)
            self.update_row_checkbox(row_id)
            return "break"

    def update_row_checkbox(self, row_id: str):
        values = list(self.tree.item(row_id, "values"))
        if not values:
            return
        values[0] = "☑" if row_id in self.checked_ids else "☐"
        self.tree.item(row_id, values=values)

    def check_all_rows(self):
        for row_id in self.tree.get_children():
            self.checked_ids.add(row_id)
            self.update_row_checkbox(row_id)

    def uncheck_all_rows(self):
        self.checked_ids.clear()
        for row_id in self.tree.get_children():
            self.update_row_checkbox(row_id)

    def delete_checked_rows(self):
        if not self.checked_ids:
            messagebox.showinfo("Удаление", "Сначала поставь галочки у записей.")
            return

        if not messagebox.askyesno("Подтверждение", f"Удалить отмеченные записи: {len(self.checked_ids)} шт.?"):
            return

        cur = self.conn.cursor()
        for item_id in list(self.checked_ids):
            cur.execute("SELECT image_path, video_path FROM anime_codes WHERE id = ?", (int(item_id),))
            row = cur.fetchone()
            if row:
                for media_path in row:
                    if media_path:
                        p = Path(media_path)
                        if p.exists() and p.is_file():
                            try:
                                p.unlink()
                            except Exception:
                                pass
            cur.execute("DELETE FROM anime_codes WHERE id = ?", (int(item_id),))
        self.conn.commit()
        self.checked_ids.clear()
        self.refresh_table()

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, code, anime_title, note, image_path, video_path, created_at FROM anime_codes ORDER BY created_at DESC, id DESC"
        )
        rows = cur.fetchall()
        existing_ids = set()
        for record_id, code, title, note, image_path, video_path, created_at in rows:
            item_id = str(record_id)
            existing_ids.add(item_id)
            checked = "☑" if item_id in self.checked_ids else "☐"
            short_img = Path(image_path).name if image_path else ""
            short_vid = Path(video_path).name if video_path else ""
            self.tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(checked, code, title, note, short_img, short_vid, created_at),
            )
        self.checked_ids &= existing_ids

    # ---------- Close ----------
    def on_close(self):
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AnimeCodeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
