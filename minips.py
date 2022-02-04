import struct
import numpy as np
import os.path
import time
import math

from cache import *

from tools import *

# Variáveis globais ------------------------------- 
execute = True
opr = False
mode = 1
memory = {}
registers = []
registersFP = []
hi = 0x00000000
lo = 0x00000000
cc = False
pc = 0x00400000

# Variáveis para simular o branch delay slot e contagem de instruções
startTime = 0
endTime = 0
iC = 0
iCount = 0
rCount = 0
jCount = 0
frCount = 0
fiCount = 0
iCBD = 0
delay = False
pcBD = 0x00400000

# Variáveis de simulação e memória
cycles = 0
hits = 0
misses = 0
file = None

# Função de contabilização de acesso à memória ----------------------
def memoryAccess():
    global cycles, hits, misses
    
    cycles += 100
    hits += 1

# Funções de String Syscall -----------------------
def syscallString():
    global registers, registersFP, pc, cycles, opr, mode

    i = 0
    text = ""
    targetAddress = registers[4]
    
    # Função para receber a string a ser impressa
    # Desvio na leitura da memória é feito para contabilizar
    # a leitura por palavras corretamente, ao invés de realizar
    # esse processo byte a bye
    while (True):
        exit = False

        data = []

        if (mode == 1):
            data = [
                memory[targetAddress - (targetAddress % 4) + i],
                memory[targetAddress - (targetAddress % 4) + i + 1],
                memory[targetAddress - (targetAddress % 4) + i + 2],
                memory[targetAddress - (targetAddress % 4) + i + 3]]
        
        # Acesso à cache e contabilização dos ciclos
        elif (mode == 2):
            data = cache.getWordL1Unif(targetAddress - (targetAddress % 4) + i, 'R', False, 1)
        elif (mode == 3 or mode == 4):
            data = cache.getWordL1Split(targetAddress - (targetAddress % 4) + i, 1, 'R', False, 1)

        # Remoção dos caracteres irrelevantes
        if (i == 0):
            index = targetAddress % 4
            data = data[index:4]

        if (b'\0' in data):
            index = data.index(b'\0')
            data = data[0:index]
            exit = True

        data = b''.join(data)

        # Acesso dos dados depende da codificação das instruções!
        text += data.decode('iso-8859-1')

        # Contabilização no modo sem cache
        diff = targetAddress - (targetAddress % 4) + i 
        if (mode == 1 and ((i == 0) or (diff % 4 == 0))):
            memoryAccess()
            
            if (opr > 1):
                address = targetAddress - (targetAddress % 4) + i
                writeFile(file, opr, mode, 'R', address)

        if exit:
            break

        i += 4

    return text


# Instruções Tipo I -------------------------------

def addi(rs, rt, value, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ADDI {registerTranslator(rt)}, {registerTranslator(rs)}, {value}'
        printer(pc, word, content)

    else:
        registers[rt] = abs(registers[rs]) + abs(sign_extend(value, 32))
    
def andi(rs, rt, value, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ANDI {registerTranslator(rt)}, {registerTranslator(rs)}, {value}'
        printer(pc, word, content)

    else:
        registers[rt] = registers[rs] & sign_extend(value, 32)

def addiu(rs, rt, value, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ADDIU {registerTranslator(rt)}, {registerTranslator(rs)}, {twoComplement(value, 16)}'
        printer(pc, word, content)

    else:
        registers[rt] = registers[rs] + sign_extend(twoComplement(value, 16), 32)

def beq(rs, rt, value, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    pc = int(pc)

    if (opr == 1):
        content = f'BEQ {registerTranslator(rs)}, {registerTranslator(rt)}, {twoComplement(value, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and registers[rs] == registers[rt]):
            pcBD = pc + (sign_extend(twoComplement(value, 16), 30) << 2)
            iCBD = iC 
            delay = True

def bgez(rs, value, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    pc = int(pc)

    if (opr == 1):
        content = f'BGEZ {registerTranslator(rs)}, {twoComplement(value, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and registers[rs] >= 0):
            pcBD = pc + (sign_extend(twoComplement(value, 16), 30) << 2)
            iCBD = iC 
            delay = True

def blez(rs, value, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    pc = int(pc)

    if (opr == 1):
        content = f'BLEZ {registerTranslator(rs)}, {twoComplement(value, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and registers[rs] <= 0):
            pcBD = pc + (sign_extend(twoComplement(value, 16), 30) << 2)
            iCBD = iC 
            delay = True

def bne(rs, rt, value, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    pc = int(pc)

    if (opr == 1):
        content = f'BNE {registerTranslator(rs)}, {registerTranslator(rt)}, {twoComplement(value, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and registers[rs] != registers[rt]):
            pcBD = pc + (sign_extend(twoComplement(value, 16), 30) << 2)
            iCBD = iC 
            delay = True

def lb(rs, rt, value, word):
    global registers, memory, opr, pc, mode, cycles

    if (opr == 1):
        content = f"LB {registerTranslator(rt)}, {value}({registerTranslator(rs)})  # {hex(int(value))}"
        printer(pc, word, content)

    else:
        value = sign_extend(value, 32)

        # Contabilização de acesso
        if (mode == 1):
            memoryAccess()
            cycles -= 1
        elif (mode >= 2):
            cache.cycles -= 1

        data = None

        # Leitura do byte a partir do endereço alvo (registers[rs] + value), 
        # para ser traduzido
        if (mode == 1):
            data = memory[registers[rs] + value]
        elif (mode == 2):
            data = cache.getWordL1Unif(registers[rs] + value, 'R', True, 0)
        elif (mode == 3 or mode == 4):
            data = cache.getWordL1Split(registers[rs] + value, 1, 'R', False, 0)
        word = int.from_bytes(data, 'little')
        registers[rt] = sign_extend(word, 32)

def lui(rt, value, word):
    global registers, opr

    if (opr == 1):
        content = f'LUI {registerTranslator(rt)}, {value}'
        printer(pc, word, content)

    else:
        value = value << 16
        registers[rt] = value

def lw(rs, rt, value, word):
    global registers, memory, opr, pc, mode, cycles

    if (opr == 1):

        aux = value
        if (twoComplement(value, 16) < 0):
            aux = int2hex(twoComplement(value, 16), 32)
        else:
            aux = hex(int(twoComplement(value, 16)))

        content = f"LW {registerTranslator(rt)}, {twoComplement(value, 16)}({registerTranslator(rs)}) # {aux}"
        printer(pc, word, content)

    else:
        value = sign_extend(twoComplement(value, 16), 32)

        # Leitura dos 4 bytes a partir do endereço alvo (registers[rs] + value), 
        # para serem juntados e traduzidos

        # Contabilização de acesso
        if (mode == 1):
            memoryAccess()
            cycles -= 1
            
            if (opr > 1):
                address = registers[rs] + value
                writeFile(file, opr, mode, 'R', address)

        elif (mode >= 2):
            cache.cycles -= 1

        data = []

        if (mode == 1):
            data = memory[registers[rs] + value], memory[registers[rs] + value + 1], memory[registers[rs] + value + 2], memory[registers[rs] + value + 3]
            data = b''.join(data)
        elif (mode == 2):
            data = cache.getWordL1Unif(registers[rs] + value, 'R', False, 0)
        elif (mode == 3 or mode == 4):
            data = cache.getWordL1Split(registers[rs] + value, 1, 'R', False, 0)
        word = int(readLittleEndian(data), 16)
        registers[rt] = word

def ldc1(rs, rt, value, word):
    global registers, opr, pc, mode, cycles

    if (opr == 1):
        content = f"LDC1 {registerFloatTranslator(rt)}, {value}({registerTranslator(rs)}) # {hex(int(value))}"
        printer(pc, word, content)

    else:
        value = sign_extend(twoComplement(value, 16), 32)

        # Contabilização de acesso
        if (mode == 1):
            memoryAccess()
            memoryAccess()
            cycles -= 1

            if (opr > 1):
                address = registers[rs] + value
                writeFile(file, opr, mode, 'R', address)
                writeFile(file, opr, mode, 'R', address + 4)
        elif (mode >= 2):
            cache.cycles -= 1

        # Leitura dos 4 bytes a partir do endereço alvo (registers[rs] + value), 
        # para serem juntados e traduzidos
        data = [] 
        
        if (mode == 1):
            data = memory[registers[rs] + value], memory[registers[rs] + value + 1], memory[registers[rs] + value + 2], memory[registers[rs] + value + 3]
            data = b''.join(data)
        elif (mode == 2):
            data = cache.getWordL1Unif(registers[rs] + value, 'R', False, 0)
        elif (mode == 3 or mode == 4):
            data = cache.getWordL1Split(registers[rs] + value, 1, 'R', False, 0)

        word = int(readLittleEndian(data), 16)
        
        if (word < 0):
            word = int(int2hex(word, 32), 16)
        
        registersFP[rt] = word

        # Leitura dos 4 bytes a partir do endereço alvo (registers[rs] + value + 4), 
        # para serem juntados e traduzidos
        data2 = []
        
        if (mode == 1):
            data2 = memory[registers[rs] + value + 4], memory[registers[rs] + value + 5], memory[registers[rs] + value + 6], memory[registers[rs] + value + 7]
            data2 = b''.join(data2)
        elif (mode == 2):
            data2 = cache.getWordL1Unif(registers[rs] + value + 4, 'R', False, 0)
        elif (mode == 3 or mode == 4):
            data2 = cache.getWordL1Split(registers[rs] + value + 4, 1, 'R', False, 0)
        word2 = int(readLittleEndian(data2), 16)

        if (word2 < 0):
            word2 = int(int2hex(word, 32), 16)
        
        registersFP[rt + 1] = word2

def lwc1(rs, rt, value, word):
    global registers, opr, pc, mode, cycles

    if (opr == 1):
        content = f"LWC1 {registerFloatTranslator(rt)}, {value}({registerTranslator(rs)}) # {hex(int(value))}"
        printer(pc, word, content)

    else:
        value = sign_extend(twoComplement(value, 16), 32)

        # Contabilização de acesso
        if (mode == 1):
            memoryAccess()
            cycles -= 1

            if (opr > 1):
                address = registers[rs] + value
                writeFile(file, opr, mode, 'R', address)
        elif (mode >= 2):
            cache.cycles -= 1

        # Leitura dos 4 bytes a partir do endereço alvo (registers[rs] + value), 
        # para serem juntados e traduzidos
        data = []
        
        if (mode == 1):
            data = memory[registers[rs] + value], memory[registers[rs] + value + 1], memory[registers[rs] + value + 2], memory[registers[rs] + value + 3]
            data = b''.join(data)
        elif (mode == 2):
            data = cache.getWordL1Unif(registers[rs] + value, 'R', False, 0)
        elif (mode == 3 or mode == 4):
            data = cache.getWordL1Split(registers[rs] + value, 1, 'R', False, 0)
        word = int(readLittleEndian(data), 16)

        if (word < 0):
            word = int(int2hex(word, 32), 16)

        registersFP[rt] = word


def ori(rs, rt, value, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ORI {registerTranslator(rt)}, {registerTranslator(rs)}, {value}'
        printer(pc, word, content)

    else:
        registers[rt] = registers[rs] | (0x00000000 | value)

def sw(rs, rt, value, word):
    global registers, opr, memory, pc, mode, cycles

    if (opr == 1):

        aux = twoComplement(value, 16)
        if (aux < 0):
            aux = int2hex(aux, 32)
        else:
            aux = hex(int(aux))

        content = f"SW {registerTranslator(rt)}, {twoComplement(value, 16)}({registerTranslator(rs)}) # {aux}"
        printer(pc, word, content)

    else:
        value = sign_extend(twoComplement(value, 16), 32)

        # Conversão do valor armazenado no registrador em 4 bytes e separação em bytes individuais,
        # para serem armazenados nos 4 bytes a partir do endereço alvo (registers[rs] + value)
        data = registers[rt]
        data = (data).to_bytes(4, byteorder='little', signed=True)

        dataChunk1 = data[:1]
        dataChunk2 = data[1:2]
        dataChunk3 = data[2:3]
        dataChunk4 = data[-1:]

        if (mode == 1):
            memory[registers[rs] + value] = dataChunk1
            memory[registers[rs] + value + 1] = dataChunk2
            memory[registers[rs] + value + 2] = dataChunk3
            memory[registers[rs] + value + 3] = dataChunk4

            # Contabilização de acesso
            memoryAccess()
            cycles -= 1

            if (opr > 1):
                address = registers[rs] + value
                writeFile(file, opr, mode, 'W', address)
        
        elif (mode == 2):
            data = [dataChunk1, dataChunk2, dataChunk3, dataChunk4]
            cache.storeWordL1Unif(registers[rs] + value, data)
            cache.cycles -= 1
        
        elif (mode == 3 or mode == 4):
            data = [dataChunk1, dataChunk2, dataChunk3, dataChunk4]
            cache.storeWordL1Split(registers[rs] + value, 1, data)
            cache.cycles -= 1

def slti(rs, rt, value, word):
    global registers, opr

    if (opr == 1):
        content = f'SLTI {registerTranslator(rt)}, {registerTranslator(rs)}, {sign_extend(value, 32)}'
        printer(pc, word, content)
    
    else:
        if (registers[rs] < sign_extend(value, 32)):
            registers[rt] = 1
        else:
            registers[rt] = 0

def swc1(rs, rt, value, word):
    global registers, opr, memory, pc, mode, cycles

    if (opr == 1):
        content = f"SWC1 {registerFloatTranslator(rt)}, {value}({registerTranslator(rs)}) # {hex(int(value))}"
        printer(pc, word, content)

    else:
        value = sign_extend(twoComplement(value, 16), 32)

        # Conversão do valor armazenado no registrador em 4 bytes e separação em bytes individuais,
        # para serem armazenados nos 4 bytes a partir do endereço alvo (registers[rs] + value)
        data = registersFP[rt]
        data = (data).to_bytes(4, byteorder='little')

        dataChunk1 = data[:1]
        dataChunk2 = data[1:2]
        dataChunk3 = data[2:3]
        dataChunk4 = data[-1:]

        if (mode == 1):
            memory[registers[rs] + value] = dataChunk1
            memory[registers[rs] + value + 1] = dataChunk2
            memory[registers[rs] + value + 2] = dataChunk3
            memory[registers[rs] + value + 3] = dataChunk4

            # Contabilização de acesso
            memoryAccess()
            cycles -= 1
            
            if (opr > 1):
                address = registers[rs] + value
                writeFile(file, opr, mode, 'W', address)

        elif (mode == 2):
            data = [dataChunk1, dataChunk2, dataChunk3, dataChunk4]
            cache.storeWordL1Unif(registers[rs] + value, data)
            cache.cycles -= 1

        elif (mode == 3 or mode == 4):
            data = [dataChunk1, dataChunk2, dataChunk3, dataChunk4]
            cache.storeWordL1Split(registers[rs] + value, 1, data)
            cache.cycles -= 1


# Instruções Tipo R -------------------------------

def add(rs, rt, rd, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ADD {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)
    
    else:
        if (rd != 0):
            registers[rd] = registers[rs] + registers[rt]

def addu(rs, rt, rd, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'ADDU {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            registers[rd] = twoComplement((registers[rs] + registers[rt]) & 0xffffffff, 32)

def _and(rs, rt, rd, word): 
    global registers, opr, pc

    if (opr == 1):
        content = f'AND {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            registers[rd] = registers[rs] & registers[rt]

def div(rs, rt, word):
    global registers, opr, lo, hi, pc

    if (opr == 1):
        content = f'DIV {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        lo = int(registers[rs] / registers[rt])
        hi = int(math.fmod(registers[rs], registers[rt]))

def mfhi(rd, word):
    global registers, opr, lo, hi, pc

    if (opr == 1):
        content = f'MFHI {registerTranslator(rd)}'
        printer(pc, word, content)

    else:
        registers[rd] = hi

def mflo(rd, word):
    global registers, opr, lo, hi, pc

    if (opr == 1):
        content = f'MFLO {registerTranslator(rd)}'
        printer(pc, word, content)

    else:
        registers[rd] = lo


def mult(rs, rt, word):
    global registers, opr, lo, hi, pc

    if (opr == 1):
        content = f'MULT {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        product = (registers[rs] * registers[rt])
        hi = product >> 32
        lo = product & (0xffffffff)

def _or(rd, rs, rt, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'OR {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        registers[rd] = int(registers[rs]) | int(registers[rt])

def sra(rt, rd, shamt, word):
    global registers, opr

    if (opr == 1):
        content = f'SRA {registerTranslator(rd)}, {registerTranslator(rt)}, {shamt}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            value = registers[rt]

            if (value < 0):
                value = (pow(2, 32 - shamt) - 1 << shamt | value >> shamt) & 0xffffffff
                registers[rd] = twoComplement(value, 32)
            else:
                registers[rd] = value >> shamt

def sll(rt, rd, shamt, word):
    global registers, opr, pc

    if (opr == 1):
        content = ""
        if (word == 0x00000000):
            content = f'NOP'
        elif (word & 0xff == 0x0000000d):
            content = f'BREAK'
        else:
            content = f'SLL {registerTranslator(rd)}, {registerTranslator(rt)}, {shamt}'
        printer(pc, word, content)
    
    else:
        if (rd != 0):
            registers[rd] = twoComplement((registers[rt] << shamt) & 0xffffffff, 32)

def srl(rt, rd, shamt, word):
    global registers, opr

    if (opr == 1):
        content = f'SRL {registerTranslator(rd)}, {registerTranslator(rt)}, {shamt}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            registers[rd] = twoComplement((registers[rt] >> shamt) & 0xffffffff, 32)

def slt(rs, rt, rd, word):
    global registers, opr

    if (opr == 1):
        content = f'SLT {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            if (registers[rs] < registers[rt]):
                registers[rd] = sign_extend(1, 32)
            else:
                registers[rd] = sign_extend(0, 32)

def sltu(rs, rt, rd, word):
    global registers, opr

    if (opr == 1):
        content = f'SLTU {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            if (abs(registers[rs]) < abs(registers[rt])):
                registers[rd] = sign_extend(1, 32)
            else:
                registers[rd] = sign_extend(0, 32)

def subu(rs, rt, rd, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'SUBU {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        if (rd != 0):
            registers[rd] = abs(registers[rs]) - abs(registers[rt])

def xor(rs, rt, rd, word):
    global registers, opr, pc

    if (opr == 1):
        content = f'XOR {registerTranslator(rd)}, {registerTranslator(rs)}, {registerTranslator(rt)}'
        printer(pc, word, content)

    else:
        registers[rd] = registers[rs] ^ registers[rt]

# Implementação soma pc por 4 a cada instrução, 
# para compensar isso foram feitos os descontos em 4 para os valores de pcBD
# nas instruções de jump dada a forma de simulação do branch delay slot
def jr(rs, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    if (opr == 1):
        content = f'JR {registerTranslator(rs)}'
        printer(pc, word, content)

    else:
        if (not delay):
            pcBD = registers[rs] - (4 & 0xffffffff)
            iCBD = iC 
            delay = True

def jalr(rs, rd, word):
    global registers, opr, pc, pcBD, iC, iCBD, delay

    if (opr == 1):
        if (rd == 31):
            content = f'JALR {registerTranslator(rs)}'
        else:
            content = f'JALR {registerTranslator(rd)}, {registerTranslator(rs)}'
        printer(pc, word, content)

    else:
        if (not delay and rs != rd):
            pcBD = registers[rs] - (4 & 0xffffffff)
            registers[rd] = pc + (8 & 0xffffffff)
            iCBD = iC
            delay = True

# Instruções tipo J ----------------------------

def j(address, word):
    global pc, pcBD, iC, iCBD, delay
    
    if (opr == 1):
        content = f'J {hex(int(address))} # {hex(int(address) * 4)}'
        printer(pc, word, content)

    else:
        if (not delay):
            pcBD = ((pc + 4) >> 28 & 0xf)  + (sign_extend(address, 30) << 2) - (4 & 0xffffffff)
            iCBD = iC 
            delay = True

def jal(address, word):
    global pc, pcBD, iC, iCBD, delay

    if (opr == 1):
        content = f'JAL {hex(int(address))} # {hex(int(address) * 4)}'
        printer(pc, word, content)

    else:
        if (not delay):
            registers[31] = pc + (8 & 0xffffffff)
            pcBD = ((pc + 4) >> 28 & 0xf)  + (sign_extend(address, 30) << 2) - (4 & 0xffffffff)
            iCBD = iC 
            delay = True

def syscall(word):
    global execute, registers, registersFP, pc, cycles, opr, mode

    v0 = registers[2]

    # Imprimir inteiro em $a0
    if (v0 == 1):
        print(registers[4], end='')

    # Imprimir float em $f12
    elif (v0 == 2):
        print(convertToFloatDouble(registersFP[12], 32), end='')

    # Imprimir double em $f12/$f13
    elif (v0 == 3):
        double = (registersFP[13] << 32) | registersFP[12]
        double = convertToFloatDouble(double, 64)
        if (double > 10000000):
            double = np.format_float_scientific(double, unique=False, precision=16)
        print(double, end='')

    # Imprimir string terminada em '\0' em $a0
    elif (v0 == 4):
        text = syscallString()
        if (mode == 1):
            cycles -= 1
        elif (mode >= 2):
            cache.cycles -= 1
        
        print(text, end='')

    # Ler um inteiro do usuário e guardar em $v0
    elif (v0 == 5):
        # Checa por inputs negativos
        value = userInput(int(input(), 10))
        registers[2] = value

    # Ler um float do usuário e guardar em $f0
    elif (v0 == 6):
        value = float_to_bin(float(input()), 32)
        registersFP[0] = int(value, 2)

    # Ler um double do usuário e guardar em $f0/$f1
    elif (v0 == 7):
        value = float_to_bin(float(input()), 64)
        registersFP[0] = int(value[32:64], 2)
        registersFP[1] = int(value[0:32], 2)
    
    # Encerrar o programa
    elif (v0 == 10):
        execute = False
        print('\n\033[94m' + "----- So long! [Execution finished successfully] -----" + '\033[0m')
        return
    
    # Imprimir um char em $a0
    elif (v0 == 11):
        print(chr(registers[4]), end='')
    
    if (opr == 1):
        content = "SYSCALL"
        printer(pc, word, content)


# Instruções FP -----------------------------------------

def addD(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'ADD.D {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        doubleFt = (registersFP[ft + 1] << 32) | registersFP[ft]
        doubleFt = convertToFloatDouble(doubleFt, 64)

        doubleFs = (registersFP[fs + 1] << 32) | registersFP[fs]
        doubleFs = convertToFloatDouble(doubleFs, 64)
        
        doubleFd = float_to_bin(float(doubleFs + doubleFt), 64)
        registersFP[fd] = int(doubleFd[32:64], 2)
        registersFP[fd + 1] = int(doubleFd[0:32], 2)

def addS(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'ADD.S {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        singleFs = convertToFloatDouble(registersFP[fs], 32)
        singleFt = convertToFloatDouble(registersFP[ft], 32)

        value = float_to_bin(singleFs + singleFt, 32)
        registersFP[fd] = int(value, 2)

def bc1f(offset, word):
    global cc, opr, pc, pcBD, iC, iCBD, delay
    
    ccField = word >> 18 & 0x7

    if (opr == 1):
        if (ccField == 0):
            content = f'BC1F {twoComplement(offset, 16)}'
        else:
            content = f'BC1F {ccField}, {twoComplement(offset, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and cc == False):
            pcBD = pc + (sign_extend(twoComplement(offset, 16), 30) << 2)
            iCBD = iC 
            delay = True

def bc1t(offset, word):
    global cc, opr, pc, pcBD, iC, iCBD, delay
    
    ccField = word >> 18 & 0x7

    if (opr == 1):
        if (ccField == 0):
            content = f'BC1T {twoComplement(offset, 16)}'
        else:
            content = f'BC1T {ccField}, {twoComplement(offset, 16)}'
        printer(pc, word, content)

    else:
        if (not delay and cc == True):
            pcBD = pc + (sign_extend(twoComplement(offset, 16), 30) << 2)
            iCBD = iC 
            delay = True

def cltS(ft, fs, word):
    global registers, registersFP, cc, opr, pc
    
    ccField = word >> 8 & 0x7

    if (opr == 1):
        if (ccField == 0):
            content = f'C.LT.S {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        else:
            content = f'C.LT.S {ccField}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        singleFs = convertToFloatDouble(registersFP[fs], 32)
        singleFt = convertToFloatDouble(registersFP[ft], 32)

        if (singleFs < singleFt):
            cc = True
        else:
            cc = False

def cvtDW(fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'CVT.D.W {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        value = float_to_bin(float(registersFP[fs]), 64)        
        registersFP[fd] = int(value[32:64], 2)
        registersFP[fd + 1] = int(value[0:32], 2)

def cvtSD(fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'CVT.S.D {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        doubleFs = (registersFP[fs + 1] << 32) | registersFP[fs]
        doubleFs = convertToFloatDouble(doubleFs, 64)
        doubleFs = np.float32(doubleFs)

        floatFs = int(float_to_bin(doubleFs, 32), 2)

        registersFP[fd] = floatFs

def divD(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'DIV.D {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        doubleFt = (registersFP[ft + 1] << 32) | registersFP[ft]
        doubleFt = convertToFloatDouble(doubleFt, 64)

        doubleFs = (registersFP[fs + 1] << 32) | registersFP[fs]
        doubleFs = convertToFloatDouble(doubleFs, 64)
        
        doubleFd = float_to_bin(float(doubleFs / doubleFt), 64)

        registersFP[fd] = int(doubleFd[32:64], 2)
        registersFP[fd + 1] = int(doubleFd[0:32], 2)

def divS(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'DIV.S {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        floatFs = convertToFloatDouble(registersFP[fs], 32)
        floatFt = convertToFloatDouble(registersFP[ft], 32)
        
        value = float_to_bin(floatFs / floatFt, 32)
        registersFP[fd] = int(value, 2)

def movD(fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MOV.D {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        registersFP[fd] = registersFP[fs]
        registersFP[fd+1] = registersFP[fs+1]

def movS(fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MOV.S {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        registersFP[fd] = registersFP[fs]

def mulD(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MUL.D {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        doubleFt = (registersFP[ft + 1] << 32) | registersFP[ft]
        doubleFt = convertToFloatDouble(doubleFt, 64)

        doubleFs = (registersFP[fs + 1] << 32) | registersFP[fs]
        doubleFs = convertToFloatDouble(doubleFs, 64)
        
        doubleFd = float_to_bin(float(doubleFt * doubleFs), 64)
        registersFP[fd] = int(doubleFd[32:64], 2)
        registersFP[fd + 1] = int(doubleFd[0:32], 2)

def mulS(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MUL.S {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        singleFs = convertToFloatDouble(registersFP[fs], 32)
        singleFt = convertToFloatDouble(registersFP[ft], 32)

        singleFd = float_to_bin(singleFs * singleFt, 32)
        registersFP[fd] = int(singleFd, 2)

def mfc1(rt, fs, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MFC1 {registerTranslator(rt)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        registers[rt] = twoComplement(registersFP[fs], 32)

def mtc1(rt, fs, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'MTC1 {registerTranslator(rt)}, {registerFloatTranslator(fs)}'
        printer(pc, word, content)

    else:
        registersFP[fs] = registers[rt]

def subS(ft, fs, fd, word):
    global registers, registersFP, opr, pc
    
    if (opr == 1):
        content = f'SUB.S {registerFloatTranslator(fd)}, {registerFloatTranslator(fs)}, {registerFloatTranslator(ft)}'
        printer(pc, word, content)

    else:
        singleFs = convertToFloatDouble(registersFP[fs], 32)
        singleFt = convertToFloatDouble(registersFP[ft], 32)

        value = float_to_bin(singleFs - singleFt, 32)
        registersFP[fd] = int(value, 2)
    

# R-format
#  op   |   rs   |   rt   |   rd   |  shamt  |  funct
# 6bits |  5bits |  5bits |  5bits |  5bits  |  6bits

def rType(word):
    global pc, rCount, opr, mode, file

    # Escrita no arquivo minips.trace
    if (opr > 1 and mode == 1):
        writeFile(file, opr, mode, 'I', pc)

    rs = word >> 21 & 0x1f
    rt = word >> 16 & 0x1f
    rd = word >> 11 & 0x1f
    shamt = word >> 6 & 0x1f
    funct = word & 0x3f
        
    if (funct == 12):
        syscall(word)
    elif (funct == 32):
        add(rs, rt, rd, word)
    elif (funct == 33):
        addu(rs, rt, rd, word)
    elif (funct == 36):
        _and(rs, rt, rd, word)
    elif (funct == 26):
        div(rs, rt, word)
    elif (funct == 8):
        jr(rs, word)
    elif (funct == 9):
        jalr(rs, rd, word)
    elif (funct == 16):
        mfhi(rd, word)
    elif (funct == 18):
        mflo(rd, word)
    elif (funct == 24):
        mult(rs, rt, word)
    elif (funct == 37):
        _or(rd, rs, rt, word)
    elif (funct == 3):
        sra(rt, rd, shamt, word)
    # 13: Tratamendo de break
    elif (funct == 0 or funct == 13):
        sll(rt, rd, shamt, word)
    elif (funct == 2):
        srl(rt, rd, shamt, word)
    elif (funct == 42):
        slt(rs, rt, rd, word)
    elif (funct == 43):
        sltu(rs, rt, rd, word)
    elif (funct == 35):
        subu(rs, rt, rd, word)
    elif (funct == 38):
        xor(rs, rt, rd, word)

    # Incrementa o valor de pc em 4 para seguir para a próxima palavra
    pc = pc + 4 

    # Incrementa a contagem de instruções
    rCount += 1

# I-format
#  op   |   rs   |   rt   |  constante ou endereco (valor)
# 6bits |  5bits |  5bits |          16bits

def iType(opcode, word):
    global pc, iCount, opr, mode, file

    # Escrita no arquivo minips.trace
    if (opr > 1 and mode == 1):
        writeFile(file, opr, mode, 'I', pc)

    rs = word >> 21 & 0x1f
    rt = word >> 16 & 0x1f
    value = word & 0xffff

    if (opcode == 8):
        addi(rs, rt, value, word)
    elif (opcode == 9):
        addiu(rs, rt, value, word)
    elif (opcode == 12):
        andi(rs, rt, value, word)
    elif (opcode == 4):
        beq(rs, rt, value, word)
    elif (opcode == 1 and rt == 1):
        bgez(rs, value, word)
    elif (opcode == 6):
        blez(rs, value, word)
    elif (opcode == 5):
        bne(rs, rt, value, word)
    elif (opcode == 32):
        lb(rs, rt, value, word)
    elif (opcode == 15):
        lui(rt, value, word)
    elif (opcode == 35):
        lw(rs, rt, value, word)
    elif (opcode == 53):
        ldc1(rs, rt, value, word)
    elif (opcode == 49):
        lwc1(rs, rt, value, word)
    elif (opcode == 13):
        ori(rs, rt, value, word)
    elif (opcode == 10):
        slti(rs, rt, value, word)
    elif (opcode == 43):
        sw(rs, rt, value, word)
    elif (opcode == 57):
        swc1(rs, rt, value, word)

    # Incrementa o valor de pc em 4 para seguir para a próxima palavra
    pc = pc + 4 

    # Incrementa a contagem de instruções
    iCount += 1

# J-format
#  op   |  endereco
# 6bits |   26bits

def jType(opcode, word):
    global pc, jCount, opr, mode, file

    # Escrita no arquivo minips.trace
    if (opr > 1 and mode == 1):
        writeFile(file, opr, mode, 'I', pc)

    address = word & 0x03ffffff

    if (opcode == 2):
        j(address, word)
    elif (opcode == 3):
        jal(address, word)

    # Incrementa o valor de pc em 4 para seguir para a próxima palavra
    pc = pc + 4

    # Incrementa a contagem de instruções
    jCount += 1

# FR-format
#  opcode |  fmt  |   ft  |   fs  |   fd  | funct
#  6 bits | 5bits | 5bits | 5bits | 5bits | 6bits

# FI-format
#  opcode |   fmt  |   ft   |   constante ou endereco (valor)
#   6bits |  5bits |  5bits |          16bits


def floatingPointType(opcode, word):
    global pc, frCount, fiCount, opr, mode, file

    # Escrita no arquivo minips.trace
    if (opr > 1 and mode == 1):
        writeFile(file, opr, mode, 'I', pc)

    fiInstruction = False

    if (opcode == 17):
        # Instruções move
        m = word >> 21 & 0x1f
        rt = word >> 16 & 0x1f
        fs = word >> 11 & 0x1f
        value1 = word & 0x7ff

        # instruções fmt
        fmt = word >> 21 & 0x1f
        # 0/ft
        value2 = word >> 16 & 0x1f
        fs = word >> 11 & 0x1f
        fd = word >> 6 & 0x1f
        # add/cvt.d/cvt.s/div/mov/mult
        value3 = word & 0x3f

        # instruções branch
        nd = word >> 17 & 0x1
        tf = word >> 16 & 0x1
        offset = word & 0xffff

        if (fmt == 8 and nd == 0 and tf == 0):
            bc1f(offset, word)
            fiInstruction = True
        elif (fmt == 8 and nd == 0 and tf == 1):
            bc1t(offset, word)
            fiInstruction = True
        elif (fmt == 17 and value3 == 0):
            addD(value2, fs, fd, word)
        elif (fmt == 16 and value3 == 0):
            addS(value2, fs, fd, word)
        elif (fmt == 16 and value3 == 60):
            cltS(value2, fs, word)
        elif (fmt == 17 and value2 == 0 and value3 == 32):
            cvtSD(fs, fd, word)
        elif (fmt == 20 and value2 == 0 and value3 == 33):
            cvtDW(fs, fd, word)
        elif (fmt == 17 and value3 == 3):
            divD(value2, fs, fd, word)
        elif (fmt == 16 and value3 == 3):
            divS(value2, fs, fd, word)
        elif (fmt == 17 and value2 == 0 and value3 == 6):
            movD(fs, fd, word)
        elif (fmt == 16 and value2 == 0 and value3 == 6):
            movS(fs, fd, word)
        elif (fmt == 17 and value3 == 2):
            mulD(value2, fs, fd, word)
        elif (fmt == 16 and value3 == 2):
            mulS(value2, fs, fd, word)
        elif (m == 0 and value1 == 0):
            mfc1(rt, fs, word)
        elif (m == 4 and value1 == 0):
            mtc1(rt, fs, word)
        elif (fmt == 16 and value3 == 1):
            subS(value2, fs, fd, word)

    # Incrementa o valor de pc em 4 para seguir para a próxima palavra
    pc = pc + 4

    # Incrementa a contagem de instruções
    if (fiInstruction):
        fiCount += 1
    else:
        frCount += 1

# Identificador de Instruções ---------------------------

def instructionFinder(word):
    global pc, pcBD, registers, iC, iCBD, delay, hi, lo, mode, cycles
    
    # Contabilização de acesso
    if (mode == 1):
        memoryAccess()

    if (word < 0):
        word = int(int2hex(word, 32), 16)
    else:
        word = twoComplement(word, 32)
    opcode = word >> 26

    # Ins - Debug
    # print('\n')
    # print(hex(word)) 
    # print("R:", registers) 
    # print("RFP:", registersFP)
    # print(f'HI: {hi}', f'LO: {lo}')
    # print(f'CC: {cc}')
    # print(f'Cycles: {100}, (total: {cycles})')
    # print("OPC:", opcode)

    if (opcode == 0):
        rType(word)
    elif (opcode == 2 or opcode == 3):
        jType(opcode, word)
    elif (opcode >= 16 and opcode < 20):
        floatingPointType(opcode, word)
    else:
        iType(opcode, word)

    if (delay and iCBD + 1 == iC):
        pc = pcBD + 4
        delay = False

    # Incrementa a contagem de instruções e ciclos
    iC += 1
    
    if (mode == 1):
        cycles += 1
    elif (mode >= 2):
        cache.cycles += 1

# Funções base ----------------------

def registerInitialization():
    registers = [0x00000000] * 32
    registers[28] = 0x10008000
    registers[29] = 0x7fffeffc
    return registers

def registerFPInitialization():
    registers = [0x00000000] * 32
    return registers

def memoryInitialization(pc, size):
    return dict.fromkeys(range(pc, pc + size), 0)

def readLittleEndian(data):
    value = struct.unpack("<i", bytearray(data))[0]
    return(hex(value))

def storeInMemory(file, index):
    global memory

    instruction = file.read(1)
    textStart = index
    while instruction:
        memory[textStart] = instruction
        instruction = file.read(1)
        textStart += 1
    textEnd = textStart

    return textEnd

# Operações -------------------------

# Contém condições adicionais para tratar os modos 'trace' e 'debug'
def run():
    global execute, memory, opr, mode, startTime, endTime

    startTime = time.time()
    if (mode == 1):
        while execute:
            i = pc
            data = [memory.get(i, 0), memory.get(i + 1, 0), memory.get(i + 2, 0), memory.get(i + 3, 0)]
            data = b''.join(data)
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    elif (mode == 2):
        while execute:
            i = pc
            data = cache.getWordL1Unif(i, 'I')
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    elif (mode == 3 or mode == 4):
        while execute:
            i = pc
            data = cache.getWordL1Split(i, 0, 'I')
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    
    endTime = time.time()
    
def traceDebug():
    global execute, memory, opr, startTime, endTime, file

    startTime = 0

    if (mode == 1):
        file = open("./files/minips.trace", "w+")
        
        startTime = time.time()
        while execute:
            i = pc
            data = [memory.get(i, 0), memory.get(i + 1, 0), memory.get(i + 2, 0), memory.get(i + 3, 0)]
            data = b''.join(data)
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    elif (mode == 2):
        cache.file = open("./files/minips.trace", "w+")
        
        startTime = time.time()
        while execute:
            i = pc
            data = cache.getWordL1Unif(i, 'I')
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    elif (mode == 3 or mode == 4):
        cache.file = open("./files/minips.trace", "w+")

        startTime = time.time()
        while execute:
            i = pc
            data = cache.getWordL1Split(i, 0, 'I')
            instruction = int(readLittleEndian(data), 16)
            instructionFinder(instruction)
    
    endTime = time.time()

    if (mode == 1):
        file.close()
    elif (mode >= 2):
        cache.file.close()

def decode(memory, pc, textEnd):
    i = pc
    while i < textEnd:
        data = [memory.get(i, 0), memory.get(i + 1, 0), memory.get(i + 2, 0), memory.get(i + 3, 0)]
        data = b''.join(data)
        instruction = int(readLittleEndian(data), 16)
        instructionFinder(instruction)
        i += 4
    print()

# Main ------------------------------

def main():
    global execute, mode, opr, memory, registers, registersFP, pc, iC, iCount, rCount, jCount, frCount, fiCount, startTime, endTime, cycles, hits, misses

    rodataPresent = False

    # Definição do modo de operação (opr = [0, 3])
    operation = input("Your operation (run/decode/trace/debug): ")
    if (operation != "decode" and operation != "run" and operation != "trace" and operation != "debug"):
        print("Please select one of the options above!")
        return

    elif (operation == "decode"):
        opr = 1
    else:
        if (operation == "trace"):
            opr = 2
        elif (operation == "debug"):
            opr = 3
        
        # Definição do modo de configuração de memória
        mode = int(input("Select memory configuration (1/2/3/4/5/6): "))
        if (mode < 1 or mode > 6):
            print("Please select one of the options above!")
            return

    # Arquivo de entrada
    filename = input("Your file: ")
    
    # Inicialização dos registradores
    registers = registerInitialization()
    registersFP = registerFPInitialization()

    size1 = size2 = size3 = 0

    # Leitura dos arquivos
    textFile = open(f'./files/{filename}.text', "rb")
    dataFile = open(f'./files/{filename}.data', "rb")
    rodataFile = None

    if (os.path.isfile(f'./files/{filename}.rodata')):
        rodataPresent = True
    
    if (rodataPresent):
        rodataFile = open(f'./files/{filename}.rodata', "rb")
        size3 = len(rodataFile.read())

    # Definição de tamanho a ser reservado
    size1 = len(textFile.read())
    size2 = len(dataFile.read())

    # Inicializando memória com 0s
    if (mode == 1):
        memory = memoryInitialization(pc, size1 + size2 + size3)
    elif (mode >= 2):
        cache.opr = opr
        cache.mode = mode
        cache.initializeMemory(pc, size1 + size2 + size3)

        if (mode == 2):
            cache.initializeL1Unif()
        elif (mode == 3 or mode == 4):
            cache.initializeL1Split()

    # Retornando ao início dos arquivos
    textFile.seek(0)
    dataFile.seek(0)
    if (rodataPresent):
        rodataFile.seek(0)

    # Armazenando as seções de texto e dados na memória
    textEnd = 0
    dataEnd = 0
    rodataEnd = 0
    if (mode == 1):
        textEnd = storeInMemory(textFile, pc)
        dataEnd = storeInMemory(dataFile, 0x10010000)
        if (rodataPresent):
            rodataEnd = storeInMemory(rodataFile, 0x00800000)
    elif (mode >= 2):
        textEnd = cache.storeInMemory(textFile, pc)
        dataEnd = cache.storeInMemory(dataFile, 0x10010000)
        if (rodataPresent):
            rodataEnd = cache.storeInMemory(rodataFile, 0x00800000)

    if (opr == 1):
        decode(memory, pc, textEnd)
    else:
        if (opr == 0):
            run()
        else:
            traceDebug()

        printStats(iC, iCount, rCount, jCount, frCount, fiCount, startTime, endTime)
        
        if (mode == 1):
            printSimulatedExecutionTimes(iC, cycles)
            printMemoryInformation(hits, misses)
        elif (mode == 2):
            printSimulatedExecutionTimes(iC, cache.cycles)
            printMemoryInformation2(cache.hitsL1, cache.missesL1, cache.hitsMem, cache.missesMem)
        elif (mode == 3 or mode == 4):
            printSimulatedExecutionTimes(iC, cache.cycles)
            printMemoryInformation34(cache.hitsL1i, cache.missesL1i, cache.hitsL1d, cache.missesL1d, cache.hitsMem, cache.missesMem)
            
main()