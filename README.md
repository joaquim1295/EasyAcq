# Aquisição SDM3055 + Dinamómetro

Aplicação desktop Python para **Windows 10 (64 bits) e Windows 11** (executável e instalador testados nesse alvo).

- SDM3055 via NI-VISA (pyvisa)
- Dinamómetro via porta série (stream ou passivo)
- Visualização ao vivo, gráficos e registo CSV **por sessão** (`data/dados_<id_sessão>.csv`)
- Cabeçalho de metadados no CSV (versão da app, taxa, modo, IDN do multímetro quando disponível)
- Exportação de gráficos (PNG + CSV) com opção de incluir só SDM, só dinamómetro ou ambos, e CSV combinado (forward-fill)

## Pré-requisitos

- Python **3.11 ou 3.12** (64 bits; **recomendado 3.12**) para o ficheiro principal **`requirements.txt`** (NumPy **1.26.4**, compatível com CPUs sem x86-64-v2). Para **Python 3.13** use apenas **`requirements-py313.txt`** (NumPy 2.x — adequado a desenvolvimento, **proibido** para gerar `EasyAcq.exe`).
- NI-VISA instalado (para o SDM3055)
- **Windows 10 ou 11, 64 bits** (não há build para Windows 32 bits)
- No PC onde corre o **EasyAcq empacotado**: instalar [Visual C++ Redistributable 2015–2022 (x64)](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) se ainda não existir. O próprio **EasyAcq.exe** verifica no arranque se essas DLL podem ser carregadas; o **instalador** (`EasyAcq_Setup_…`) sugere abrir a página da Microsoft se o VC++ não estiver detetado e avisa se o **NI-VISA** não estiver presente após a instalação.

## Instalação

Recomenda-se **Python 3.12** (64 bits) para criar a venv — alinha com o build `EasyAcq` e com o GitHub Actions.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Com **Python 3.13** (só desenvolvimento):

```powershell
py -3.13 -m venv .venv313
.venv313\Scripts\Activate.ps1
pip install -r requirements-py313.txt
```

## Execução

```powershell
python -m app.main
```

Definições persistentes: `data/user_settings.json` (gravadas ao sair da aplicação).

## Discovery da COM (dinamómetro)

Script alinhado ao **mesmo parser em stream** que a app (`consume_stream_frames`):

```powershell
python scripts/dyno_discovery.py --port COM6 --seconds 3 --frame-chars 9
```

O relatório é escrito em `docs/dyno_discovery_report.md`.

## Colunas do CSV de aquisição

Cabeçalho após linhas `#` de comentário (delimitador `;`):

`sequencia`, `data`, `hora`, `momento_s`, `instrumento`, `modo`, `valor`, `unidade`

Apenas leituras com estado **OK** são escritas no CSV; o gráfico do SDM também ignora amostras **STALE**.

## Testes

```powershell
pytest tests/test_dyno_parser.py -q
```

## Build Windows (EasyAcq.exe)

Requisitos: ícone em **`assets\easyacq.ico`**. O script **`scripts\build_release.ps1` exige Python 3.11 ou 3.12** na venv (recusa 3.13+) para empacotar **NumPy 1.26**, compatível com **Windows 10** e CPUs sem conjunto de instruções x86-64-v2. Após o build, é criado o atalho **`EasyAcq.lnk`** na raiz do repositório (aponta para `dist\EasyAcq\EasyAcq.exe`; não versionar se preferir caminhos locais).

```powershell
pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --noconfirm EasyAcq.spec
```

O executável fica em `dist\EasyAcq\EasyAcq.exe` (modo **onedir**: copie a pasta inteira `EasyAcq`).

**Importante:** use apenas o programa em **`dist\EasyAcq\`** (`EasyAcq.exe` e a pasta `_internal` no mesmo nível). A pasta **`build\`** contém artefactos intermédios do PyInstaller; se executar um `.exe` a partir de `build\`, o Windows pode falhar ao carregar `python3xx.dll` (“módulo especificado não encontrado”).

### Erro «NumPy was built with baseline … (X86_V2)»

Significa que o `.exe` foi gerado com **NumPy 2.x** (o traceback mostra `numpy\_core\`). Apague `dist\` e `build\`, use uma **venv Python 3.12**, `pip install -r requirements.txt` e volte a correr **`scripts\build_release.ps1`** (o script força `numpy==1.26.4` e valida a versão antes do PyInstaller). Confirme com:

`python -c "import numpy; print(numpy.__version__)"` → deve imprimir **1.26.4** antes de empacotar.

Script único (limpa `build/`, gera `dist/` e o atalho `EasyAcq.lnk` na raiz):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

### Instalador (Inno Setup 6)

1. Instale [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Gere primeiro o PyInstaller (passo acima).
3. Compile o `.iss`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer
```

O ficheiro `EasyAcq_Setup_<versão>.exe` é criado em `release\`. Atualize a versão em `packaging\EasyAcq.iss` (`#define MyAppVersion`) em conjunto com `app\__version__.py` antes de publicar.

## Release no GitHub

1. Atualize `app\__version__.py` e `packaging\EasyAcq.iss` (`MyAppVersion`).
2. Crie e envie uma tag semântica (ex.: `v0.2.0`):

```powershell
git tag v0.2.0
git push origin v0.2.0
```

3. O workflow `.github/workflows/release.yml` compila no GitHub Actions e anexa à release:
   - `EasyAcq-windows.zip` (pasta da aplicação)
   - `EasyAcq_Setup_<versão>.exe` (instalador)

**Nota:** o utilizador final continua a precisar de **NI-VISA** instalado para o multímetro (pyvisa).

**Compatibilidade de CPU (executável):** o GitHub Actions e o `build_release.ps1` usam **NumPy 1.26.4** em **Python 3.12**. Não use `requirements-py313.txt` para builds destinados a PCs antigos.

## Empacotamento legado (PyInstaller sem spec)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onedir --name aquisicao app/main.py
```

## UAT rápido

- Iniciar a app e validar estados CONNECTED nos dois instrumentos.
- Confirmar valores nos painéis e na linha de estatísticas (descartes nas filas, Hz aproximado).
- Exportar com as opções desejadas e verificar ficheiros na pasta escolhida.
- Desligar um cabo e verificar RECONNECTING sem travar a UI.
