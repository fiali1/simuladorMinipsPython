import random

from tools import writeFileCache, writeFileSplitCache

class cache:
    file = None
    opr = 0
    mode = 0

    memory = {}
    hitsMem = 0
    missesMem = 0

    l1 = {}
    hitsL1 = 0
    missesL1 = 0


    l1i = {}
    hitsL1i = 0
    missesL1i = 0

    l1d = {}
    hitsL1d = 0
    missesL1d = 0

    l2 = {}
    hitsL2 = 0
    missesL2 = 0

    cycles = 0

    # Memória
    def initializeMemory(pc, size):
        cache.memory = dict.fromkeys(range(pc, pc + size), 0)

    def storeInMemory(file, index):
        cache.memory

        instruction = file.read(1)
        textStart = index
        while instruction:
            cache.memory[textStart] = instruction
            instruction = file.read(1)
            textStart += 1
        textEnd = textStart

        return textEnd

    def randomReplacement(ways):
        way = random.randint(0, ways)
        return way

    def lruReplacement(ways, set, index):
        way = 0
        if (ways != 0):
            # Identifica o way com menos usos com busca sequencial
            # nas configurações 4-way e 8-way
            target = None
            if (set == 0):
                target = cache.l1i
            else: 
                target = cache.l1d
            i = 1
            while i < ways - 1:
                if (target[way][index][3] > target[i][index][3]):
                    way = i
                i += 1
        
        return way

    # L1 - bool: validade, int: tag, bool: clean(F)/dirty(T), byte[]: [dados]
    def initializeL1Unif():
        cache.l1 = dict.fromkeys(range(32), (False, 0, False, 0))

    # int: address, 
    # char: flag ['R', 'I'], 
    # bool: single byte (T), full word (F), 
    # int: operation [0: Junção de dados embutida, 1: Junção omitida]
    def getWordL1Unif(address, flag, single = False, operation = 0):
        offset = address & 0x1f
        index = address >> 5 & 0x1f
        tag = address >> 10

        target = cache.l1.get(index)

        # Miss por linha inválida
        if (target[0] == False):
            replacement = cache.randomReplacement(0)

            if (cache.opr > 1):
                writeFileCache(cache.file, cache.opr, cache.mode, flag, address, target, True, replacement, False)

            # Leitura da linha completa
            line = []
            i = 0
            for i in range(32):
                data = cache.memory.get(address - (address % 32) + i, b'\x00')
                line.append(data)
            cache.l1[index] = (True, tag, False, line)

            # Acesso RAM
            cache.missesL1 += 1
            cache.hitsMem += 1
        
        elif (target[0] == True):
            # Tags coincidem (Hit confirmado)
            if (target[1] == tag):
                if (cache.opr > 1):
                    writeFileCache(cache.file, cache.opr, cache.mode, flag, address, target, False, 0, False)

                # Acesso L1
                cache.cycles += 1
                cache.hitsL1 += 1
                
                # Retorna byte único na instrução 'lb'
                if (single):
                    return cache.l1[index][3][offset]

                # Junção de 4 bytes
                data = [
                    cache.l1[index][3][offset],
                    cache.l1[index][3][offset + 1],
                    cache.l1[index][3][offset + 2],
                    cache.l1[index][3][offset + 3]]
                
                if (operation == 0):
                    data = b''.join(data)
                
                return data

            # Tags diferentes (Miss por tag incorreta)
            else:
                replacement = cache.randomReplacement(0)
                writeBack = False

                # Write back
                if (target[2] == True):
                    baseAddress = (cache.l1[index][1] << 5 | index) * 32

                    writeBack = True

                    for i in range(32):
                        cache.memory[baseAddress + i] = cache.l1[index][3][i]

                    # Acesso RAM
                    cache.hitsMem += 1
                    cache.cycles += 100

                # Leitura da linha completa
                line = []
                i = 0
                for i in range(32):
                    data = cache.memory.get(address - (address % 32) + i)
                    line.append(data)
                cache.l1[index] = (True, tag, False, line)

                if (cache.opr > 1):
                    writeFileCache(cache.file, cache.opr, cache.mode, flag, address, target, True, replacement, writeBack)

                # Acesso RAM
                cache.missesL1 += 1
                cache.hitsMem += 1

        # Acesso L1 + RAM no caso de MISS
        cache.cycles += 101
        
        # Retorna byte único na instrução 'lb'
        if (single):
            return cache.l1[index][3][offset]

        # Junção de 4 bytes
        data = [
            cache.l1[index][3][offset],
            cache.l1[index][3][offset + 1],
            cache.l1[index][3][offset + 2],
            cache.l1[index][3][offset + 3]]
        
        if (operation == 0):
            data = b''.join(data)    

        return data
    
    def storeWordL1Unif(address, receivedData):
        offset = address & 0x1f
        index = address >> 5 & 0x1f
        tag = address >> 10

        target = cache.l1.get(index)

        # Miss por linha inválida
        if (target[0] == False):
            replacement = cache.randomReplacement(0)

            if (cache.opr > 1):
                writeFileCache(cache.file, cache.opr, cache.mode, 'W', address, target, True, replacement, False)

            # Leitura da linha completa
            line = []
            i = 0
            for i in range(32):
                data = cache.memory.get(address - (address % 32) + i, b'\x00')
                line.append(data)
            
            # Carregando e substituindo linha
            cache.l1[index] = (True, tag, True, line)
            cache.l1[index][3][offset] =  receivedData[0]
            cache.l1[index][3][offset + 1] = receivedData[1]
            cache.l1[index][3][offset + 2] = receivedData[2]
            cache.l1[index][3][offset + 3] = receivedData[3]

            # Acessos
            cache.missesL1 += 1
            cache.hitsMem += 1
        
        elif (target[0] == True):
            # Tags coincidem (Hit confirmado)
            if (target[1] == tag):
                if (cache.opr > 1):
                    writeFileCache(cache.file, cache.opr, cache.mode, 'W', address, target, False, 0, False)

                # Acesso L1
                cache.cycles += 1
                cache.hitsL1 += 1

                # Substituição da palavra
                cache.l1[index][3][offset] =  receivedData[0]
                cache.l1[index][3][offset + 1] = receivedData[1]
                cache.l1[index][3][offset + 2] = receivedData[2]
                cache.l1[index][3][offset + 3] = receivedData[3]

                # Marcação da linha como dirty
                cache.l1[index] = (cache.l1[index][0], cache.l1[index][1], True, cache.l1[index][3])

                return

            # Tags diferentes (Miss por tag incorreta)
            else:
                replacement = cache.randomReplacement(0)
                writeBack = False

                # Write back
                if (target[2] == True):
                    baseAddress = (cache.l1[index][1] << 5 | index) * 32

                    writeBack = True

                    for i in range(32):
                        cache.memory[baseAddress + i] = cache.l1[index][3][i]

                    # Acesso RAM
                    cache.hitsMem += 1
                    cache.cycles += 100
                

                # Leitura da linha completa
                line = []
                i = 0
                for i in range(32):
                    data = cache.memory.get(address - (address % 32) + i)
                    line.append(data)
                
                # Substituição de palavra na linha
                cache.l1[index] = (True, tag, True, line)
                cache.l1[index][3][offset] =  receivedData[0]
                cache.l1[index][3][offset + 1] = receivedData[1]
                cache.l1[index][3][offset + 2] = receivedData[2]
                cache.l1[index][3][offset + 3] = receivedData[3]
                
                if (cache.opr > 1):
                    writeFileCache(cache.file, cache.opr, cache.mode, 'W', address, target, True, replacement, writeBack)

                cache.missesL1 += 1
                cache.hitsMem += 1

        # Acesso L1 + RAM
        cache.cycles += 101

    # L1i/L1d - (bool: validade, int: estado [0 - Modificado, 1 - Exclusivo, 2 - Compartilhado, 3 - Inválido) - 3], int: tag, byte[]: [dados])

    def initializeL1Split():
        cache.l1i = dict.fromkeys(range(16), (3, 0, 0))
        cache.l1d = dict.fromkeys(range(16), (3, 0, 0))
    
    # int: address, 
    # int: set [0 - instruções , 1 - dados], 
    # char: flag ['R', 'I'], 
    # bool: single byte (T), full word (F), 
    # int: operation [0: Junção de dados embutida, 1: Junção omitida]
    def getWordL1Split(address, set, flag, single = False, operation = 0):
        offset = address & 0x1f
        index = address >> 5 & 0xf
        tag = address >> 9

        if (set == 0):
            target = cache.l1i.get(index)
        elif (set == 1):
            target = cache.l1d.get(index)

        # Miss por linha inválida
        if (target[0] == 3):
            
            lineFound = False
            replacement = cache.randomReplacement(0)
                    
            line = []

            if ((set == 0 and not index in cache.l1d) or (set == 1 and not index in cache.l1i)):
                # Leitura da linha completa
                i = 0
                for i in range(32):
                    data = cache.memory.get(address - (address % 32) + i, b'\x00')
                    line.append(data)
                if (set == 0):
                    cache.l1i[index] = (1, tag, line)
                    cache.missesL1i += 1
                elif (set == 1):
                    cache.l1d[index] = (1, tag, line)
                    cache.missesL1d += 1
                
                # Acesso RAM
                cache.hitsMem += 1
                cache.cycles += 101
            else:
                if (set == 0 and (cache.l1d[index][1] << 4 | index) == (address >> 5)):
                    i = 0
                    cache.l1i[index] = cache.l1d[index]

                    # Atualizando a memória
                    if (cache.l1d[0] == 0):
                        baseAddress = (cache.l1d[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1d[index][2][i]
                        cache.hitsMem += 1
                        cache.cycles += 100

                    # Linhas passam a ser compartilhadas
                    cache.l1i[index] =  (2, cache.l1i[index][1], cache.l1i[index][2])
                    cache.l1d[index] =  (2, cache.l1d[index][1], cache.l1d[index][2])
                    cache.missesL1i += 1
                    # cache.hitsL1d += 1
                    cache.cycles += 1
                    lineFound = True
                elif (set == 1 and (cache.l1i[index][1] << 4 | index) == (address >> 5)):
                    i = 0
                    cache.l1d[index] = cache.l1i[index]

                    # Atualizando a memória
                    if (cache.l1i[0] == 0):
                        baseAddress = (cache.l1i[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1i[index][2][i]
                        cache.hitsMem += 1
                        cache.cycles += 100

                    # Linhas passam a ser compartilhadas
                    cache.l1d[index] =  (2, cache.l1d[index][1], cache.l1d[index][2])
                    cache.l1i[index] =  (2, cache.l1i[index][1], cache.l1i[index][2])
                    cache.missesL1d += 1
                    # cache.hitsL1i += 1
                    cache.cycles += 1
                    lineFound = True
                else:
                    i = 0
                    for i in range(32):
                        data = cache.memory.get(address - (address % 32) + i, b'\x00')
                        line.append(data)
                    if (set == 0):
                        cache.l1i[index] = (1, tag, line)
                        cache.missesL1i += 1
                    elif (set == 1):
                        cache.l1d[index] = (1, tag, line)
                        cache.missesL1d += 1
                    
                    # Acesso RAM
                    cache.hitsMem += 1
                    cache.cycles += 101

            if (cache.opr > 1):
                writeFileSplitCache(cache.file, cache.opr, cache.mode, set, flag, address, target, True, replacement, False, lineFound)
        
        elif (target[0] != 3):
            # Tags coincidem (Hit confirmado)
            if (target[1] == tag):
                if (cache.opr > 1):
                    writeFileSplitCache(cache.file, cache.opr, cache.mode, set, flag, address, target, False, 0, False)

                # Acesso L1
                if (set == 0):
                    cache.hitsL1i += 1
                if (set == 1):
                    cache.hitsL1d += 1
                
                cache.cycles += 1
                
                # Retorna byte único na instrução 'lb'
                if (single):
                    if (set == 0):
                        return cache.l1i[index][2][offset]
                    elif (set == 1):
                        return cache.l1d[index][2][offset]

                data = []

                # Junção de 4 bytes
                if (set == 0):
                    data = [
                        cache.l1i[index][2][offset],
                        cache.l1i[index][2][offset + 1],
                        cache.l1i[index][2][offset + 2],
                        cache.l1i[index][2][offset + 3]]
                elif (set == 1):
                    data = [
                        cache.l1d[index][2][offset],
                        cache.l1d[index][2][offset + 1],
                        cache.l1d[index][2][offset + 2],
                        cache.l1d[index][2][offset + 3]]
                
                if (operation == 0):
                    data = b''.join(data)
                
                return data

            # Tags diferentes (Miss por tag incorreta)
            else:
                if (cache.mode < 4):
                    replacement = cache.randomReplacement(0)
                elif (cache.mode >= 4):
                    replacement = cache.lruReplacement(0, set, index)
                
                lineFound = False
                writeBack = False

                # Write back se linha estiver modificada
                if (target[0] == 0):
                    baseAddress = 0
                    if (set == 0):
                        baseAddress = (cache.l1i[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1i[index][2][i]
                    elif (set == 1):
                        baseAddress = (cache.l1d[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1d[index][2][i]

                    writeBack = True

                    # Acesso RAM
                    cache.hitsMem += 1
                    cache.cycles += 100

                line = []

                if ((set == 0 and not index in cache.l1d) or (set == 1 and not index in cache.l1i)):
                    # Leitura da linha completa
                    i = 0
                    for i in range(32):
                        data = cache.memory.get(address - (address % 32) + i, b'\x00')
                        line.append(data)
                    if (set == 0):
                        cache.l1i[index] = (1, tag, line)
                        cache.missesL1i += 1
                    elif (set == 1):
                        cache.l1d[index] = (1, tag, line)
                        cache.missesL1d += 1
                        
                        # Acesso RAM
                        cache.hitsMem += 1
                        cache.cycles += 101

                else:
                    if (set == 0 and (cache.l1d[index][1] << 4 | index) == (address >> 5)):
                        i = 0
                        cache.l1i[index] = cache.l1d[index]
                        cache.l1i[index] =  (2, cache.l1i[index][1], cache.l1i[index][2])
                        cache.l1d[index] =  (2, cache.l1d[index][1], cache.l1d[index][2])
                        cache.missesL1i += 1
                        
                        cache.cycles += 1
                        lineFound = True
                    elif (set == 1 and (cache.l1i[index][1] << 4 | index) == (address >> 5)):
                        i = 0
                        cache.l1d[index] = cache.l1i[index]
                        cache.l1d[index] =  (2, cache.l1d[index][1], cache.l1d[index][2])
                        cache.l1i[index] =  (2, cache.l1i[index][1], cache.l1i[index][2])
                        cache.missesL1d += 1
                        
                        cache.cycles += 1
                        lineFound = True
                    else:
                        i = 0
                        for i in range(32):
                            data = cache.memory.get(address - (address % 32) + i, b'\x00')
                            line.append(data)
                        if (set == 0):
                            cache.l1i[index] = (1, tag, line)
                            cache.missesL1i += 1
                        elif (set == 1):
                            cache.l1d[index] = (1, tag, line)
                            cache.missesL1d += 1
                        
                        # Acesso RAM
                        cache.hitsMem += 1
                        cache.cycles += 101
                

                if (cache.opr > 1):
                    writeFileSplitCache(cache.file, cache.opr, cache.mode, set, flag, address, target, True, replacement, writeBack, lineFound)
        
        # Retorna byte único na instrução 'lb'
        if (single):
            if (set == 0):
                return cache.l1i[index][2][offset]
            elif (set == 1):
                return cache.l1d[index][2][offset]

        data = []

        # Junção de 4 bytes
        if (set == 0):
            data = [
                cache.l1i[index][2][offset],
                cache.l1i[index][2][offset + 1],
                cache.l1i[index][2][offset + 2],
                cache.l1i[index][2][offset + 3]]
        elif (set == 1):
            data = [
                cache.l1d[index][2][offset],
                cache.l1d[index][2][offset + 1],
                cache.l1d[index][2][offset + 2],
                cache.l1d[index][2][offset + 3]]

        if (operation == 0):
            data = b''.join(data)    

        return data
    
    def storeWordL1Split(address, set, receivedData):
        offset = address & 0x1f
        index = address >> 5 & 0xf
        tag = address >> 9

        if (set == 0):
            target = cache.l1i.get(index)
        elif (set == 1):
            target = cache.l1d.get(index)

        # Miss por linha inválida
        if (target[0] == 3):
            replacement = cache.randomReplacement(0)

            if (cache.opr > 1):
                writeFileSplitCache(cache.file, cache.opr, cache.mode, set, 'W', address, target, True, replacement, False)

            # Leitura da linha completa
            line = []
            i = 0
            for i in range(32):
                data = cache.memory.get(address - (address % 32) + i, b'\x00')
                line.append(data)
            
            # Carregando e substituindo linha
            if (set == 0):
                cache.l1i[index] = (0, tag, line)
                cache.l1i[index][2][offset] =  receivedData[0]
                cache.l1i[index][2][offset + 1] = receivedData[1]
                cache.l1i[index][2][offset + 2] = receivedData[2]
                cache.l1i[index][2][offset + 3] = receivedData[3]
                cache.missesL1i += 1
            elif (set == 1):
                cache.l1d[index] = (0, tag, line)
                cache.l1d[index][2][offset] =  receivedData[0]
                cache.l1d[index][2][offset + 1] = receivedData[1]
                cache.l1d[index][2][offset + 2] = receivedData[2]
                cache.l1d[index][2][offset + 3] = receivedData[3]
                cache.missesL1d += 1

            # Acessos
            cache.hitsMem += 1
            cache.cycles += 101
        
        elif (target[0] != 3):
            # Tags coincidem (Hit confirmado)
            if (target[1] == tag):
                invalidating = False

                # Acesso L1
                if (set == 0):
                    cache.hitsL1i += 1
                    # Substituição da palavra
                    cache.l1i[index][2][offset] =  receivedData[0]
                    cache.l1i[index][2][offset + 1] = receivedData[1]
                    cache.l1i[index][2][offset + 2] = receivedData[2]
                    cache.l1i[index][2][offset + 3] = receivedData[3]

                    # Invalidando linha
                    if (cache.l1i[index][0] == 2):
                        cache.l1d[index] = (3, 0, 0)
                        
                        invalidating = True
                elif (set == 1):
                    cache.hitsL1d += 1
                    # Substituição da palavra
                    cache.l1d[index][2][offset] =  receivedData[0]
                    cache.l1d[index][2][offset + 1] = receivedData[1]
                    cache.l1d[index][2][offset + 2] = receivedData[2]
                    cache.l1d[index][2][offset + 3] = receivedData[3]

                    # Invalidando linha
                    if (cache.l1d[index][0] == 2):
                        cache.l1i[index] = (3, 0, 0)
                        
                        invalidating = True

                if (cache.opr > 1):
                    writeFileSplitCache(cache.file, cache.opr, cache.mode, set, 'W', address, target, False, 0, False, False, invalidating)

                cache.cycles += 1
                
                # Marcação da linha como modificada
                if (set == 0):
                    cache.l1i[index] = (0, cache.l1i[index][1], cache.l1i[index][2])
                elif (set == 1):
                    cache.l1d[index] = (0, cache.l1d[index][1], cache.l1d[index][2])

                return

            # Tags diferentes (Miss por tag incorreta)
            else:
                if (cache.mode < 4):
                    replacement = cache.randomReplacement(0)
                elif (cache.mode >= 4):
                    replacement = cache.lruReplacement(0, set, index)
                writeBack = False

                # Write back se linha estiver modificada
                if (target[0] == 0):
                    baseAddress = 0

                    if (set == 0):
                        baseAddress = (cache.l1i[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1i[index][2][i]
                    elif (set == 1):
                        baseAddress = (cache.l1d[index][1] << 4 | index) * 32
                        for i in range(32):
                            cache.memory[baseAddress + i] = cache.l1d[index][2][i]

                    writeBack = True

                    # Acesso RAM
                    cache.hitsMem += 1
                    cache.cycles += 100

                # Leitura da linha completa
                line = []
                i = 0
                for i in range(32):
                    data = cache.memory.get(address - (address % 32) + i, b'\x00')
                    line.append(data)
                
                # Carregando e substituindo linha
                if (set == 0):
                    cache.l1i[index] = (0, tag, line)
                    cache.l1i[index][2][offset] =  receivedData[0]
                    cache.l1i[index][2][offset + 1] = receivedData[1]
                    cache.l1i[index][2][offset + 2] = receivedData[2]
                    cache.l1i[index][2][offset + 3] = receivedData[3]
                    cache.missesL1i += 1
                elif (set == 1):
                    cache.l1d[index] = (0, tag, line)
                    cache.l1d[index][2][offset] =  receivedData[0]
                    cache.l1d[index][2][offset + 1] = receivedData[1]
                    cache.l1d[index][2][offset + 2] = receivedData[2]
                    cache.l1d[index][2][offset + 3] = receivedData[3]
                    cache.missesL1d += 1
                
                # Acesso L1 + RAM
                cache.hitsMem += 1
                cache.cycles += 101

                if (cache.opr > 1):
                    writeFileSplitCache(cache.file, cache.opr, cache.mode, set, 'W', address, target, True, replacement, writeBack)
        

    # L2 - bool: validade, int: tag, byte[]: [dados]
    def initializeL2():
        for i in range(64):
            cache.l2[i] = (False, 0, False, 0)