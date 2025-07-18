from .funcs import *
import copy
def get_8bit_bin(hex):
        #print("hex is \n\n",(hex[0]))
        decimal = int(hex, 16)
        
        binary = bin(decimal)[2:].zfill(int(len(hex)*4))#.zfill(8)
        return binary
class parameter:
    def __init__(self, name, start_byte, start_bit, byte_length, bit_length, dec_function = None, coef=1.0 ):
        self.name = name
        self.start_byte, self.start_bit, self.byte_length, self.bit_length = start_byte, start_bit, byte_length, bit_length
        self.decode_func =''.join( str(dec_function).split(' ')) or (lambda x: x)
        self.coef = coef
        self.__raw_data__ = ''
        self.time_stamp = None
        self.func_dict = {'int' : integer,
                          ' int' : integer,
                          'int ' : integer,
                          'float' : float_IEEE754,
                          "float" : float_IEEE754,
                          ' float' : float_IEEE754,
                          'float ' : float_IEEE754,
                            "binary" : binary_yes_no
                          }
    def decode(self):
        try:
            decoded = self.func_dict[str(self.decode_func)](self.__raw_data__,self.coef)
        except:
            if self.__raw_data__ =='':
                decoded = 'нет в кадре'
            elif str(self.decode_func) == 'float':
                self.__raw_data__ : str = self.__raw_data__
                insufficient_length =32 - len(self.__raw_data__)
                #print("function not defined for or data len is unappropriate\n", [i for i in str(self.decode_func)], self.__raw_data__, len(self.__raw_data__))
                decoded = self.func_dict[str(self.decode_func)]('0'*insufficient_length+self.__raw_data__)
            
            else:
                decoded = 0
        self.decoded = decoded
        return self.decoded
class one_frame:
    def __init__(self, size):
        self.time_stamp = None
        self.size = size
        self.named_frame_dict : dict ={}
        self.frame = []
        self.names = []
        self.hex_dec =[]
    def alloc_raw(self, full_raw,times : list = []):
        byte_pointer = 0
        bit_pointer = 0
        time_num = 0
        for n, par in enumerate(self.frame):
            if not self.frame[n].__raw_data__:
                try:    
                    self.frame[n].__raw_data__ = get_8bit_bin(''.join(full_raw[(par.start_byte)-1 : par.start_byte-1+ par.byte_length])) if par.bit_length == 0 else get_8bit_bin(full_raw[par.start_byte-1])[7-par.start_bit: 7- par.start_bit + par.bit_length]
                    self.frame[n].time_stamp = times[int(par.start_byte-1 )] 
                except:
                    self.frame[n].time_stamp= ''
                    self.frame[n].__raw_data__ = ''
    def display_raw(self):
        for par in self.frame:
            pass#print(par.time_stamp, par.name, (par.__raw_data__))

    def display_decoded(self):
        data = ""
        for par in self.frame:
            par.decode()
            self.named_frame_dict[par.name] =par.time_stamp, par.decoded
            #print(par.time_stamp, par.name,par.decoded)
            data += str(par.time_stamp) +" "+ str(par.name) +" "+str(par.decoded) + " \n"
        return data
    def duplicate(self):
        duplicated = copy.deepcopy(self)#one_frame(self.size)
        for n, par in enumerate(duplicated.frame):
            duplicated.frame[n].__raw_data__ = None
            duplicated.frame[n].time_stamp = None
        duplicated.names = self.names
        return duplicated
    def add_parameter(self, name, start_byte, start_bit, byte_length, bit_length, dec_function = None, coef =1.0 ):
        self.frame.append(parameter(name,start_byte, start_bit, byte_length, bit_length, dec_function,coef))
        self.names.append(name)