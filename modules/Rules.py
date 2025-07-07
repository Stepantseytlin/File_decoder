from .Frame import parameter, one_frame
def to_float(input : str):
    integ_part = float(1)
    dec = float(1)
    if input:
        integ_part = float(int(input.split('.')[0]))
        dec = float(int(input.split('.')[1])) if len(input.split('.'))>1 else 0.0
    return integ_part+dec
class RULES:
    def __init__(self,path : str):
        self.RULES_FILE_PATH = path
        h = []
        with open(self.RULES_FILE_PATH, 'r') as f:
            dose = f.read(1) 
            while len(dose) == 1:
                h.append(dose)
                dose = f.read(1)
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
    def read_protocol(self):
        FRAME_OBJECT = one_frame(self.length)
        for param in self.parameters[1:]:
            name = param.split(' ')[0]
            format = param.split(' ')[5]
            coef = param.split(' ')[6]
            self.byte_start[name] = int(param.split(' ')[1])
            self.bit_start[name] = int(param.split(' ')[2])
            self.byte_lengths[name] = int(param.split(' ')[3])
            self.bit_lengths[name] = int(param.split(' ')[4])
            self.params[name] = format
            FRAME_OBJECT.add_parameter(name,self.byte_start[name],self.bit_start[name],self.byte_lengths[name],self.bit_lengths[name],format, to_float((coef)))
        return FRAME_OBJECT
    def start_new_frame(self):
        FRAME_OBJECT = one_frame(self.length)
        for param in self.parameters[1:]:
            name = param.split(' ')[0]
            format = param.split(' ')[5]
            coef = param.split(' ')[6]
            self.byte_start[name] = int(param.split(' ')[1])
            self.bit_start[name] = int(param.split(' ')[2])
            self.byte_lengths[name] = int(param.split(' ')[3])
            self.bit_lengths[name] = int(param.split(' ')[4])
            self.params[name] = format
            FRAME_OBJECT.add_parameter(name,self.byte_start[name],self.bit_start[name],self.byte_lengths[name],self.bit_lengths[name],format, to_float((coef)))
        return FRAME_OBJECT