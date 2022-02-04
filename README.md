### Simulador MIPS em Python - Fase III
O programa foi desenvolvido com a versão 3.8.5 do Python instalada no sistema operacional Linux, distro Ubuntu 20.04. 
Inclui o uso da biblioteca <a href="https://numpy.org/install/">Numpy</a>, instalada usando o instalador de pacotes <a href="https://pip.pypa.io/en/stable/installing/">pip<a/>.

Após ter o pip instalado, inserir o comando no terminal:

```
$ pip install numpy
```

Para executar o simulador, basta abrir o terminal no diretório e inserir o comando

```
$ python3 ./minips.py
```

Deve ser escolhido o modo de operação como indicado, a configuração de memória (1 a 4 implementadas) e ser digitado o título do arquivo correspondente, sem extensão. Como exemplo:

```
$ python3 ./minips.py
Your operation (run/decode/trace/debug): run
Select memory configuration (1/2/3/4/5/6): 2    
Your file: 17.rng
```

A execução dos modos de operação trace e debug gera o arquivo minips.trace no diretório ```/files```, contendo um log das operações de acesso à memória cache e RAM.
