# EasyAcq

Aplicação **Windows** para aquisição em bancada de **multímetro digital** (Siglent SDM3055 via **NI-VISA**) e **dinamómetro** (porta série), com painéis em tempo real, gráficos e registo em **CSV** por sessão. Desenvolvida para apoiar ensaios e **controlo de qualidade** na **Nanopaint, Lda.**

**Código-fonte:** [github.com/joaquim1295/EasyAcq](https://github.com/joaquim1295/EasyAcq)

---

## O que o programa faz

- Liga ao **SDM3055** (VISA) e ao **dinamómetro** (COM), com reconexão automática.
- Mostra **valores ao vivo** e **gráficos** (multímetro, dinamómetro e vista integrada opcional).
- Grava **CSV por sessão** em `data\`, com metadados no cabeçalho.
- **Exporta** pasta com CSV das séries do gráfico, PNG e registo formatado (ver opções na app).

---

## Requisitos no seu PC (antes de instalar)

| Requisito | Nota |
|-----------|------|
| **Windows 10 ou 11 (64 bits)** | Não existe versão para Windows 32 bits. |
| **Visual C++ Redistributable 2015–2022 (x64)** | [Descarregar da Microsoft](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Muitos PCs já têm; a app avisa se faltar. |
| **NI-VISA** (National Instruments) | Necessário para o **multímetro** USB/GPIB. [NI-VISA](https://www.ni.com/en/support/downloads/drivers.download-ni-visa.html). Pode usar só o dinamómetro em série sem VISA. |

---

## Como instalar (utilizador)

1. Abra **[Releases](https://github.com/joaquim1295/EasyAcq/releases)** do repositório.
2. Na última versão, descarregue **um** dos seguintes:
   - **`EasyAcq_Setup_X.Y.Z.exe`** — instalador (recomendado). Instala em `%LocalAppData%\Programs\EasyAcq` e cria atalhos.
   - **`EasyAcq-windows.zip`** — pasta portátil. Extraia **toda** a pasta e execute **`EasyAcq.exe`** no interior (deve existir a pasta **`_internal`** ao lado do `.exe`).

3. Instale o **VC++** e o **NI-VISA** se ainda não tiver (tabela acima).

A primeira execução pode mostrar avisos se o VISA não estiver detetado; o multímetro só funciona com o NI-VISA instalado.

---

## Desenvolvimento (código-fonte)

Requer **Python 3.11 ou 3.12** (recomendado **3.12**) e o ficheiro `requirements.txt`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

Para **Python 3.13** (apenas desenvolvimento local): `pip install -r requirements-py313.txt` — **não** use esta venv para gerar o executável publicado.

**Build do `.exe` (PyInstaller)** na máquina de desenvolvimento, com Python 3.12:

```powershell
pip install -r requirements.txt -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

Instalador **Inno Setup** local: instale [Inno Setup 6](https://jrsoftware.org/isdl.php) e corra `scripts\build_release.ps1 -Installer` (gera `release\EasyAcq_Setup_….exe`).

---

## Publicação de versões (mantenedores)

Ao criar uma **tag** `v*` (ex.: `v0.2.2`) e enviar para o GitHub, o [workflow Release](.github/workflows/release.yml) gera o **ZIP** e o **instalador** e associa-os à release dessa tag.

Versão da aplicação: `app\__version__.py` e `#define MyAppVersion` em `packaging\EasyAcq.iss` devem coincidir antes de etiquetar.
