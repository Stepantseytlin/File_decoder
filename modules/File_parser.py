from .Rules import RULES
from .Frame import one_frame
class ONE_FILE(RULES):
    def __init__(self, path : str):
        self.FILE_PATH = path
        self._ = 0 
        self.FRAMES : list[one_frame]= []
        self.data = []      ### все данные в одной строке
        self.data_str = ""  ### все данные полностью в строчном формате, потом используется 
        self.datas = []     ### все данные с полезной нагрузкой, по сути load, но load - для каждой строки
        self.enable = False
        self.times_for_alloc = []
        self.raw_for_alloc = [] ### Сырые данные для каждого отдельного пакета 
        self.bytes_cntr = 0 
        self.n_frames = 0
        self.n_errors = 0
        self.ERRORS_dict = {}
        self.n_collisions = 0
        self.header = False ### Маркер в середине строки или в начале
        self.header2 = False ### Маркер на границе строк
    @property
    def new_frame(self) -> one_frame:
        self.n_frames+=1
        frame :one_frame = super().start_new_frame()
        return frame
    def read_parameters(self, rules_path : str):
        super().__init__(rules_path)
        self.FRAME_TEMPLATE = self.read_protocol()
    def read_file(self,disable_collisions):
        block_headers = False
        with open(self.FILE_PATH, 'r') as f:
            dat = f.read(2)
            data = []
            while len(dat) == 2:
                data.append(dat)
                dat = f.read(2)
        lines = ''.join(data).split('\n')
        for n,line in enumerate(lines):
            ### Итерируем по каждой строке
            self.header = False
            self.header2 = False
            if len(line.split(' ')) > 3 and line.split(' ')[3]!="ERR":
                ### Если формат строки сохранен, то есть на наличие ошибок 
                date = line.split(' ')[0]
                time = line.split(' ')[1]
                time = ' '.join([date, time])
                self.data =  ((line.split(' ')[4]).split('='))
                #time_data[time] = self.data[1] if len(self.data)==2 else ''
                self.datas.append(self.data[1] if len(self.data)==2 else '')
                load = self.data[1] if len(self.data)==2 else ''
                if self.bytes_cntr > self.length+1-8:
                    ### Если в кадре осталось свободно меньше 8 байт
                    appendix = (((load.split('0x')[-1].split(self.marker)))[-1].split('-'))[0:38-self.bytes_cntr]
                    self.raw_for_alloc += appendix
                    for i in range(len(appendix)):
                                    self.times_for_alloc += [time]
                    new_frame :one_frame = self.new_frame
                    new_frame.alloc_raw(self.raw_for_alloc,self.times_for_alloc)
                    new_frame.hex_dec =  self.raw_for_alloc
                    self.FRAMES.append(new_frame)
                    self.raw_for_alloc,self.times_for_alloc = [],[]
                    self.bytes_cntr = 0
                    self.enable = False
                    if disable_collisions: block_headers = False
                
                if len(load.split(self.marker))>1 and block_headers == False:
                    ### Если в строке Заголовок пакета
                        # Блокируем прием пакетов, если коллизия запрещена 
                        if disable_collisions: block_headers = True
                        self._+=1
                        self.enable = True
                        self.header = True
                if n < len(lines)-1 and block_headers == False:
                    ### Если строка не последняя, то проверяем следующую строку на наличие разорванного заголовка
                        next_date = lines[n+1].split(' ')[0]
                        next_time = lines[n+1].split(' ')[1]
                        next_time = ' '.join([next_date, next_time])
                        next_data = ((lines[n+1].split(' ')[4]).split('='))
                        next_load = next_data[1] if len(next_data)==2 else ''
                        if len( ((''.join(load.split("0x") ).split(self.marker)[-1] )+"-"+ (''.join(next_load.split("0x"))).split(self.marker)[0]).split(self.marker) )>1:
                            ### Проверяем наличие разорванного заголовка
                            # Блокируем прием пакетов, если коллизия запрещена 
                            if disable_collisions: block_headers = True
                            self.enable = True
                            self._+=1
                            self.header2 = True
                           
                
                if self.enable and self.bytes_cntr < self.length:
                    if disable_collisions!=True:
                    ### Если был найден хотя бы один заголовок
                        if (self.header or self.header2) and (self.bytes_cntr>0):
                            ### Если пакет пришел раньше конца предыдущего, то есть КОЛЛИЗИЯ 
                            ### то просто завершаем предыдущий пакет и получаем новый шаблон для пакета 
                            new_frame = self.new_frame
                            new_frame.alloc_raw(self.raw_for_alloc,self.times_for_alloc)
                            new_frame.hex_dec =  self.raw_for_alloc
                            self.FRAMES.append(new_frame)
                            self.bytes_cntr=0
                            self.raw_for_alloc,self.times_for_alloc = [],[]

                        if self.header:
                            ### Если заголовок в строке 
                            if (load.split('0x')[-1]).split(self.marker)[-1]:
                                
                                self.raw_for_alloc += (((load.split('0x')[-1].split(self.marker)))[-1].split('-'))[1:]
                                for i in range(len((''.join( load.split('0x')[-1].split("-"+self.marker+"-")[-1])).split('-'))):
                                    self.times_for_alloc += [time]
                                self.bytes_cntr = 0 
                                self.bytes_cntr +=len((((load.split('0x')[-1].split(self.marker)))[-1].split('-'))[1:]) #len(((''.join(load.split('0x')[-1].split(bench_mark)))[-1].split('-'))[1:])
                        if self.header2:
                            if self.header:
                                new_frame = self.new_frame
                                self.bytes_cntr=0
                                new_frame.hex_dec =  self.raw_for_alloc
                                new_frame.alloc_raw(self.raw_for_alloc,self.times_for_alloc)
                                self.FRAMES.append(new_frame)
                                self.raw_for_alloc,self.times_for_alloc = [],[]
                            whole = ((''.join(load.split("0x") ).split(self.marker)[-1] )+"-"+ (''.join(next_load.split("0x"))).split(self.marker)[0]).split(self.marker)[-1]
                            whole = whole.split('-')[1:]
                            self.raw_for_alloc += (whole)
                            for i in range(len(whole)-1):
                                self.times_for_alloc += [next_time]
                            self.bytes_cntr = 0 
                            self.bytes_cntr += len(whole)
                        else:
                            if not self.header:
                                self.raw_for_alloc = self.raw_for_alloc + (load.split('0x')[-1]).split('-')
                                for i in range(len((load.split('0x')[-1]).split('-'))):
                                    self.times_for_alloc += [time]
                                self.bytes_cntr += 8
                    elif disable_collisions==True:
                        if self.header:
                                ### Если заголовок в строке 
                            if (load.split('0x')[-1]).split(self.marker)[-1]:
                                
                                self.raw_for_alloc += (((load.split('0x')[-1].split(self.marker)))[-1].split('-'))[1:]
                                for i in range(len((''.join( load.split('0x')[-1].split("-"+self.marker+"-")[-1])).split('-'))):
                                    self.times_for_alloc += [time]
                                self.bytes_cntr = 0 
                                self.bytes_cntr +=len((((load.split('0x')[-1].split(self.marker)))[-1].split('-'))[1:])
                        elif self.header2:
                            whole = self.marker.join((''.join(load.split('0x'))+'-'+''.join(next_load.split("0x"))).split(self.marker)[1:])#((''.join(load.split("0x") ).split(self.marker)[-1] )+"-"+ (''.join(next_load.split("0x"))).split(self.marker)[0]).split(self.marker)[-1]
                            whole = whole.split('-')[1:]
                            self.raw_for_alloc += (whole)
                            for i in range(len(whole)-1):
                                self.times_for_alloc += [next_time]
                            self.bytes_cntr = 0 
                            self.bytes_cntr += len(whole)
                        else:
                            #if not self.header:
                            self.raw_for_alloc = self.raw_for_alloc + (load.split('0x')[-1]).split('-')
                            for i in range(len((load.split('0x')[-1]).split('-'))):
                                self.times_for_alloc += [time]
                            self.bytes_cntr += 8
                        
                elif self.enable and self.bytes_cntr >= self.length:
                        
                        self.enable = False
                        if self.n_frames ==0 : print("raw_for alloc final\n\n",self.raw_for_alloc)
                        new_frame = self.new_frame
                        
                        
                        new_frame.alloc_raw(self.raw_for_alloc,self.times_for_alloc)
                        new_frame.hex_dec =  self.raw_for_alloc
                        self.FRAMES.append(new_frame)
                        self.bytes_cntr =0 
                        self.raw_for_alloc,self.times_for_alloc = [],[]
            else:
                self.n_errors+=1
                date = line.split(' ')[0]
                time = line.split(' ')[1]
                time = ' '.join([date, time])
                self.ERRORS_dict[self.n_errors-1] = line.split(' ')[5]
        return self.FRAMES
    def get_param_information(self,name:str):
        if name not in self.FRAME_TEMPLATE.names:
            return 0
        parameter_dynamics = []
        for frame in self.FRAMES:
            parameter_dynamics.append(frame.named_frame_dict[name])
        return parameter_dynamics
    
            