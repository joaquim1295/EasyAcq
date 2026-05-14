# Assinatura de código (Windows / EasyAcq)

Instaladores e executáveis **sem** assinatura Authenticode aparecem no Windows como provenientes de um **«Editor desconhecido»** e o SmartScreen pode bloquear ou pedir confirmação extra. **Isto não se resolve** com ícones, textos no assistente ou publicação no GitHub: é preciso um **certificado de assinatura de código** emitido por uma autoridade em que o Windows confie (ou, em contexto empresarial, políticas internas / certificados da organização).

## O que precisa

1. **Certificado de assinatura de código** (ex.: Standard ou **EV** Code Signing). Fornecedores comuns: DigiCert, Sectigo, SSL.com, etc. Certificados **EV** tendem a gerar reputação no SmartScreen mais depressa, mas têm custo e processo de validação mais exigentes.
2. **Windows SDK** ou ferramentas de build que incluam **`signtool.exe`** (comum em máquinas de desenvolvimento Windows com Visual Studio / Windows SDK).
3. **Servidor de carimbo de tempo** (timestamp), para o ficheiro continuar válido após expirar o certificado de assinatura.

## Assinar o instalador depois do Inno

Exemplo (ajuste caminhos e palavra-passe; **não** commite o `.pfx` ao repositório):

```powershell
signtool sign /fd sha256 `
  /tr "http://timestamp.digicert.com" /td sha256 `
  /f "C:\segredos\EasyAcq_codesign.pfx" /p "PALAVRA_SECRETA" `
  /d "EasyAcq" `
  "release\EasyAcq_Setup_0.2.3.exe"
```

Verifique com:

```powershell
signtool verify /pa "release\EasyAcq_Setup_0.2.3.exe"
```

## Integrar com Inno Setup

O Inno pode assinar o `Setup.exe` (e opcionalmente o desinstalador) durante a compilação, através da directiva [`SignTool`](https://jrsoftware.org/ishelp/index.php?topic=setup_signtool) no `[Setup]`. O formato exacto depende da sua instalação do `signtool` e do armazenamento da chave (ficheiro PFX, Azure Key Vault, token USB, etc.).

Recomendação: primeiro assine **manualmente** com `signtool` até o fluxo estar estável; só depois automatize no `.iss` ou num passo de CI com segredos (`GITHUB_SECRET` com o PFX em base64, etc.), seguindo as boas práticas da sua equipa.

## CI (GitHub Actions)

É possível assinar no workflow de release, mas o **segredo** do certificado deve ficar em **GitHub Encrypted Secrets**, nunca em texto claro no repositório. Alternativas modernas incluem assinatura via **Azure Key Vault** ou fornecedores que expõem API de assinatura.

## Resumo

| Medida | Efeito no aviso do Windows |
|--------|------------------------------|
| Ícone do Setup / imagens do assistente | Apenas **apresentação**; não altera confiança criptográfica. |
| Publicar no GitHub Releases | **Não** substitui assinatura. |
| **Assinatura Authenticode** com certificado válido | Identifica o **editor** e é o caminho correcto para reduzir bloqueios do SmartScreen. |

Para a Nanopaint / distribuição interna, avalie certificado da própria organização ou política de «Trusted publishers» em domínio gerido.
