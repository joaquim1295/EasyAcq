from __future__ import annotations

import csv
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from matplotlib.figure import Figure

from app.config import AppConfig
from app.services.csv_format import (
    CHART_CSV_HEADERS_PUBLIC,
    MERGED_CSV_HEADERS_PUBLIC,
    SAMPLE_CSV_HEADERS_PUBLIC,
    acquisition_headers_variant,
    acquisition_metadata_lines,
    chart_metadata_lines,
    is_sample_reading,
    merged_metadata_lines,
    parse_event_timestamp,
    sample_row,
    write_comment_lines,
)
from app.services.units import format_reading_value_csv, instrument_label, normalize_dyno_force_unit

DMM_MODE_UNITS = {
    "DCV": "V",
    "ACV": "V",
    "DCI": "A",
    "ACI": "A",
    "R": "OHM",
}

SUB_RESULTADO = "resultado"
README_NAME = "LEIAME.txt"


def _chart_export_dmm_unit(dmm_mode: str) -> str:
    if dmm_mode.strip().upper() == "R":
        return "MΩ"
    return DMM_MODE_UNITS.get(dmm_mode.strip().upper(), "")


def _safe_session_tag(session_csv_id: str) -> str:
    s = re.sub(r"[^\w\-.]+", "_", (session_csv_id or "").strip(), flags=re.UNICODE)
    s = s.strip("._") or "sem_id"
    return s[:80]


def export_session_folder_name(*, created: datetime, session_csv_id: str) -> str:
    stamp = created.strftime("%Y-%m-%d_%H%M%S")
    return f"exportacao_{stamp}_{_safe_session_tag(session_csv_id)}"


@dataclass(frozen=True)
class ExportResult:
    """Resultado de uma exportacao; `directory` e a pasta da sessao criada."""

    directory: Path
    parent_dest: Path
    chart_csv: Path
    chart_png: Path
    acquisition_csv: Path | None
    chart_rows: int
    chart_csv_dmm: Path | None = None
    chart_csv_dyno: Path | None = None
    merged_csv: Path | None = None
    chart_png_integrated: Path | None = None
    raw_acquisition_csv: Path | None = None
    readme_path: Path | None = None

    def all_files(self) -> list[str]:
        rel = []
        if self.readme_path is not None:
            rel.append(self.readme_path.relative_to(self.directory).as_posix())
        if self.raw_acquisition_csv is not None:
            rel.append(self.raw_acquisition_csv.relative_to(self.directory).as_posix())
        rel.append(self.chart_csv.relative_to(self.directory).as_posix())
        rel.append(self.chart_png.relative_to(self.directory).as_posix())
        if self.chart_csv_dmm is not None:
            rel.append(self.chart_csv_dmm.relative_to(self.directory).as_posix())
        if self.chart_csv_dyno is not None:
            rel.append(self.chart_csv_dyno.relative_to(self.directory).as_posix())
        if self.merged_csv is not None:
            rel.append(self.merged_csv.relative_to(self.directory).as_posix())
        if self.acquisition_csv is not None:
            rel.append(self.acquisition_csv.relative_to(self.directory).as_posix())
        if self.chart_png_integrated is not None:
            rel.append(self.chart_png_integrated.relative_to(self.directory).as_posix())
        return rel


def export_session(
    dest_parent: Path,
    *,
    config: AppConfig,
    figure: Figure,
    dmm_times: Sequence[float],
    dmm_values: Sequence[float],
    dmm_mode: str,
    dyno_times: Sequence[float],
    dyno_values: Sequence[float],
    dyno_force_unit: str,
    session_acquisition_csv: Path | None = None,
    session_csv_id: str = "",
    include_dmm: bool = True,
    include_dyno: bool = True,
    write_merged: bool = False,
    figure_integrated: Figure | None = None,
    save_integrated_png: bool = False,
) -> ExportResult:
    dest_parent.mkdir(parents=True, exist_ok=True)
    created = datetime.now()
    base_name = export_session_folder_name(created=created, session_csv_id=session_csv_id)
    session_root = dest_parent / base_name
    suffix = 0
    while session_root.exists():
        suffix += 1
        session_root = dest_parent / f"{base_name}_{suffix}"
    session_root.mkdir(parents=False)

    resultado = session_root / SUB_RESULTADO
    resultado.mkdir(parents=True)

    if not include_dmm and not include_dyno:
        raise ValueError("Selecione pelo menos um instrumento para exportar.")

    dmm_unit = _chart_export_dmm_unit(dmm_mode)
    dyno_unit = normalize_dyno_force_unit(dyno_force_unit)

    chart_csv_dmm: Path | None = None
    chart_csv_dyno: Path | None = None
    merged_csv: Path | None = None
    chart_rows = 0

    if include_dmm and include_dyno:
        chart_csv = resultado / "series_amostras_grafico.csv"
        chart_rows = _write_chart_csv(
            chart_csv,
            config=config,
            dmm_mode=dmm_mode,
            dmm_unit=dmm_unit,
            dyno_unit=dyno_unit,
            dmm_times=dmm_times,
            dmm_values=dmm_values,
            dyno_times=dyno_times,
            dyno_values=dyno_values,
            include_dmm=True,
            include_dyno=True,
            created=created,
        )
        chart_csv_dmm = resultado / "series_amostras_grafico_multimetro.csv"
        _write_chart_csv(
            chart_csv_dmm,
            config=config,
            dmm_mode=dmm_mode,
            dmm_unit=dmm_unit,
            dyno_unit=dyno_unit,
            dmm_times=dmm_times,
            dmm_values=dmm_values,
            dyno_times=(),
            dyno_values=(),
            include_dmm=True,
            include_dyno=False,
            created=created,
        )
        chart_csv_dyno = resultado / "series_amostras_grafico_dinamometro.csv"
        _write_chart_csv(
            chart_csv_dyno,
            config=config,
            dmm_mode=dmm_mode,
            dmm_unit=dmm_unit,
            dyno_unit=dyno_unit,
            dmm_times=(),
            dmm_values=(),
            dyno_times=dyno_times,
            dyno_values=dyno_values,
            include_dmm=False,
            include_dyno=True,
            created=created,
        )
        if write_merged and dmm_times and dyno_times:
            merged_csv = resultado / "series_alinhadas_por_tempo.csv"
            _write_merged_csv(
                merged_csv,
                config=config,
                created=created,
                dmm_times=dmm_times,
                dmm_values=dmm_values,
                dmm_unit=dmm_unit,
                dmm_mode=dmm_mode,
                dyno_times=dyno_times,
                dyno_values=dyno_values,
                dyno_unit=dyno_unit,
            )
    elif include_dmm:
        chart_csv = resultado / "series_amostras_grafico_multimetro.csv"
        chart_rows = _write_chart_csv(
            chart_csv,
            config=config,
            dmm_mode=dmm_mode,
            dmm_unit=dmm_unit,
            dyno_unit=dyno_unit,
            dmm_times=dmm_times,
            dmm_values=dmm_values,
            dyno_times=(),
            dyno_values=(),
            include_dmm=True,
            include_dyno=False,
            created=created,
        )
    else:
        chart_csv = resultado / "series_amostras_grafico_dinamometro.csv"
        chart_rows = _write_chart_csv(
            chart_csv,
            config=config,
            dmm_mode=dmm_mode,
            dmm_unit=dmm_unit,
            dyno_unit=dyno_unit,
            dmm_times=(),
            dmm_values=(),
            dyno_times=dyno_times,
            dyno_values=dyno_values,
            include_dmm=False,
            include_dyno=True,
            created=created,
        )

    chart_png = resultado / "grafico_janela_principal.png"
    save_chart_image(chart_png, figure)
    chart_png_integrated: Path | None = None
    if save_integrated_png and figure_integrated is not None:
        chart_png_integrated = resultado / "grafico_integrado.png"
        save_chart_image(chart_png_integrated, figure_integrated)

    acquisition_csv = None
    if session_acquisition_csv is not None and session_acquisition_csv.exists():
        fmt_path = resultado / "aquisicao_sessao_formatada.csv"
        if write_formatted_acquisition_csv(
            session_acquisition_csv,
            fmt_path,
            refresh_metadata=config,
            dmm_mode_for_comments=dmm_mode,
        ):
            acquisition_csv = fmt_path

    readme = session_root / README_NAME
    session_data_hint: Path | None = None
    if session_acquisition_csv is not None and session_acquisition_csv.exists():
        session_data_hint = session_acquisition_csv
    _write_export_readme(
        readme,
        session_root=session_root,
        parent_dest=dest_parent,
        created=created,
        session_csv_id=session_csv_id or "(sem identificador)",
        chart_csv=chart_csv,
        chart_png=chart_png,
        merged_csv=merged_csv,
        acquisition_csv=acquisition_csv,
        session_data_file=session_data_hint,
        chart_csv_dmm=chart_csv_dmm,
        chart_csv_dyno=chart_csv_dyno,
        chart_png_integrated=chart_png_integrated,
    )

    return ExportResult(
        directory=session_root,
        parent_dest=dest_parent,
        chart_csv=chart_csv,
        chart_png=chart_png,
        acquisition_csv=acquisition_csv,
        chart_rows=chart_rows,
        chart_csv_dmm=chart_csv_dmm,
        chart_csv_dyno=chart_csv_dyno,
        merged_csv=merged_csv,
        chart_png_integrated=chart_png_integrated,
        raw_acquisition_csv=None,
        readme_path=readme,
    )


def _write_export_readme(
    path: Path,
    *,
    session_root: Path,
    parent_dest: Path,
    created: datetime,
    session_csv_id: str,
    chart_csv: Path,
    chart_png: Path,
    merged_csv: Path | None,
    acquisition_csv: Path | None,
    session_data_file: Path | None,
    chart_csv_dmm: Path | None,
    chart_csv_dyno: Path | None,
    chart_png_integrated: Path | None,
) -> None:
    lines = [
        "Pacote de exportacao — multimetro e dinamometro",
        "==============================================",
        "",
        f"Data e hora da exportacao: {created.isoformat(timespec='seconds')}",
        f"Identificador de sessao (interno): {session_csv_id}",
        f"Pasta escolhida pelo utilizador: {parent_dest}",
        f"Esta pasta: {session_root.name}",
        "",
        "Organizacao",
        "-----------",
        f"{SUB_RESULTADO}/",
        "    Ficheiros prontos para analise ou relatorio:",
        f"    - {chart_csv.name}: series do grafico (conteudo conforme opcoes de exportacao).",
    ]
    if chart_csv_dmm is not None:
        lines.append(
            f"    - {chart_csv_dmm.name}: serie do multimetro apenas (mesma janela temporal que o grafico)."
        )
    if chart_csv_dyno is not None:
        lines.append(
            f"    - {chart_csv_dyno.name}: serie do dinamometro apenas (mesma janela temporal que o grafico)."
        )
    lines.append(f"    - {chart_png.name}: imagem do painel de graficos (multimetro + dinamometro).")
    if chart_png_integrated is not None:
        lines.append(f"    - {chart_png_integrated.name}: grafico integrado (duplo eixo).")
    if merged_csv is not None:
        lines.append(
            f"    - {merged_csv.name}: uma linha por instante, valores alinhados (ultima amostra ate cada instante)."
        )
    if acquisition_csv is not None:
        lines.append(
            f"    - {acquisition_csv.name}: registo da sessao com cabecalhos e formato normalizado para leitura humana."
        )
    elif session_data_file is not None:
        lines.append(
            "    - (CSV formatado da aquisicao nao foi gerado; consulte o ficheiro bruto na pasta de dados da aplicacao.)"
        )
    else:
        lines.append("    - (Sem ficheiro de aquisicao da sessao nesta exportacao — nao ha CSV formatado.)")

    if session_data_file is not None:
        lines.extend(
            [
                "",
                "Registo bruto (nao duplicado neste pacote)",
                "------------------------------------------",
                f"    O ficheiro continuo gravado durante a aquisicao permanece em:",
                f"    {session_data_file}",
            ]
        )

    lines.extend(
        [
            "",
            "Formato dos CSV",
            "---------------",
            "Delimitador: ponto e virgula (;). Codificacao: UTF-8 com BOM.",
            "Linhas que comecam por # sao comentarios (metadados); o Excel pode oculta-las ou mostra-las como texto.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_chart_csv(
    path: Path,
    *,
    config: AppConfig,
    dmm_mode: str,
    dmm_unit: str,
    dyno_unit: str,
    dmm_times: Sequence[float],
    dmm_values: Sequence[float],
    dyno_times: Sequence[float],
    dyno_values: Sequence[float],
    include_dmm: bool,
    include_dyno: bool,
    created: datetime,
) -> int:
    rows = 0
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        write_comment_lines(
            handle,
            chart_metadata_lines(
                config,
                dmm_mode=dmm_mode,
                created=created,
            ),
        )
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(list(CHART_CSV_HEADERS_PUBLIC))
        if include_dmm:
            for elapsed, value in zip(dmm_times, dmm_values):
                writer.writerow(
                    [
                        str(rows),
                        f"{elapsed:.2f}",
                        instrument_label("dmm"),
                        dmm_mode,
                        format_reading_value_csv("dmm", float(value), dmm_unit, dmm_mode),
                        dmm_unit,
                    ]
                )
                rows += 1
        if include_dyno:
            for elapsed, value in zip(dyno_times, dyno_values):
                writer.writerow(
                    [
                        str(rows),
                        f"{elapsed:.2f}",
                        instrument_label("dyno"),
                        f"FORCE_{dyno_unit.upper()}",
                        format_reading_value_csv("dyno", float(value), dyno_unit, None),
                        dyno_unit,
                    ]
                )
                rows += 1
    return rows


def _forward_at(
    t: float,
    times: Sequence[float],
    values: Sequence[float],
    *,
    source: str,
    unit: str,
    mode: str | None,
) -> tuple[str, str]:
    if not times:
        return "", ""
    idx = bisect_right(times, t) - 1
    if idx < 0:
        return "", ""
    v = float(values[idx])
    return f"{times[idx]:.2f}", format_reading_value_csv(source, v, unit, mode)


def _write_merged_csv(
    path: Path,
    *,
    config: AppConfig,
    created: datetime,
    dmm_times: Sequence[float],
    dmm_values: Sequence[float],
    dmm_unit: str,
    dmm_mode: str,
    dyno_times: Sequence[float],
    dyno_values: Sequence[float],
    dyno_unit: str,
) -> None:
    timeline = sorted(set(dmm_times) | set(dyno_times))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        write_comment_lines(
            handle,
            merged_metadata_lines(
                config,
                dmm_mode=dmm_mode,
                dmm_display_unit=dmm_unit,
                dyno_unit=dyno_unit,
                created=created,
            ),
        )
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(list(MERGED_CSV_HEADERS_PUBLIC))
        for t in timeline:
            dmm_tref, dmm_v = _forward_at(
                t, dmm_times, dmm_values, source="dmm", unit=dmm_unit, mode=dmm_mode
            )
            dyn_tref, dyn_v = _forward_at(
                t, dyno_times, dyno_values, source="dyno", unit=dyno_unit, mode=None
            )
            writer.writerow(
                [
                    f"{t:.2f}",
                    dmm_tref,
                    dmm_v,
                    dmm_unit,
                    dyn_tref,
                    dyn_v,
                    dyno_unit,
                ]
            )


def _strip_csv_cell_text(cell: str) -> str:
    s = cell.strip().lstrip("\ufeff")
    if s.startswith("'"):
        return s[1:]
    return s


def write_formatted_acquisition_csv(
    src: Path,
    dst: Path,
    *,
    refresh_metadata: AppConfig | None = None,
    dmm_mode_for_comments: str = "DCV",
) -> bool:
    if not src.exists():
        return False

    lines = src.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        return False

    comment_end = 0
    while comment_end < len(lines) and lines[comment_end].startswith("#"):
        comment_end += 1
    if comment_end >= len(lines):
        return False

    delimiter = ";" if ";" in lines[comment_end] else ","
    reader = csv.reader(lines[comment_end:], delimiter=delimiter)
    headers = next(reader, None)
    if headers is None:
        return False

    normalized = [header.strip().lower() for header in headers]
    variant = acquisition_headers_variant(normalized)
    if variant is None:
        legacy = _legacy_column_map(normalized)
        if legacy is None:
            return False
    else:
        legacy = None

    rows_written = 0
    ncols = len(SAMPLE_CSV_HEADERS_PUBLIC)
    meta_created = datetime.now()
    with dst.open("w", newline="", encoding="utf-8-sig") as target:
        if refresh_metadata is not None:
            write_comment_lines(
                target,
                acquisition_metadata_lines(
                    refresh_metadata,
                    dmm_mode=dmm_mode_for_comments,
                    created=meta_created,
                ),
            )
        else:
            for line in lines[:comment_end]:
                target.write(f"{line}\n")
        writer = csv.writer(target, delimiter=";")
        writer.writerow(list(SAMPLE_CSV_HEADERS_PUBLIC))

        if variant is not None:
            for row in reader:
                if not row:
                    continue
                cells = row[:ncols]
                writer.writerow([_strip_csv_cell_text(c) for c in cells])
                rows_written += 1
            return rows_written > 0

        assert legacy is not None
        origin: datetime | None = None
        for row in reader:
            if not row:
                continue
            event = _event_from_legacy_row(row, legacy)
            if event is None or not is_sample_reading(event):
                continue
            if origin is None:
                origin = parse_event_timestamp(event.ts)
            writer.writerow(sample_row(event, sequence=rows_written, origin=origin))
            rows_written += 1
    return rows_written > 0


def _legacy_column_map(headers: list[str]) -> dict[str, int] | None:
    aliases = {
        "ts": ("ts", "data/hora"),
        "source": ("source", "instrumento"),
        "mode": ("mode", "modo"),
        "value": ("value", "valor"),
        "unit": ("unit", "unidade"),
        "status": ("status", "estado"),
    }
    mapping: dict[str, int] = {}
    for key, options in aliases.items():
        index = _first_header_index(headers, options)
        if index is None:
            if key == "status":
                continue
            return None
        mapping[key] = index
    return mapping


def _first_header_index(headers: list[str], options: tuple[str, ...]) -> int | None:
    for option in options:
        try:
            return headers.index(option)
        except ValueError:
            continue
    return None


def _event_from_legacy_row(row: list[str], columns: dict[str, int]) -> "ReadingEvent | None":
    from app.core.events import ReadingEvent

    try:
        raw_v = row[columns["value"]].strip().lstrip("\ufeff")
        if raw_v.startswith("'"):
            raw_v = raw_v[1:]
        raw_v = raw_v.replace(",", ".")
        value = float(raw_v)
    except (IndexError, ValueError):
        return None
    try:
        source = row[columns["source"]].strip()
        unit = row[columns["unit"]].strip()
        mode = row[columns["mode"]].strip()
        ts = row[columns["ts"]].strip()
    except IndexError:
        return None
    if not source:
        return None
    status = "OK"
    if "status" in columns:
        try:
            status = row[columns["status"]].strip() or "OK"
        except IndexError:
            status = "OK"
    normalized_source = source.lower()
    if normalized_source in {"multímetro", "multimetro", "sdm3055"}:
        source = "dmm"
    elif normalized_source in {"dinamómetro", "dinamometro"}:
        source = "dyno"
    return ReadingEvent(
        ts=ts,
        source=source,
        value=value,
        unit=unit,
        status=status,
        mode=mode or None,
    )


def save_chart_image(path: Path, figure: Figure) -> None:
    figure.savefig(path, dpi=150, bbox_inches="tight")


def session_acquisition_path(csv_dir: Path, session_csv_id: str) -> Path:
    return csv_dir / f"dados_{session_csv_id}.csv"


def daily_acquisition_path(csv_dir: Path) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    return csv_dir / f"dados_{stamp}.csv"
