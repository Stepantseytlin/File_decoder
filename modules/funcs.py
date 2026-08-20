import struct

def integer(raw,coef = 1.0):
    if isinstance(coef, dict):
        integ = int(raw,2)
        dictionary :dict = coef
        decoded = dictionary.get(integ, integ)

        return decoded
    else:
        integ = int(raw,2)*coef
        return integ
def binary_yes_no(raw,coef = None):
    if isinstance(coef, dict):
            integ = int(raw,2)
            dictionary :dict = coef
            decoded = dictionary.get(integ, integ)
    
            return decoded
    return "ready" if raw else "not ready"
    
    
def float_IEEE754(binary,coef=1.0)->float:
    
    """
    Преобразует 32-битное число в двоичной системе в float (формат IEEE 754).
    :param binary: строка из 32 символов (0 и 1), представляющая число в двоичной системе.
    :return: число с плавающей точкой (float).
    """
    if len(binary) != 32 or not all(bit in '01' for bit in binary):
        #print(binary)
        raise ValueError("Число должно быть строкой из 32 символов, содержащих только 0 или 1.")
    
    # Преобразуем двоичную строку в целое число
    int_value = int(binary, 2)
    
    # Упаковываем это число как 32-битное беззнаковое целое
    packed = struct.pack('!I', int_value)
    
    # Распаковываем как float по стандарту IEEE 754
    float_value = struct.unpack('!f', packed)[0]
    
    return float_value*coef
def custom(binary, dict : dict):
    return dict[binary]
