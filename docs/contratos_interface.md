# Contratos de Interface

## ReadingEvent
Campos obrigatorios:
- `ts: str` (ISO-8601 com milissegundos)
- `source: str` (`dmm` ou `dyno`; em CSV legado aceita-se `sdm3055` / `Multimetro`)
- `value: float`
- `unit: str`
- `status: str` (`OK`, `STALE`, `OVERLOAD`, `ERROR`)

Campos opcionais:
- `mode: str | None`
- `raw: str`

## StatusEvent
- `ts: str`
- `source: str`
- `state: str` (`CONNECTED`, `DISCONNECTED`, `RECONNECTING`, `ERROR`)
- `detail: str`

## APIs publicas por modulo
- `EventBus.publish_reading(event)`
- `EventBus.publish_status(event)`
- `Supervisor.start()`
- `Supervisor.stop()`
- `Supervisor.set_multimeter_mode(mode)`
- `MainWindow.run()`

## Invariantes
- `value` deve ser numerico para `status=OK`.
- `source` em novos eventos deve ser `dmm` ou `dyno` (importação antiga pode mapear `sdm3055`).
- `ts` sempre presente e no formato ISO.
- Shutdown deve terminar threads em ate 2 s por join.

## Exemplo valido
```json
{
  "ts": "2026-05-06T21:20:11.123",
  "source": "dmm",
  "mode": "DCV",
  "value": 5.012,
  "unit": "V",
  "status": "OK",
  "raw": "5.0120"
}
```

## Exemplo invalido
```json
{
  "ts": "",
  "source": "meter",
  "value": "abc",
  "unit": "V",
  "status": "OK"
}
```
