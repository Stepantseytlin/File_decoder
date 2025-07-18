class Cash_Object:
    def __init__(self, name):
        self.name = name
        self.value : list[str]|str = None
        self.to_head : Cash_Object = None
        self.to_tail : Cash_Object = None

class LRU_CASH:
    def __init__(self, size:int):
        self.size = size
        self.head : Cash_Object= None
        self.tail : Cash_Object = None 
        self.all_objects = {}
        self.counter = 0
    def clear(self):
        self.counter = 0
        self.head : Cash_Object= None
        self.tail : Cash_Object = None 
        self.all_objects = {}
    def get(self, name : str):
        if name in list(self.all_objects.keys()):
            requested : Cash_Object = self.all_objects[name]
            
            if requested == self.head: 
                requested.to_tail = self.head.to_tail
                next_tail = self.tail
            else:
                if requested==self.tail:
                    next_tail = requested.to_head if requested != self.head else self.tail
                else:
                    next_tail = self.tail
                    requested.to_tail.to_head = requested.to_head
                    requested.to_head.to_tail = requested.to_tail
                requested.to_tail = self.head if self.head else None
            self.head.to_head = requested
            #self.head.to_tail = self.
            self.head = requested
            self.tail = next_tail 
            self.head.to_head = None
            self.tail.to_tail = None 
            return requested
        else:
            if self.counter == self.size:
                self.all_objects.pop(self.tail.name)
                self.tail = self.tail.to_head
                self.tail.to_tail = None
            requested: Cash_Object = Cash_Object(name=name)
            if self.counter==0:
                self.tail = requested
                self.head = requested
            requested.to_tail = self.head
            self.head.to_head = requested
            self.head = requested
            self.all_objects[name] = requested
            self.head = self.all_objects[name]
            self.head.to_head = None 
            self.counter+=1
            self.tail.to_tail = None

            return requested
