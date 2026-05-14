# Especificacao Funcional

## 1) Objetivo e ambito
Aplicacao desktop Python para Windows 10 legado que adquire dados em tempo real de:
- SDM3055 via NI-VISA.
- Dinamometro via COM6.

O sistema apresenta leituras ao vivo, graficos em janela deslizante e regista dados em CSV diario.

## 2) Requisitos funcionais
- RF01: Iniciar/parar aquisicao por comando do operador.
- RF02: Mostrar valor atual do SDM3055 e do dinamometro.
- RF03: Mostrar estado de ligacao por dispositivo (CONNECTED, DISCONNECTED, RECONNECTING, ERROR).
- RF04: Permitir selecionar modo do SDM3055 na UI (DCV, ACV, DCI, ACI, R).
- RF05: Registar leituras em CSV rotativo diario.
- RF06: Reagir a perda de ligacao com reconexao automatica.

## 3) Requisitos nao funcionais
- RNF01: CPU media alvo < 15% em operacao continua.
- RNF02: RAM alvo < 250 MB.
- RNF03: UI responsiva durante aquisicao e escrita em ficheiro.
- RNF04: Logs em ficheiro rotativo para diagnostico.

## 4) Casos de uso principais
- CU01: Operador inicia aquisicao e observa valores ao vivo.
- CU02: Operador muda modo de medicao do SDM3055 sem reiniciar app.
- CU03: Operador perde e recupera cabo de instrumento sem crash.
- CU04: Operador valida dados gravados em CSV no Excel.

## 5) Fora de ambito
- Banco de dados SQL no MVP.
- Controlo remoto via rede.
- Calibracao automatica dos instrumentos.

## 6) Criterios de aceitacao
- CA01: App inicia sem erros em Windows 10 com NI-VISA instalado.
- CA02: Ambos dispositivos produzem leituras por >= 1h sem bloqueio da UI.
- CA03: CSV diario e criado e contem colunas canonicamente definidas.
- CA04: Desligar um dispositivo nao interrompe o outro.

## 7) Riscos e mitigacao
- Protocolo dinamometro desconhecido -> fase M0 discovery.
- Variacao de comandos SCPI -> fallback de leitura.
- Hardware legado -> taxas moderadas e processamento por filas.

## 8) Roadmap
- v1: Aquisicao, UI, grafico, CSV, reconexao.
- v1.1: Melhorias de parser dinamometro e exportacao por intervalo.
