from .Frame import parameter, one_frame
def to_float_or_dict(input : str)->int|dict:
    try:
        return float(input)
        # integ_part = float(1)
        # dec = float(1)
        # if input:
        #     integ_part = float(int(input.split('.')[0]))
        #     dec = float(int(input.split('.')[1])) if len(input.split('.'))>1 else 0.0
        # return integ_part+dec*(0.1**len(input.split('.')[-1]))
    except:
        
        data_ = input.split("data(")[1].split(")")[0]
        items = data_.split(";")
        data_dict = {}
        for item in items:
            data_dict[int(item.split(":")[0])] = item.split(":")[1]
        return data_dict
class RULES:
    def __init__(self,path : str,numProtocol:int = 0):
        self.RULES_FILE_PATH = path
        h = []
        with open(self.RULES_FILE_PATH, 'r') as f:
            dose = f.read(1) 
            while len(dose) == 1:
                h.append(dose)
                dose = f.read(1)
        self.protocols = ("".join(h)).split("\n--\n")
        self.numProtocols = len (self.protocols)
        h = self.protocols[numProtocol]
        self.parameters = (''.join(h)).split('\n')
        self.num_parameters = len(self.parameters)-1
        self.params = dict()
        self.byte_lengths = dict()
        self.bit_lengths = dict()
        self.byte_start = dict()
        self.bit_start = dict()
        self.marker = self.parameters[0].split(" ")[0]
        self.marker = self.marker[:2] + "-" + self.marker[2:]
        self.length= int(self.parameters[0].split(" ")[1])
        self.FRAME_OBJECT : one_frame
    def CountProtocols(self):
        return self.numProtocols
    def read_protocol(self):
        FRAME_OBJECT = one_frame(self.length)
        for param in self.parameters[1:]:
            name = param.split(' ')[0]
            format = param.split(' ')[5]
            try: coef = ''.join(param.split(' ')[6:])
            except:coef = 1
            self.byte_start[name] = int(param.split(' ')[1])
            self.bit_start[name] = int(param.split(' ')[2])
            self.byte_lengths[name] = int(param.split(' ')[3])
            self.bit_lengths[name] = int(param.split(' ')[4])
            self.params[name] = format
            FRAME_OBJECT.add_parameter(name,self.byte_start[name],self.bit_start[name],self.byte_lengths[name],self.bit_lengths[name],format, to_float_or_dict((coef)))
        return FRAME_OBJECT
    def start_new_frame(self):
        FRAME_OBJECT = one_frame(self.length)
        for param in self.parameters[1:]:
            name = param.split(' ')[0]
            format = param.split(' ')[5]
            try: coef = ''.join(param.split(' ')[6:])
            except:coef = 1
            self.byte_start[name] = int(param.split(' ')[1])
            self.bit_start[name] = int(param.split(' ')[2])
            self.byte_lengths[name] = int(param.split(' ')[3])
            self.bit_lengths[name] = int(param.split(' ')[4])
            self.params[name] = format
            FRAME_OBJECT.add_parameter(name,self.byte_start[name],self.bit_start[name],self.byte_lengths[name],self.bit_lengths[name],format, to_float_or_dict((coef)))
        return FRAME_OBJECT