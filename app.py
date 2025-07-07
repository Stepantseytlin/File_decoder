from modules.File_parser import ONE_FILE
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import pandas as pd
class ProtocolDecoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Protocol Decoder")

        self.protocol_path = ""
        self.binary_path = ""
        self.frames = []

        self.create_widgets()

    def create_widgets(self):
        # Выбор файлов
        tk.Button(self.root, text="Выбрать протокол ", command=self.load_protocol).pack(pady=5)
        self.protocol_label = tk.Label(self.root, text="Протокол не выбран")
        self.protocol_label.pack()

        tk.Button(self.root, text="Выбрать бинарный файл", command=self.load_binary).pack(pady=5)
        self.binary_label = tk.Label(self.root, text="Файл не выбран")
        self.binary_label.pack()

        tk.Button(self.root, text="Декодировать", command=self.decode).pack(pady=10)

        # Список фреймов
        self.frame_listbox = tk.Listbox(self.root, width=50)
        
        self.frame_listbox.pack(pady=5)
        self.frame_listbox.bind("<<ListboxSelect>>", self.show_frame_details)

        # Подробности
        self.text_box = tk.Text(self.root, width=80, height=20)
        self.text_box.pack(pady=5)

        # Экспорт
        tk.Button(self.root, text="Экспорт в Excel", command=self.export_to_excel).pack(pady=10)

    def load_protocol(self):
        path = filedialog.askopenfilename(filetypes=[("all files", "*.txt")])
        if path:
            self.protocol_path = path
            self.protocol_label.config(text=f"Протокол: {os.path.basename(path)}")

    def load_binary(self):
        path = filedialog.askopenfilename(filetypes=[("Binary files", "*.all"), ("All files", "*.*")])
        if path:
            self.binary_path = path
            self.binary_label.config(text=f"Файл: {os.path.basename(path)}")

    def decode(self):
        if not self.protocol_path or not self.binary_path:
            messagebox.showerror("Ошибка", "Укажите оба файла")
            return
        try:
            self.parser= ONE_FILE(self.binary_path)
            self.parser.read_parameters(self.protocol_path)
            self.frames = self.parser.read_file() 
            self.frame_listbox.delete(0, tk.END)
            for i, frame in enumerate(self.frames):
                self.frame_listbox.insert(tk.END, f"Фрейм {i+1}:")
                for line in (frame.display_decoded()).split("\n"):
                    self.frame_listbox.insert(tk.END, f"{line}")

            messagebox.showinfo("Готово", f"Декодировано {self.parser.n_frames} фреймов.")
        except Exception as e:
            messagebox.showerror("Ошибка при декодировании", str(e))

    def show_frame_details(self, event):
        selection = self.frame_listbox.curselection()
        if not selection:
            return

        idx = selection[0]%(self.parser.num_parameters+2)-1
        #frame = self.frames[idx]
        if idx >-1 and (selection[0]%(self.parser.num_parameters+2)!=0):
            self.text_box.delete(1.0, tk.END)
            self.text_box.insert(tk.END, self.parser.get_param_information(self.parser.FRAME_TEMPLATE.names[idx]))

    def export_to_excel(self):
        if not self.frames:
            messagebox.showerror("Ошибка", "Нет фреймов для экспорта.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 filetypes=[("Excel files", "*.xlsx")])
        if not save_path:
            return

        try:
            data = []
            for frame in self.frames:
                row = {"Offset": frame.offset}
                row.update(frame.decoded)  # frame.decoded — словарь с параметрами
                data.append(row)

            df = pd.DataFrame(data)
            df.to_excel(save_path, index=False)

            messagebox.showinfo("Успех", f"Экспортировано в {save_path}")
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = ProtocolDecoderApp(root)
    root.mainloop()

