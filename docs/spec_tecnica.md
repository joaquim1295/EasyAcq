# Especificacao Tecnica

## Arquitetura
Pipeline por eventos com workers isolados:
- Worker SDM3055 (pyvisa).
- Worker dinamometro (pyserial).
- Event bus com filas thread-safe.
- Consumidores: UI e CSV writer.
- Supervisor para lifecycle e reconexao.

## Fluxo de dados
1. Worker le frame.
2. Worker publica `ReadingEvent` no bus.
3. UI atualiza cards e grafico.
4. CSV writer persiste evento em lote.
5. Status de ligacao via `StatusEvent`.

## Concorrencia
- Threads dedicadas por worker e writer.
- UI permanece na thread principal Tkinter.
- Queue com tamanho maximo e politica de descarte mais antigo para backpressure.

## Performance budget
- Aquisicao por fonte: 2-5 Hz (default 2).
- Redraw UI/grafico: 3 Hz.
- Janela de grafico: 60 s.
- CSV batch: 20 linhas ou 1 s.

## Reconexao
- Backoff exponencial por dispositivo:
  - inicial: 1 s
  - maximo: 30 s

## Logging
- Rotating file handler:
  - `logs/app.log`
  - 1 MB por ficheiro
  - 5 backups

## Persistencia
- CSV diario: `data/dados_YYYY-MM-DD.csv`.
- Encoding: UTF-8 BOM para compatibilidade com Excel.

## Plano de testes tecnico
- Teste de arranque sem dispositivos.
- Teste com apenas SDM3055.
- Teste com apenas COM6.
- Teste com ambos e desconexao/reconexao.
- Teste de soak de 1 hora.
