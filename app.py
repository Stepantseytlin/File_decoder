from modules.File_parser import ONE_FILE
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import os
import time
import pandas as pd
from modules.Rules import RULES
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
        self.collisions = True
        self.thread_display_details = threading.Thread(target=self.display_details_thread,daemon = True)
        self.thread_parse_parameters_info = threading.Thread(target = self.parse_parameters_thread, daemon = True)
        self.die_text_box_thread =threading.Event()
    def create_widgets(self):
        # Выбор файлов
        tk.Button(self.root, text="Выбрать протокол шифрования", command=self.load_protocol).pack(pady=5,padx=4)
        self.protocol_label = tk.Label(self.root, text="Протокол не выбран")
        self.protocol_label.pack()

        tk.Button(self.root, text="Выбрать файл для расшифровки", command=self.load_binary).pack(pady=5)
        self.binary_label = tk.Label(self.root, text="Файл не выбран")
        self.binary_label.pack()

        dec_bt = tk.Button(self.root, text="Декодировать", command=self.initiate_parallel_decode)
        dec_bt.place(anchor="s")
        dec_bt.pack(pady=10)
        # Список фреймов
        self.tree_frame = tk.Frame(self.root,width= 500, height=200)
        self.tree_frame.pack_propagate(False)
        self.tree_frame.pack()
        scrollbar = tk.Scrollbar(self.tree_frame)
        scrollbar.pack(side = "right",fill = "y")
        self.tree_of_frames = ttk.Treeview(self.tree_frame,yscrollcommand=scrollbar.set)
        self.frames_branch_id= self.tree_of_frames.insert('','end',text = 'Фреймы')
        self.frames_branch = ttk.Treeview(self.tree_of_frames)
        self.tree_of_frames.pack(fill="both",expand=True)
        self.tree_of_frames.bind("<<TreeviewSelect>>", self.show_frame_details)
        scrollbar.config(command=self.tree_of_frames.yview)
        
        # Подробности
        self.addition = tk.Frame(self.root,width= 700, height=300)
        self.addition.pack_propagate(False)
        self.addition.pack(pady= 10)
        scrollbar1 = tk.Scrollbar(self.addition)
        scrollbar1.pack(side = "right", fill = 'y')
        self.text_box = tk.Text(self.addition, width=180, height=20,yscrollcommand=scrollbar1.set)
        self.text_box.config(state = "disabled")
        self.text_box.pack(pady=5)
        scrollbar1.config(command=self.text_box.yview)
        
        sh_all_btn = tk.Button(self.root, text = "Показать всё", command= self.thread_display)
        sh_all_btn.place(rely = 0.9,relx =0.5,anchor='center')#(rely = 0.172,relx =0.4,anchor="center")        
        #sh_all_btn.pack(padx=5, side = "top")
        # Экспорт
        export_btn = tk.Button(self.root, text="Экспорт в Excel", command=self.export_to_excel)
        export_btn.place(rely = 0.95,relx =0.5,anchor='center')
        #export_btn.pack(pady=10)
        tk.Label(self.root,text="Разрешить коллизии").place(rely = 0.17,relx =0.63, anchor="w")
        #tk.Button(self.root,text="Показать протокол",command=self.show_protocol).place(rely = 0.022,relx =0.603, anchor="w")
        
        self.disable_collisions =tk.BooleanVar()
        tk.Checkbutton(self.root,variable=self.disable_collisions).place(rely=0.17,relx=0.61,anchor="center")
        
    def show_protocol(self):
        protocol_window = tk.Toplevel(self.root)
        
        
    def append_to_textbox(self,text):
        self.text_box.config(state = "normal")
        self.text_box.insert(tk.END,text)
        self.text_box.config(state = "disabled")
        #self.text_box.see(tk.END)
    def display_all_after(self):
        self.export_dict["date"] = []
        self.export_dict["parameter"] = []
        self.export_dict["value"] = []
        self.text_box.config(state = "normal")
        self.text_box.delete(1.0, tk.END)
        self.text_box.config(state = "disabled")
        for i, frame in enumerate(self.frames):
            if self.die_text_box_thread.is_set():
                self.die_text_box_thread.clear()
                break
            text_to_append = ''
            text_to_append += f"Фрейм {i+1}\n"
            #self.root.after(0,self.append_to_textbox, f"Фрейм {i+1}\n")
            for line in (frame.display_decoded()).split("\n"):
                if self.die_text_box_thread.is_set():
                    break
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
        self.die_text_box_thread.clear()
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
            try:
                RULES(path).read_protocol()
            except:
                messagebox.showerror("Ошибка", "Проверьте формат файла протокола")
    def load_binary(self):
        path = filedialog.askopenfilename(filetypes=[("all files", "*.txt"), ("All files", "*.txt*")])
        if path:
            if path != self.binary_path:
                self.CASH.clear()
            self.binary_path = path
            self.binary_label.config(text=f"Файл: {os.path.basename(path)}")
    def read_file(self):
        if not self.disable_collisions.get() != self.collisions:  self.CASH.clear()
        self.collisions = not self.disable_collisions.get()
        self.frames = self.parser.read_file(disable_collisions = self.collisions) 
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
            all_errors = list(self.parser.ERRORS_dict.values())
            unique_errors = list(set(list(self.parser.ERRORS_dict.values())))
            amount_of_each_error = [list(self.parser.ERRORS_dict.values()).count(er) for er in list(set(list(self.parser.ERRORS_dict.values())))]
            text = "\n".join([f"     ошибка {a} встречена {b} раз" for a, b in zip(unique_errors,amount_of_each_error)]) if unique_errors else ''
            messagebox.showinfo("Готово", f"Декодировано {self.parser.n_frames} фреймов. В файле {len(all_errors)} ошибок :\n"+text)
        except Exception as e:
            messagebox.showerror("Ошибка при декодировании", str(e))
    def display_details_thread(self,data : list):
        need_delete = False
        while self.die_text_box_thread.is_set(): 
            need_delete = True
            self.text_box.config(state = "normal")
            self.text_box.delete(1.0, tk.END)
            self.text_box.config(state = "disabled")
            pass
        if need_delete :
            self.to_excel = pd.DataFrame(columns=["date","parameter","value"])
            self.text_box.config(state = "normal")
            self.text_box.delete(1.0, tk.END)
            self.text_box.config(state = "disabled")
        self.text_box.config(state = "normal")
        self.text_box.delete(1.0, tk.END)
        self.text_box.config(state = "disabled")
        for par_data, value in data:
                    if self.die_text_box_thread.is_set():
                        try:
                            self.root.after_cancel(id)
                        except:
                            pass
                        # try:
                        #     #self.root.after_cancel(id2)
                        # except:
                        #     pass
                        self.text_box.config(state = "normal")
                        self.text_box.delete(1.0, tk.END)
                        self.text_box.config(state = "disabled")
                        self.die_text_box_thread.clear()
                        
                        break
                    append = str(par_data) + ' ' + str(value) + '\n'
                    self.to_excel.loc[(len(self.to_excel),["date"])], self.to_excel.loc[(len(self.to_excel)-1,["value"])] = par_data, value
                    id = self.root.after(0, self.append_to_textbox, append)
        #id2 = self.root.after(0, self.append_to_textbox, "from CASH")
        self.die_text_box_thread.clear()
    def show_frame_details(self, event):
        selection = self.tree_of_frames.selection()
        if not selection:
            return
        if self.thread_display_details.is_alive() or self.thread_parse_parameters_info.is_alive(): 
            self.die_text_box_thread.set()
            #while self.thread_display_details.is_alive() or self.thread_parse_parameters_info.is_alive(): time.sleep(0.5)
                
        idx = (int(selection[0].split("I")[-1].encode(),16)-3)%(self.parser.num_parameters+2)
        #frame = self.frames[idx]
        if idx >-1 and int(selection[0].split("I")[-1].encode(),16)-3>=0 and -1<(int(selection[0].split("I")[-1].encode(),16)-3)%(self.parser.num_parameters+2)<self.parser.num_parameters:#(int(selection[0].split("I")[-1].encode(),16)%(self.parser.num_parameters+4)!=0):
            self.to_excel = pd.DataFrame(columns=["date","parameter","value"])
            self.text_box.config(state = "normal")
            self.text_box.delete(1.0, tk.END)
            self.text_box.config(state = "disabled")
            cash_obj = self.CASH.get(self.parser.FRAME_TEMPLATE.names[idx])
            if cash_obj.value is not None:
                 self.thread_display_details = threading.Thread(target=self.display_details_thread,args = (cash_obj.value,),daemon = True)
                 self.thread_display_details.start()
            else: 
                self.thread_parse_parameters_info = threading.Thread(target = self.parse_parameters_thread, args = (idx, cash_obj), daemon = True)
                self.thread_parse_parameters_info.start()
    def parse_parameters_thread(self, idx : int, cash_obj : Cash_Object):
        need_delete = False
        while self.die_text_box_thread.is_set(): 
            need_delete = True
            self.text_box.config(state = "normal")
            self.text_box.delete(1.0, tk.END)
            self.text_box.config(state = "disabled")
            pass
        if need_delete : 
            self.to_excel = pd.DataFrame(columns=["date","parameter","value"])
            self.text_box.config(state = "normal")
            self.text_box.delete(1.0, tk.END)
            self.text_box.config(state = "disabled")
        cash_obj.value = []
        self.text_box.config(state = "normal")
        self.text_box.delete(1.0, tk.END)
        self.text_box.config(state = "disabled")
        for par_data, value in self.parser.get_param_information(self.parser.FRAME_TEMPLATE.names[idx]):
                    if self.die_text_box_thread.is_set():
                        try:
                            self.root.after_cancel(id)
                        except:
                            pass
                        self.text_box.config(state = "normal") 
                        self.text_box.delete(1.0, tk.END)
                        self.text_box.config(state = "disabled")
                        self.die_text_box_thread.clear()
                        break
                    text =  str(par_data) + ' ' + str(value) + '\n'
                    cash_obj.value.append((par_data,value))
                    self.to_excel.loc[(len(self.to_excel),["date"])] = par_data
                    self.to_excel.loc[(len(self.to_excel)-1,["value"])] =  value
                    id = self.root.after(0,self.append_to_textbox,text)
        self.die_text_box_thread.clear()
    def display_all(self):
        self.export_dict["date"] = []
        self.export_dict["parameter"] = []
        self.export_dict["value"] = []
        self.text_box.config(state = "normal")
        self.text_box.delete(1.0, tk.END)
        self.text_box.config(state = "disabled")
        for i, frame in enumerate(self.frames):
            self.text_box.config(state = "normal")
            self.text_box.insert(tk.END, f"Фрейм {i+1}\n")
            self.text_box.config(state = "disabled")
            for line in (frame.display_decoded()).split("\n"):
                self.text_box.config(state = "normal")
                self.text_box.insert(tk.END, f"{line}\n")
                self.text_box.config(state = "disabled")
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
            if self.export_par_names : self.to_excel = pd.DataFrame(self.export_dict)
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

