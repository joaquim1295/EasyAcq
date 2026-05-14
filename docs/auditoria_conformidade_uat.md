# Auditoria de Conformidade e UAT

## Conformidade por milestone
- M0: `scripts/dyno_discovery.py` cria relatorio com tentativas e sugestao base.
- M1: `app/workers/sdm3055_worker.py` implementa `CONF:<modo>`, `READ?`, fallback `MEAS:<modo>?`.
- M2: `app/workers/dyno_worker.py` conecta COM6, parseia payload numerico e publica eventos.
- M3: `app/core/events.py` e `app/core/bus.py` implementam modelo/event bus.
- M4: `app/ui/app.py` mostra cards, estados e seletor de modo.
- M5: `app/ui/app.py` renderiza graficos em janela deslizante.
- M6: `app/services/csv_writer.py` grava CSV diario com batch e flush periodico.
- M7: workers implementam reconexao com backoff exponencial.
- M8: `requirements.txt` (Python 3.11–3.12), opcional `requirements-py313.txt` (só dev 3.13), + `README.md` para setup e execucao.

## Roteiro UAT
1. Arranque normal
   - Passos: executar `python -m app.main`.
   - Esperado: janela abre sem excecao.
2. Leitura simultanea
   - Passos: ligar SDM3055 e COM6, pressionar Iniciar.
   - Esperado: valores em ambos paineis e curvas nos dois graficos.
3. Perda/retoma SDM3055
   - Passos: desligar/religar USB do SDM3055.
   - Esperado: estado vai para ERROR/RECONNECTING e retorna CONNECTED.
4. Perda/retoma COM6
   - Passos: desligar/religar dinamometro.
   - Esperado: comportamento equivalente sem travar UI.
5. Integridade CSV
   - Passos: abrir `data/dados_YYYY-MM-DD.csv` no Excel.
   - Esperado: colunas `ts,source,mode,value,unit,status,raw` e linhas consistentes.
6. Soak test
   - Passos: executar 1 hora.
   - Esperado: sem crash, UI responsiva, crescimento de CSV continuo.
