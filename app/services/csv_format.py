from __future__ import annotations

from datetime import datetime
from typing import Literal, Sequence

from app.config import AppConfig
from app.core.events import ReadingEvent
from app.services.units import (
    format_reading_display_unit,
    format_reading_value_csv,
    instrument_label,
)

try:
    from app.__version__ import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.0.0"

# Nomes internos (codigo, compatibilidade com ficheiros antigos)
SAMPLE_CSV_HEADERS = [
    "sequencia",
    "data",
    "hora",
    "momento_s",
    "instrumento",
    "modo",
    "valor",
    "unidade",
]

# Cabecalho apresentavel para cliente (CSV final / novas aquisicoes)
SAMPLE_CSV_HEADERS_PUBLIC = [
    "Indice da amostra",
    "Data",
    "Hora",
    "Tempo desde o inicio da sessao (s)",
    "Instrumento",
    "Modo de medicao",
    "Valor medido",
    "Unidade",
]

CHART_CSV_HEADERS = [
    "sequencia",
    "momento_s",
    "instrumento",
    "modo",
    "valor",
    "unidade",
]

CHART_CSV_HEADERS_PUBLIC = [
    "Indice da amostra",
    "Tempo no grafico (s)",
    "Instrumento",
    "Modo",
    "Valor medido",
    "Unidade",
]

MERGED_CSV_HEADERS_PUBLIC = [
    "Instante de referencia (s)",
    "Instante leitura multimetro (s)",
    "Valor multimetro",
    "Unidade multimetro",
    "Instante leitura dinamometro (s)",
    "Forca dinamometro",
    "Unidade dinamometro",
]

FIELD_DESCRIPTIONS_PUBLIC = [
    ("Indice da amostra", "Numero sequencial da amostra no ficheiro, a partir de 0"),
    ("Data", "Data local da amostra (AAAA-MM-DD)"),
    ("Hora", "Hora local da amostra (HH:MM:SS.mmm)"),
    ("Tempo desde o inicio da sessao (s)", "Segundos desde a primeira amostra do ficheiro"),
    ("Instrumento", "Multimetro ou dinamometro"),
    ("Modo de medicao", "Grandeza ou modo do instrumento (ex.: DCV, R, forca)"),
    ("Valor medido", "Leitura numerica"),
    ("Unidade", "Unidade da grandeza"),
]

CHART_FIELD_DESCRIPTIONS_PUBLIC = [
    ("Indice da amostra", "Numero sequencial da amostra exportada"),
    ("Tempo no grafico (s)", "Tempo relativo na janela do grafico"),
    ("Instrumento", "Origem da leitura"),
    ("Modo", "Modo ou grandeza registada"),
    ("Valor medido", "Valor numerico da amostra"),
    ("Unidade", "Unidade da grandeza"),
]


def write_comment_lines(handle, lines: Sequence[str]) -> None:
    for line in lines:
        handle.write(f"# {line}\n")


def _norm_header_row(headers: list[str]) -> list[str]:
    return [h.strip().lower() for h in headers]


def acquisition_headers_variant(norm: list[str]) -> Literal["internal", "public"] | None:
    if norm == [h.lower() for h in SAMPLE_CSV_HEADERS]:
        return "internal"
    if norm == [h.lower() for h in SAMPLE_CSV_HEADERS_PUBLIC]:
        return "public"
    return None


def acquisition_metadata_lines(
    config: AppConfig,
    *,
    dmm_mode: str,
    created: datetime,
    app_version: str = APP_VERSION,
) -> list[str]:
    lines = [
        "Relatorio de aquisicao — amostras em tempo real",
        f"Ficheiro criado em {created.isoformat(timespec='seconds')}",
        f"Versao da aplicacao: {app_version}",
        "Delimitador: ponto e virgula (;). Codificacao: UTF-8 com BOM (compativel com Excel).",
        "",
        "Definicoes da sessao",
        "----------------------",
        f"Taxa de aquisicao (Hz): {config.sample_hz:g}",
        f"Modo do multimetro (DMM): {dmm_mode}",
        f"Dinamometro: porta {config.dyno_port} @ {config.dyno_baudrate} baud",
        f"Unidade de forca: {config.dyno_force_unit}",
        (
            "Grafico forca (dinamometro): eixo automatico (min/max dos dados)"
            if config.dyno_chart_max_abs_force <= 0
            else f"Grafico forca (dinamometro): limite ±{config.dyno_chart_max_abs_force:g} {config.dyno_force_unit}"
        ),
        f"Resistencia no grafico (escala log): {'sim' if config.chart_resistance_log_scale else 'nao'}",
        "",
    ]
    idn = (config.last_dmm_idn or "").strip()
    if idn:
        lines.extend(
            [
                "Identificacao do multimetro (ultimo *IDN?)",
                "--------------------------------------------",
                idn,
                "",
            ]
        )
    lines.extend(
        [
            "Descricao das colunas",
            "----------------------",
            *[f"{name}: {description}" for name, description in FIELD_DESCRIPTIONS_PUBLIC],
            "",
        ]
    )
    return lines


def chart_metadata_lines(
    config: AppConfig,
    *,
    dmm_mode: str,
    created: datetime,
    app_version: str = APP_VERSION,
) -> list[str]:
    base = [
        "Exportacao das series do grafico (janela atual)",
        f"Criado em {created.isoformat(timespec='seconds')}",
        f"Versao da aplicacao: {app_version}",
        f"Janela do grafico (s): {config.chart_window_seconds}",
        f"Modo do multimetro (DMM): {dmm_mode}",
        f"Unidade de forca (dinamometro): {config.dyno_force_unit}",
        (
            "Grafico forca (dinamometro): eixo automatico (min/max dos dados)"
            if config.dyno_chart_max_abs_force <= 0
            else f"Grafico forca (dinamometro): limite ±{config.dyno_chart_max_abs_force:g} {config.dyno_force_unit}"
        ),
        f"Resistencia no grafico (escala log): {'sim' if config.chart_resistance_log_scale else 'nao'}",
        "",
        "Descricao das colunas",
        "----------------------",
        *[f"{name}: {desc}" for name, desc in CHART_FIELD_DESCRIPTIONS_PUBLIC],
        "",
    ]
    idn = (config.last_dmm_idn or "").strip()
    if idn:
        base.insert(3, f"Multimetro (*IDN?): {idn}")
    return base


def merged_metadata_lines(
    config: AppConfig,
    *,
    dmm_mode: str,
    dmm_display_unit: str,
    dyno_unit: str,
    created: datetime,
    app_version: str = APP_VERSION,
) -> list[str]:
    return [
        "Series alinhadas por instante — multimetro e dinamometro",
        f"Criado em {created.isoformat(timespec='seconds')}",
        f"Versao da aplicacao: {app_version}",
        "",
        "Metodo",
        "------",
        "Cada linha usa um instante da uniao dos tempos amostrados por ambos os instrumentos.",
        "Para cada instante, o valor de cada instrumento e o da ultima amostra com instante",
        "menor ou igual a esse instante (ultimo valor conhecido ate esse momento).",
        "Celulas vazias: ainda nao havia amostra desse instrumento.",
        "",
        "Contexto",
        "----------",
        f"Modo do multimetro (DMM): {dmm_mode}",
        f"Unidade dos valores do multimetro: {dmm_display_unit}",
        f"Unidade dos valores do dinamometro: {dyno_unit}",
        f"Janela do grafico na aplicacao (s): {config.chart_window_seconds}",
        "",
        "Descricao das colunas",
        "----------------------",
        "Instante de referencia (s): instante comum da linha",
        "Instante leitura multimetro (s): instante da amostra do multimetro usada nesta linha",
        "Valor multimetro / Unidade multimetro: leitura no modo indicado",
        "Instante leitura dinamometro (s): instante da amostra do dinamometro usada nesta linha",
        "Forca dinamometro / Unidade dinamometro: forca na unidade configurada",
        "",
    ]


def parse_event_timestamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def split_timestamp(ts: str) -> tuple[str, str]:
    moment = parse_event_timestamp(ts)
    return moment.strftime("%Y-%m-%d"), moment.strftime("%H:%M:%S.%f")[:-3]


def moment_seconds(origin: datetime, current: datetime) -> str:
    return f"{(current - origin).total_seconds():.2f}"


def sample_row(
    event: ReadingEvent,
    *,
    sequence: int,
    origin: datetime,
) -> list[str]:
    current = parse_event_timestamp(event.ts)
    date_value, time_value = split_timestamp(event.ts)
    raw_row = [
        str(sequence),
        date_value,
        time_value,
        moment_seconds(origin, current),
        instrument_label(event.source),
        event.mode or "",
        format_reading_value_csv(event.source, event.value, event.unit, event.mode),
        format_reading_display_unit(event.source, event.unit, event.mode),
    ]
    return raw_row


def is_sample_reading(event: ReadingEvent) -> bool:
    return event.status == "OK"
