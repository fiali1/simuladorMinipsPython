from os import write
import struct
import numpy as np

from cache import *

# Registradores (32)
# $zero     | 0
# $at       | 1
# $v0, $v1  | 2 - 3
# $a0...$a3 | 4 - 7
# $t0...$t7 | 8 - 15
# $s0...$s7 | 16 - 23
# $t8...$t9 | 24 - 25
# $k0, $k1  | 26 - 27
# $gp       | 28
# $sp       | 29
# $fp       | 30
# $ra       | 31

def registerTranslator(index):
    if index == 0:
        return "$zero"
    elif index == 1:
        return "$at"
    elif index == 2 or index == 3:
        return f"$v{index % 2}"
    elif index >= 4 and index <= 7:
        return f"$a{index % 4}"
    elif index >= 8 and index <= 15:
        return f"$t{index % 8}"
    elif index >= 16 and index <= 23:
        return f"$s{index % 16}"
    elif index == 24 or index == 25:
        return f"$t{index % 24 + 8}"
    elif index == 26 or index == 27:
        return f"$k{index % 26}"
    elif index == 28:
        return "$gp"
    elif index == 29:
        return "$sp"
    elif index == 30:
        return "$fp"
    elif index == 31:
        return "$ra"
    else:
        return -1

# Registradores ponto flutuante (32)
# $f0...$f31 | 0 - 31

def registerFloatTranslator(index):
    if index >= 0 and index <= 31:
        return f"$f{index}"
    else:
        return -1

# Registradores hi e lo
# hi | 0 
# lo | 1

def registerSpecificTranslator(index):
    if index == 0:
        return "hi"
    elif index == 1:
        return "lo"
    else:
        return -1

# Funções auxiliares ------------------------------

# https://stackoverflow.com/questions/32030412/twos-complement-sign-extension-python
def sign_extend(value, bits):
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

# https://stackoverflow.com/questions/1604464/twos-complement-in-python
def twoComplement(val, bits):
    if (val & (1 << (bits - 1))) != 0: 
        val = val - (1 << bits)       
    return val  

# https://stackoverflow.com/questions/43358620/get-the-hex-of-2s-complement-for-negative-numbers
def int2hex(number, bits):
    if number < 0:
        return hex((1 << bits) + number)
    else:
        return hex(number)

# Função dedicada a conferir entradas negativas do usuário
def userInput(value):
    value = int2hex(value, 32)
    value = int(value, 16)
    return value

# https://stackoverflow.com/questions/16444726/binary-representation-of-float-in-python-bits-not-hex
# Função para converter entrada para binário
def float_to_bin(num, bits):
    if (bits == 32):
        return ''.join('{:0>8b}'.format(c) for c in struct.pack('!f', num))
    else:
        return ''.join('{:0>8b}'.format(c) for c in struct.pack('!d', num))

# Soma mantissa
def sumBits(n, length):
    sum = 1;
    
    i = length
    
    while (n):
        if (n & 1 == 1):
            sum += pow(2, -i)
        n >>= 1;
        i -= 1

    return sum;

# Função para calcular float/double de binário na raça (agora sem strings! (nessa parte, pelo menos))
def convertToFloatDouble(binary, length):
    if (length == 32):
        signal = binary >> 31
        exponent = binary >> 23 & 0xff
        mantissa = binary & 0x7fffff
        sumM = sumBits(mantissa, 23)
    else:
        signal = binary >> 63
        exponent = binary >> 52 & 0x7ff
        mantissa = binary & 0xfffffffffffff
        sumM = sumBits(mantissa, 52)

    if (length == 32):
        exponent = exponent -  127
    else:
        exponent = exponent -  1023

    value = pow(-1, signal) * sumM * pow(2, exponent)

    if (length == 32):
        value = np.float32(value)
    else:
        value = np.double(value)

    return value


# Impressor de instruções -------------------------
def printer(pc, word, content):
    print((f"{'{0:08X}'.format(pc)}:\t{'{0:08X}'.format(word)}\t{content}").lower())

# Impressor de estatísticas de execução -----------
def printStats(iC, iCount, rCount, jCount, frCount, fiCount, startTime, endTime):
    simTime = endTime - startTime
    avgIps = iC / simTime

    formatStart = '\033[94m'
    formatEnd = '\033[0m'

    print(formatStart + f"Instruction count: {iC} (R: {rCount} I: {iCount} J: {jCount} FR: {frCount} FI: {fiCount})" + formatEnd)
    print(formatStart + f"Simulation Time: {'%.2f' % round(simTime, 2)} sec." + formatEnd)
    print(formatStart + f"Average IPS: {'%.2f' % round(avgIps, 2)}" + formatEnd)
    print("\n")

# Impressor de simulação monociclo/pipeline -------
def printSimulatedExecutionTimes(iC, cycles):
    frequencyP = 33.8688
    frequencyM = frequencyP / 4
    
    cyclesM = cycles
    cyclesP = cyclesM + 4

    eTimeM = cyclesM / (frequencyM * 10**6)
    ipcM = iC / cyclesM
    mipsM = iC / eTimeM / 10**6

    eTimeP = cyclesP / (frequencyP * 10**6)
    ipcP = iC / cyclesP
    mipsP = iC / eTimeP / 10**6
    
    formatStart = '\033[94m'
    formatEnd = '\033[0m'
    print(formatStart + f"Simulated Execution Times for:" + formatEnd)
    print(formatStart + f"------------------------------" + formatEnd)
    print(formatStart + f"Monocycle" + formatEnd)
    print(formatStart + f"\tCycles: {cyclesM}" + formatEnd)
    print(formatStart + f"\tFrequency: {frequencyM} MHz" + formatEnd)
    print(formatStart + f"\tEstimated execution time: {'%.4f' % round(eTimeM, 4)} sec." + formatEnd)
    print(formatStart + f"\tIPC: {'%.2f' % round(ipcM, 2)}" + formatEnd)
    print(formatStart + f"\tMIPS: {'%.2f' % round(mipsM, 2)}" + formatEnd)

    print(formatStart + f"Pipelined" + formatEnd)
    print(formatStart + f"\tCycles: {cyclesP}" + formatEnd)
    print(formatStart + f"\tFrequency: {frequencyP} MHz" + formatEnd)
    print(formatStart + f"\tEstimated execution time: {'%.4f' % round(eTimeP, 4)} sec." + formatEnd)
    print(formatStart + f"\tIPC: {'%.2f' % round(ipcP, 2)}" + formatEnd)
    print(formatStart + f"\tMIPS: {'%.2f' % round(mipsP, 2)}" + formatEnd)
    print(formatStart + f"Speedup Monocycle/Pipeline: {'%.2f' % round(eTimeM / eTimeP, 2)}x" + formatEnd)

    print("\n")

# Impressor de estatísticas de memória ------------
def printMemoryInformation(hits, misses):    
    total = hits + misses
    missRate = 100 * (misses / total)
    
    formatStart = '\033[94m'
    formatEnd = '\033[0m'
    
    print(formatStart + f"Memory Information:" + formatEnd)
    print(formatStart + f"-------------------" + formatEnd)
    print(formatStart + f"Level  Hits      Misses    Total     Miss Rate" + formatEnd)
    print(formatStart + f"-----  --------  --------  --------  ---------" + formatEnd)
    print(formatStart + f"  RAM  {'%8s' % hits}  {'%8s' % misses}  {'%8s' % total}  {'%8s' % ('%.2f' % round(missRate, 2))}%" + formatEnd)

def printMemoryInformation2(hitsL1, missesL1, hitsMem, missesMem):    
    totalL1 = hitsL1 + missesL1
    missRateL1 = 100 * (missesL1 / totalL1)

    totalMem = hitsMem + missesMem
    missRateMem = 100 * (missesMem / totalMem)
    
    formatStart = '\033[94m'
    formatEnd = '\033[0m'
    
    print(formatStart + f"Memory Information:" + formatEnd)
    print(formatStart + f"-------------------" + formatEnd)
    print(formatStart + f"Level  Hits      Misses    Total     Miss Rate" + formatEnd)
    print(formatStart + f"-----  --------  --------  --------  ---------" + formatEnd)
    print(formatStart + f"   L1  {'%8s' % hitsL1}  {'%8s' % missesL1}  {'%8s' % totalL1}  {'%8s' % ('%.2f' % round(missRateL1, 2))}%" + formatEnd)
    print(formatStart + f"  RAM  {'%8s' % hitsMem}  {'%8s' % missesMem}  {'%8s' % totalMem}  {'%8s' % ('%.2f' % round(missRateMem, 2))}%" + formatEnd)

def printMemoryInformation34(hitsL1i, missesL1i, hitsL1d, missesL1d, hitsMem, missesMem):    
    totalL1i = hitsL1i + missesL1i
    missRateL1i = 0
    if (totalL1i != 0):
        missRateL1i = 100 * (missesL1i / totalL1i)

    totalL1d = hitsL1d + missesL1d
    missRateL1d = 0
    if (totalL1d != 0):
        missRateL1d = 100 * (missesL1d / totalL1d)

    totalMem = hitsMem + missesMem
    missRateMem = 100 * (missesMem / totalMem)
    
    formatStart = '\033[94m'
    formatEnd = '\033[0m'
    
    print(formatStart + f"Memory Information:" + formatEnd)
    print(formatStart + f"-------------------" + formatEnd)
    print(formatStart + f"Level  Hits      Misses    Total     Miss Rate" + formatEnd)
    print(formatStart + f"-----  --------  --------  --------  ---------" + formatEnd)
    print(formatStart + f"  L1i  {'%8s' % hitsL1i}  {'%8s' % missesL1i}  {'%8s' % totalL1i}  {'%8s' % ('%.2f' % round(missRateL1i, 2))}%" + formatEnd)
    print(formatStart + f"  L1d  {'%8s' % hitsL1d}  {'%8s' % missesL1d}  {'%8s' % totalL1d}  {'%8s' % ('%.2f' % round(missRateL1d, 2))}%" + formatEnd)
    print(formatStart + f"  RAM  {'%8s' % hitsMem}  {'%8s' % missesMem}  {'%8s' % totalMem}  {'%8s' % ('%.2f' % round(missRateMem, 2))}%" + formatEnd)

# Impressor de debug/trace ------------
def writeFile(file, opr, mode, flag, value):

    # print(file, opr, mode, flag, value, int(value / 32))

    if (mode == 1):
        file.write(f"{flag} 0x{value:08x} (line# 0x{int(value / 32):08x}) \n")
        if (opr == 3):
            if (flag == 'I' or flag == 'R'):
                file.write(f"\tRAM: read line# 0x{int(value / 32):08x} \n")
            elif (flag == 'W'):
                file.write(f"\tRAM: write: 0x{int(value / 32):08x} \n")
            file.write("\tRAM: Hit\n")

 # Impressor de debug/trace ------------
def writeFileCache(file, opr, mode, flag, address, item, miss, replacement, writeBack):
    # Contei com a ajuda do colega Rodrigo Rominho Mayer para debugar um problema na impressão do arquivo minips.trace
    # na função debug, no qual a linha de write back estava sendo exibida com um valor incorreto
    
    index = address >> 5 & 0x1f

    if (mode == 2):
        file.write(f"{flag} 0x{address:08x} (line# 0x{int(address / 32):08x}) \n")
        if (opr == 3):
            if (flag == 'I' or flag == 'R'):
                file.write(f"\tL1: read line# 0x{int(address / 32):08x} \n")
                if (miss):
                    file.write(f"\tL1: Miss \n")
                    file.write(f"\t\tRAM: read line# 0x{int(address / 32):08x} \n")
                    file.write("\t\tRAM: Hit\n")
                    file.write(f"\tL1: Replace to include line# 0x{int(address / 32):08x} \n")
                    file.write(f"\tL1: Random replacement policy. Way#{replacement} \n")
                    if (writeBack):
                        file.write(f"\tL1: Writing back line: 0x{int(item[1] << 5 | index):08x} \n")
                        file.write(f"\t\tRAM: write: 0x{int(item[1] << 5 | index):08x} \n")
                        file.write("\t\tRAM: Hit\n")
                    else:
                        file.write(f"\tL1: Line clean/invalid. No need to write back. \n")
                else:
                    file.write(f"\tL1: Hit \n")

            elif (flag == 'W'):
                file.write(f"\tL1: write: 0x{int(address / 32):08x} \n")
                if (miss):
                    file.write(f"\tL1: Miss \n")
                    file.write(f"\t\tRAM: read line# 0x{int(address / 32):08x} \n")
                    file.write("\t\tRAM: Hit\n")
                    file.write(f"\tL1: Replace to include line# 0x{int(address / 32):08x} \n")
                    file.write(f"\tL1: Random replacement policy. Way#{replacement} \n")
                    if (writeBack):
                        file.write(f"\tL1: Writing back line: 0x{int(item[1] << 5 | index):08x} \n")
                        file.write(f"\t\tRAM: write: 0x{int(item[1] << 5 | index):08x} \n")
                        file.write("\t\tRAM: Hit\n")
                    else:
                        file.write(f"\tL1: Line clean/invalid. No need to write back. \n")
                else:
                    file.write(f"\tL1: Hit \n")
                    file.write(f"\tL1: updating line# 0x{int(address / 32):08x} \n")

def writeFileSplitCache(file, opr, mode, set, flag, address, item, miss, replacement, writeBack, lineFound = False, invalidating = False):
    index = address >> 5 & 0xf

    side1 = ""
    side2 = ""

    if (set == 0):
        side1 = "L1i"
        side2 = "L1d"
    elif (set == 1):
        side1 = "L1d"
        side2 = "L1i"

    if (mode == 3 or mode == 4):
        file.write(f"{flag} 0x{address:08x} (line# 0x{int(address / 32):08x}) \n")
        if (opr == 3):
            if (flag == 'I' or flag == 'R'):
                file.write(f"\t{side1}: read line# 0x{int(address / 32):08x} \n")
                if (miss):
                    file.write(f"\t{side1}: Miss \n")
                    if (lineFound and set == 0):
                        file.write(f"\t{side1}: Line found on L1d \n")
                    elif (lineFound and set == 1):
                        file.write(f"\t{side1}: Line found on L1i \n")
                    else:
                        file.write(f"\t\tRAM: read line# 0x{int(address / 32):08x} \n")
                        file.write("\t\tRAM: Hit\n")
                    file.write(f"\t{side1}: Replace to include line# 0x{int(address / 32):08x} \n")
                    if (mode < 4):
                        file.write(f"\t{side1}: Random replacement policy. Way#{replacement} \n")
                    else:
                        file.write(f"\t{side1}: LRU replacement policy. Way#{replacement} \n")
                    if (writeBack):
                        file.write(f"\t{side1}: Writing back line: 0x{int(item[1] << 4 | index):08x} \n")
                        file.write(f"\t\tRAM: write: 0x{int(item[1] << 4 | index):08x} \n")
                        file.write("\t\tRAM: Hit\n")
                    else:
                        file.write(f"\t{side1}: Line clean/invalid. No need to write back. \n")
                else:
                    file.write(f"\t{side1}: Hit \n")

            elif (flag == 'W'):
                file.write(f"\t{side1}: write: 0x{int(address / 32):08x} \n")
                if (miss):
                    file.write(f"\t{side1}: Miss \n")
                    file.write(f"\t\tRAM: read line# 0x{int(address / 32):08x} \n")
                    file.write("\t\tRAM: Hit\n")
                    file.write(f"\t{side1}: Replace to include line# 0x{int(address / 32):08x} \n")
                    if (mode < 4):
                        file.write(f"\t{side1}: Random replacement policy. Way#{replacement} \n")
                    else:
                        file.write(f"\t{side1}: LRU replacement policy. Way#{replacement} \n")
                    if (writeBack):
                        file.write(f"\t{side1}: Writing back line: 0x{int(item[1] << 4 | index):08x} \n")
                        file.write(f"\t\tRAM: write: 0x{int(item[1] << 4 | index):08x} \n")
                        file.write("\t\tRAM: Hit\n")
                    else:
                        file.write(f"\t{side1}: Line clean/invalid. No need to write back. \n")
                else:
                    file.write(f"\t{side1}: Hit \n")
                    file.write(f"\t{side1}: updating line# 0x{int(address / 32):08x} \n")
                    if (invalidating):
                        file.write(f"\t{side2}: invalidating line 0x{int(address / 32):08x} \n")
