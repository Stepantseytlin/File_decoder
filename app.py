from modules.File_parser import ONE_FILE
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import os
import pandas as pd
from modules.LRU import LRU_CASH, Cash_Object
class ProtocolDecoderApp:
    def __init__(self, root : tk.Tk):
        self.CASH = LRU_CASH(5)
        self.root : tk.Tk = root
        self.root.title("Protocol Decoder")
        self.root.geometry(newGeometry = "900x800-2500-300")
        self.display_buffer =[]
        self.export_dict :dict= {}
        self.export_dict["date"] = []
        self.export_dict["parameter"] = []
        self.export_dict["value"] = []
        self.to_excel = pd.DataFrame(columns=["date","parameter","value"])
        self.protocol_path = ""
        self.binary_path = ""
        self.frames = []
        self.frames_headers :list[ttk.Treeview] = []
        self.export_par_names = False
        self.create_widgets()
        self.THREADING = False
    def create_widgets(self):
        # Выбор файлов
        tk.Button(self.root, text="Выбрать протокол ", command=self.load_protocol).pack(pady=5)
        self.protocol_label = tk.Label(self.root, text="Протокол не выбран")
        self.protocol_label.pack()

        tk.Button(self.root, text="Выбрать бинарный файл", command=self.load_binary).pack(pady=5)
        self.binary_label = tk.Label(self.root, text="Файл не выбран")
        self.binary_label.pack()

        dec_bt = tk.Button(self.root, text="Декодировать", command=self.initiate_parallel_decode)
        dec_bt.place(anchor="s")
        dec_bt.pack(pady=10)
        # Список фреймов
        self.tree_frame = tk.Frame(self.root,width= 500, height=200)
        self.tree_frame.pack_propagate(False)
        self.tree_frame.pack()
        
        self.tree_of_frames = ttk.Treeview(self.tree_frame)
        self.frames_branch_id= self.tree_of_frames.insert('','end',text = 'Фреймы')
        self.frames_branch = ttk.Treeview(self.tree_of_frames)
        self.tree_of_frames.pack(fill="both",expand=True)
        self.tree_of_frames.bind("<<TreeviewSelect>>", self.show_frame_details)

        # Подробности
        self.text_box = tk.Text(self.root, width=180, height=20)
        self.text_box.pack(pady=5)

        
        sh_all_btn = tk.Button(self.root, text = "Показать всё", command= self.thread_display)
        sh_all_btn.place(rely = 0.9,relx =0.5,anchor='center')#(rely = 0.172,relx =0.4,anchor="center")        
        #sh_all_btn.pack(padx=5, side = "top")
        # Экспорт
        export_btn = tk.Button(self.root, text="Экспорт в Excel", command=self.export_to_excel)
        export_btn.place(rely = 0.95,relx =0.5,anchor='center')
        #export_btn.pack(pady=10)
    def append_to_textbox(self,text):
        self.text_box.insert(tk.END,text)
        #self.text_box.see(tk.END)
    def display_all_after(self):
        self.export_dict["date"] = []
        self.export_dict["parameter"] = []
        self.export_dict["value"] = []
        self.text_box.delete(1.0, tk.END)
        for i, frame in enumerate(self.frames):
            text_to_append = ''
            text_to_append += f"Фрейм {i+1}\n"
            #self.root.after(0,self.append_to_textbox, f"Фрейм {i+1}\n")
            for line in (frame.display_decoded()).split("\n"):
                text_to_append+= f"{line}\n" #self.text_box.insert(tk.END, )
                try:
                    #self.to_excel.loc[(len(self.to_excel),["date"])],self.to_excel.loc[(len(self.to_excel)-1,["parameter"])], self.to_excel.loc[(len(self.to_excel)-1,["value"])] = ' '.join(line.split(" ")[:2]), line.split(" ")[-3], line.split(" ")[-2]
                    self.export_dict["date"].append(' '.join(line.split(" ")[:2]))
                    self.export_dict["parameter"].append(line.split(" ")[-3])
                    self.export_dict["value"].append(line.split(" ")[-2])
                except:
                    self.export_dict["date"].pop()
            self.root.after(0,self.append_to_textbox, text_to_append)
        self.export_par_names = True
    def thread_display(self):
        if self.THREADING == False:
            self.display_all()
        else: 
            self.disp_thread = threading.Thread(target=self.display_all_after,daemon=True)
            self.disp_thread.start()
    def load_protocol(self):
        path = filedialog.askopenfilename(filetypes=[("all files", "*.txt")])
        if path:
            self.protocol_path = path
            self.protocol_label.config(text=f"Протокол: {os.path.basename(path)}")

    def load_binary(self):
        path = filedialog.askopenfilename(filetypes=[("all files", "*.txt"), ("All files", "*.txt*")])
        if path:
            if path != self.binary_path:
                self.CASH.all_objects = {}
            self.binary_path = path
            self.binary_label.config(text=f"Файл: {os.path.basename(path)}")
    def read_file(self):
        self.frames = self.parser.read_file() 
        self.root.after(0,self.process_decoded)
    def initiate_parallel_decode(self):
        if not self.protocol_path or not self.binary_path:
            messagebox.showerror("Ошибка", "Укажите оба файла")
            return
        #try:
        self.parser= ONE_FILE(self.binary_path)
        self.parser.read_parameters(self.protocol_path)
        self.parser_thread = threading.Thread(target = self.read_file, daemon=True)
        self.parser_thread.start()
        messagebox.showinfo("Подождите", f"Идет расшифровка.")
        #self.frames = self.parser.read_file() 
        #     if len(self.frames)>500: 
        #         self.THREADING = True
        #     else:
        #         self.THREADING = False
        #     for item in self.frames_branch.get_children():
        #         self.frames_branch.delete(item)
        #     for i, frame in enumerate(self.frames):
        #         frame_id = self.tree_of_frames.insert(self.frames_branch_id,'end', text = f"Фрейм {i+1}:")
        #         for line in (frame.display_decoded()).split("\n"):
        #             self.tree_of_frames.insert(frame_id,'end', text =f"{line}")
        #     messagebox.showinfo("Готово", f"Декодировано {self.parser.n_frames} фреймов.")
        # except Exception as e:
        #     messagebox.showerror("Ошибка при декодировании", str(e))
    def process_decoded(self):
        try:
            if len(self.frames)>500: 
                self.THREADING = True
            else:
                self.THREADING = False
            for item in self.tree_of_frames.get_children(item=self.frames_branch_id):
                self.tree_of_frames.delete(item)
            for i, frame in enumerate(self.frames):
                frame_id = self.tree_of_frames.insert(self.frames_branch_id,'end', text = f"Фрейм {i+1}:")
                for line in (frame.display_decoded()).split("\n"):
                    self.tree_of_frames.insert(frame_id,'end', text =f"{line}")
            messagebox.showinfo("Готово", f"Декодировано {self.parser.n_frames} фреймов.")
        except Exception as e:
            messagebox.showerror("Ошибка при декодировании", str(e))
    def display_details_thread(self,data : list):
        for par_data, value in data:
                    append = str(par_data) + ' ' + str(value) + '\n'
                    self.to_excel.loc[(len(self.to_excel),["date"])], self.to_excel.loc[(len(self.to_excel)-1,["value"])] = par_data, value
                    self.root.after(0, self.append_to_textbox, append)
        self.root.after(0, self.append_to_textbox, "from CASH")
    def show_frame_details(self, event):
        selection = self.tree_of_frames.selection()
        if not selection:
            return

        idx = (int(selection[0].split("I")[-1].encode(),16)-3)%(self.parser.num_parameters+2)
        #frame = self.frames[idx]
        if idx >-1 and int(selection[0].split("I")[-1].encode(),16)-3>=0 and -1<(int(selection[0].split("I")[-1].encode(),16)-3)%(self.parser.num_parameters+2)<self.parser.num_parameters:#(int(selection[0].split("I")[-1].encode(),16)%(self.parser.num_parameters+4)!=0):
            self.to_excel = pd.DataFrame(columns=["date","parameter","value"])
            self.text_box.delete(1.0, tk.END)
            cash_obj = self.CASH.get(self.parser.FRAME_TEMPLATE.names[idx])
            if cash_obj.value is not None:
                 thread_display_details = threading.Thread(target=self.display_details_thread,args = (cash_obj.value,),daemon = True)
                 thread_display_details.start()
            else: 
                thread_parse_parameters_info = threading.Thread(target = self.parse_parameters_thread, args = (idx, cash_obj), daemon = True)
                thread_parse_parameters_info.start()
    def parse_parameters_thread(self, idx : int, cash_obj : Cash_Object):
        cash_obj.value = []
        for par_data, value in self.parser.get_param_information(self.parser.FRAME_TEMPLATE.names[idx]):
                    text =  str(par_data) + ' ' + str(value) + '\n'
                    cash_obj.value.append((par_data,value))
                    self.to_excel.loc[(len(self.to_excel),["date"])], self.to_excel.loc[(len(self.to_excel)-1,["value"])] = par_data, value
                    self.root.after(0,self.append_to_textbox,text)
    def display_all(self):
        self.export_dict["date"] = []
        self.export_dict["parameter"] = []
        self.export_dict["value"] = []
        self.text_box.delete(1.0, tk.END)
        
        for i, frame in enumerate(self.frames):
            self.text_box.insert(tk.END, f"Фрейм {i+1}\n")
            for line in (frame.display_decoded()).split("\n"):
                self.text_box.insert(tk.END, f"{line}\n")
                try:
                    #self.to_excel.loc[(len(self.to_excel),["date"])],self.to_excel.loc[(len(self.to_excel)-1,["parameter"])], self.to_excel.loc[(len(self.to_excel)-1,["value"])] = ' '.join(line.split(" ")[:2]), line.split(" ")[-3], line.split(" ")[-2]
                    self.export_dict["date"].append(' '.join(line.split(" ")[:2]))
                    self.export_dict["parameter"].append(line.split(" ")[-3])
                    self.export_dict["value"].append(line.split(" ")[-2])
                except:
                    self.export_dict["date"].pop()
        self.export_par_names = True
    def export_to_excel(self, par_name = False):
        if not self.frames:
            messagebox.showerror("Ошибка", "Нет фреймов для экспорта.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 filetypes=[("Excel files", "*.xlsx")])
        if not save_path:
            return

        try:
            # data = []
            # for frame in self.frames:
            #     row = {"Offset": frame.offset}
            #     row.update(frame.decoded)  # frame.decoded — словарь с параметрами
            #     data.append(row)

            #df = pd.DataFrame(data)
            self.to_excel = pd.DataFrame(self.export_dict)
            keys = ["date", "value"]
            if self.export_par_names: keys =["date","parameter","value"]
            self.to_excel[keys].to_excel(save_path, index=False)

            messagebox.showinfo("Успех", f"Экспортировано в {save_path}")
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    
    app = ProtocolDecoderApp(root)
    root.mainloop()

