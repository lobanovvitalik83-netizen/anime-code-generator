import csv
import random
import sqlite3
import string
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

DB_PATH = Path(__file__).with_name("anime_codes.db")
ALPHABET = string.ascii_uppercase + string.digits


class AnimeCodeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Anime Code Manager")
        self.root.geometry("980x680")
        self.conn = sqlite3.connect(DB_PATH)
        self.create_tables()
        self.build_ui()
        self.refresh_table()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS anime_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                anime_title TEXT NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_add = ttk.Frame(notebook)
        self.tab_search = ttk.Frame(notebook)
        self.tab_bulk = ttk.Frame(notebook)
        self.tab_list = ttk.Frame(notebook)

        notebook.add(self.tab_add, text="Добавить")
        notebook.add(self.tab_search, text="Поиск")
        notebook.add(self.tab_bulk, text="Массовое добавление")
        notebook.add(self.tab_list, text="База")

        self.build_add_tab()
        self.build_search_tab()
        self.build_bulk_tab()
        self.build_list_tab()

    def build_add_tab(self):
        frame = ttk.Frame(self.tab_add, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Название аниме:").grid(row=0, column=0, sticky="w", pady=6)
        self.title_entry = ttk.Entry(frame, width=60)
        self.title_entry.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Комментарий / сезон / серия:").grid(row=1, column=0, sticky="w", pady=6)
        self.note_entry = ttk.Entry(frame, width=60)
        self.note_entry.grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Длина кода:").grid(row=2, column=0, sticky="w", pady=6)
        self.length_var = tk.IntVar(value=6)
        ttk.Spinbox(frame, from_=4, to=12, textvariable=self.length_var, width=8).grid(row=2, column=1, sticky="w", pady=6)

        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="w", pady=12)
        ttk.Button(btns, text="Сгенерировать и сохранить", command=self.add_single).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Очистить", command=self.clear_add_form).pack(side="left")

        ttk.Label(frame, text="Последний созданный код:").grid(row=4, column=0, sticky="w", pady=6)
        self.last_code_var = tk.StringVar(value="—")
        ttk.Entry(frame, textvariable=self.last_code_var, width=30, state="readonly").grid(row=4, column=1, sticky="w", pady=6)

        self.add_result = tk.Text(frame, height=10, wrap="word")
        self.add_result.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

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

        ttk.Label(
            frame,
            text="Вставь список названий. Каждое аниме — с новой строки. Для каждой строки будет создан уникальный код.",
            wraplength=800,
        ).pack(anchor="w", pady=(0, 10))

        self.bulk_text = tk.Text(frame, height=18, wrap="word")
        self.bulk_text.pack(fill="both", expand=True)

        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=10)

        ttk.Label(controls, text="Длина кода:").pack(side="left")
        self.bulk_length_var = tk.IntVar(value=6)
        ttk.Spinbox(controls, from_=4, to=12, textvariable=self.bulk_length_var, width=8).pack(side="left", padx=(8, 16))
        ttk.Button(controls, text="Создать коды", command=self.bulk_add).pack(side="left")
        ttk.Button(controls, text="Экспорт CSV", command=self.export_csv).pack(side="left", padx=8)

        self.bulk_status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.bulk_status_var).pack(anchor="w")

    def build_list_tab(self):
        frame = ttk.Frame(self.tab_list, padding=10)
        frame.pack(fill="both", expand=True)

        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="Обновить", command=self.refresh_table).pack(side="left")
        ttk.Button(top, text="Удалить выбранное", command=self.delete_selected).pack(side="left", padx=8)
        ttk.Button(top, text="Экспорт CSV", command=self.export_csv).pack(side="left")

        columns = ("code", "anime_title", "note", "created_at")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("code", text="Код")
        self.tree.heading("anime_title", text="Название")
        self.tree.heading("note", text="Комментарий")
        self.tree.heading("created_at", text="Создан")

        self.tree.column("code", width=120, anchor="center")
        self.tree.column("anime_title", width=300)
        self.tree.column("note", width=280)
        self.tree.column("created_at", width=180, anchor="center")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def generate_unique_code(self, length: int) -> str:
        cur = self.conn.cursor()
        while True:
            code = "".join(random.choices(ALPHABET, k=length))
            cur.execute("SELECT 1 FROM anime_codes WHERE code = ?", (code,))
            if not cur.fetchone():
                return code

    def add_single(self):
        title = self.title_entry.get().strip()
        note = self.note_entry.get().strip()
        length = self.length_var.get()

        if not title:
            messagebox.showwarning("Пустое поле", "Введи название аниме.")
            return

        code = self.generate_unique_code(length)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO anime_codes (code, anime_title, note) VALUES (?, ?, ?)",
            (code, title, note),
        )
        self.conn.commit()

        self.last_code_var.set(code)
        self.add_result.delete("1.0", tk.END)
        self.add_result.insert(
            tk.END,
            f"Код создан успешно.\n\nКод: {code}\nАниме: {title}\nКомментарий: {note or '—'}",
        )
        self.refresh_table()

    def bulk_add(self):
        lines = [line.strip() for line in self.bulk_text.get("1.0", tk.END).splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning("Пустой список", "Добавь хотя бы одно название.")
            return

        length = self.bulk_length_var.get()
        cur = self.conn.cursor()
        created = 0

        for title in lines:
            code = self.generate_unique_code(length)
            cur.execute(
                "INSERT INTO anime_codes (code, anime_title, note) VALUES (?, ?, ?)",
                (code, title, ""),
            )
            created += 1

        self.conn.commit()
        self.bulk_status_var.set(f"Готово: создано {created} кодов без повторений.")
        self.refresh_table()

    def search_records(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showinfo("Поиск", "Введи код или название.")
            return

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT code, anime_title, note, created_at
            FROM anime_codes
            WHERE code = ? OR anime_title LIKE ?
            ORDER BY created_at DESC
            """,
            (query.upper(), f"%{query}%"),
        )
        rows = cur.fetchall()

        self.search_result.delete("1.0", tk.END)
        if not rows:
            self.search_result.insert(tk.END, "Ничего не найдено.")
            return

        for code, title, note, created_at in rows:
            self.search_result.insert(
                tk.END,
                f"Код: {code}\nАниме: {title}\nКомментарий: {note or '—'}\nСоздан: {created_at}\n\n",
            )

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, code, anime_title, note, created_at FROM anime_codes ORDER BY created_at DESC"
        )
        for record_id, code, title, note, created_at in cur.fetchall():
            self.tree.insert("", tk.END, iid=str(record_id), values=(code, title, note, created_at))

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Удаление", "Выбери запись в таблице.")
            return

        if not messagebox.askyesno("Подтверждение", "Удалить выбранные записи?"):
            return

        cur = self.conn.cursor()
        for item_id in selected:
            cur.execute("DELETE FROM anime_codes WHERE id = ?", (int(item_id),))
        self.conn.commit()
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
        cur.execute("SELECT code, anime_title, note, created_at FROM anime_codes ORDER BY created_at DESC")
        rows = cur.fetchall()

        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["code", "anime_title", "note", "created_at"])
            writer.writerows(rows)

        messagebox.showinfo("Экспорт", f"Файл сохранён:\n{file_path}")

    def clear_add_form(self):
        self.title_entry.delete(0, tk.END)
        self.note_entry.delete(0, tk.END)
        self.last_code_var.set("—")
        self.add_result.delete("1.0", tk.END)

    def on_close(self):
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = AnimeCodeApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
